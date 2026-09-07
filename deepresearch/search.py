"""Keyless multi-backend web search and page fetching. Standard library only.

Why this exists
---------------
Every hosted search API wants a key: Tavily, Serper, Exa, Brave. That turns a
research tool into a billing relationship, and it puts a hard floor under the
cost of a single question. Everything here is keyless.

Why *multi*-backend
-------------------
DuckDuckGo rate-limits aggressively and, when it does, answers with an HTTP 202
challenge page that parses to **zero results while looking like success**. A
single-backend tool reads that as "the web contains nothing on this topic" and
the agent above it faithfully reports that there is no evidence. So every
backend attempt is recorded and reported: a null must be *provably* a null.

Backends, all keyless and all independent of one another:

    ddg-html, ddg-lite   general web
    mojeek               independent crawler and index, not a Bing/Google reseller
    wikipedia            encyclopaedic grounding
    openalex             ~250M scholarly works
    crossref             DOI registry and publisher metadata
    hn                   practitioner signal via the Algolia API

The DOI trap
------------
Crossref and OpenAlex both return ``doi.org`` links, and a DOI resolver is not
fetchable: it redirects to a publisher that answers crawlers with a JavaScript
challenge. Measured, fetching ``doi.org/10.1038/nature12373`` returns about 212
bytes of "a required part of this site couldn't load". A research run can
therefore fetch sixteen sources and extract zero claims while every log line
says the searches succeeded.

``fetch`` routes any DOI to ``api.crossref.org/works/<doi>`` instead, which is
keyless and returns title, journal, year, authors and usually the abstract. On
the run that first exposed this, the same sixteen sources went from 0 claims to
33.
"""
from __future__ import annotations

import html
import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed

__all__ = ["search", "fetch", "health", "reset_health", "BACKENDS"]

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/125.0 Safari/537.36")
# Crossref asks for a contact address in the User-Agent as a courtesy; it buys
# you the "polite" pool and better rate limits.
CROSSREF_UA = "deepresearch/1.0 (+https://github.com/7inaydas-cmyk/deepresearch)"
TIMEOUT = 25

BACKENDS = ["searxng", "ddg-html", "ddg-lite", "mojeek", "wikipedia",
            "openalex", "crossref", "europepmc", "pubmed", "arxiv", "hn"]
# Order matters: general web first (broadest), then independent index, then the
# scholarly and practitioner sources that stay healthy when the web ones are
# challenged.
# searxng first when configured: it is the only general-web source that keeps
# working when DDG and Mojeek challenge the host. It no-ops instantly when
# DR_SEARXNG_URL is unset, so leaving it here costs nothing.
DEFAULT_CHAIN = ["searxng", "ddg-html", "ddg-lite", "mojeek", "wikipedia",
                 "crossref", "europepmc", "openalex", "pubmed", "arxiv", "hn"]

_health: dict[str, dict[str, int]] = {}
_health_lock = threading.Lock()


def health() -> dict[str, dict[str, int]]:
    """Per-backend attempt/result counts for the current process.

    Report this. A run where every general-web backend shows ``results: 0`` saw
    a scholarly-only slice of the web, and its coverage gaps are a search
    artefact rather than evidence that nothing exists.
    """
    with _health_lock:
        return {k: dict(v) for k, v in _health.items()}


def reset_health() -> None:
    with _health_lock:
        _health.clear()


def _note(backend: str, status: str, n: int) -> None:
    with _health_lock:
        h = _health.setdefault(backend, {"attempts": 0, "ok": 0, "fail": 0, "results": 0})
        h["attempts"] += 1
        h["results"] += n
        h["ok" if status == "ok" else "fail"] += 1


def _get_bytes(url: str, headers: dict | None = None, timeout: int = TIMEOUT):
    """Raw bytes plus the content-type. Text callers go through _get.

    Bytes matter because the latin-1 fallback below will happily decode ANYTHING,
    including a PDF, into a mojibake string that looks like page text to every caller
    downstream. Measured 2026-09-07: 7.8% of all sources across every recorded run were
    PDFs, and each one reached the extractor and the citation auditor as binary.
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), (r.headers.get("content-type") or "")


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _get(url: str, headers: dict | None = None, timeout: int = TIMEOUT) -> str:
    raw, _ = _get_bytes(url, headers, timeout)
    return _decode(raw)


_PDF_ESC = {b"n": b"\n", b"r": b"\n", b"t": b" ", b"b": b"", b"f": b""}


def _pdf_unescape(s: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(s):
        c = s[i:i + 1]
        if c == b"\\" and i + 1 < len(s):
            nxt = s[i + 1:i + 2]
            if nxt in _PDF_ESC:
                out += _PDF_ESC[nxt]; i += 2; continue
            if nxt.isdigit():
                j = i + 1
                while j < len(s) and j < i + 4 and s[j:j + 1].isdigit():
                    j += 1
                try:
                    out.append(int(s[i + 1:j], 8) & 0xFF)
                except ValueError:
                    pass
                i = j; continue
            out += nxt; i += 2; continue
        out += c; i += 1
    return bytes(out)


def pdf_text(raw: bytes, cap: int = 200000) -> str:
    """Text from a PDF, stdlib only. `pypdf` is used instead when it is installed.

    Two things make this work without a dependency. Content streams are almost always
    FlateDecode, and zlib is stdlib. And PDFs position words by KERNING rather than by
    spaces: a TJ array is glyph runs separated by numbers in thousandths of an em, so
    "(Employment)-250(Effects)" is two words and naive concatenation yields
    "EmploymentEffects". Anything below -100 is treated as a word break.

    Research is PDF-heavy - arXiv, working papers, government reports - so a research
    tool that cannot read one is not reading the primary sources it claims to prefer.
    """
    try:
        from pypdf import PdfReader          # optional extra, better on odd encodings
        import io
        pages = PdfReader(io.BytesIO(raw)).pages
        txt = "\n".join((pg.extract_text() or "") for pg in pages)
        if len([w for w in txt.split() if len(w) > 3]) > 40:
            return re.sub(r"\n{3,}", "\n\n", txt)[:cap].strip()
    except Exception:
        pass
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        chunk = m.group(1)
        try:
            chunk = zlib.decompress(chunk)
        except Exception:
            try:
                chunk = zlib.decompressobj().decompress(chunk)   # truncated stream
            except Exception:
                continue
        if b"TJ" not in chunk and b"Tj" not in chunk:
            continue
        for op in re.finditer(rb"\[((?:[^\[\]\\]|\\.)*)\]\s*TJ|\(((?:[^\\()]|\\.)*)\)\s*Tj|(T\*|Td|TD)", chunk):
            if op.group(3):
                out.append("\n"); continue
            if op.group(2) is not None:
                out.append(_pdf_unescape(op.group(2)).decode("latin-1", "ignore")); continue
            parts = []
            for tok in re.finditer(rb"\(((?:[^\\()]|\\.)*)\)|(-?\d+(?:\.\d+)?)", op.group(1)):
                if tok.group(1) is not None:
                    parts.append(_pdf_unescape(tok.group(1)).decode("latin-1", "ignore"))
                else:
                    try:
                        kern = float(tok.group(2))
                    except ValueError:
                        kern = 0.0
                    if kern < -100:
                        parts.append(" ")
            out.append("".join(parts))
        out.append("\n")
        if sum(len(x) for x in out) > cap:
            break
    txt = re.sub(r"[ \t]{2,}", " ", "".join(out))
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


# ── Backends ────────────────────────────────────────────────────────────────
def _ddg(query: str, n: int, lite: bool) -> list[dict]:
    base = "https://lite.duckduckgo.com/lite/" if lite else "https://html.duckduckgo.com/html/"
    body = _get(base + "?q=" + urllib.parse.quote(query))
    # A challenge page parses to nothing but returns HTTP 200/202. Say so rather
    # than silently reporting an empty result set.
    if "anomaly" in body.lower() or "challenge" in body.lower():
        raise RuntimeError("challenged")
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+class="[^"]*result[^"]*a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S):
        href, title = m.group(1), _clean(m.group(2))
        if href.startswith("//duckduckgo.com/l/?uddg="):
            href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
        if href.startswith("http") and href not in seen and title:
            seen.add(href)
            out.append({"url": href, "title": title, "snippet": ""})
        if len(out) >= n:
            break
    if not out:  # lite layout
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', body, re.S):
            href, title = m.group(1), _clean(m.group(2))
            if "duckduckgo.com" in href or not title or href in seen:
                continue
            seen.add(href)
            out.append({"url": href, "title": title, "snippet": ""})
            if len(out) >= n:
                break
    return out


def _mojeek(query: str, n: int) -> list[dict]:
    # Mojeek 403s some hosts/UAs outright. Try the browser UA, then a plain one.
    url = "https://www.mojeek.com/search?q=" + urllib.parse.quote(query)
    try:
        body = _get(url)
    except urllib.error.HTTPError:
        body = _get(url, {"User-Agent": "deepresearch/1.0"})
    out = []
    for m in re.finditer(r'<a class="ob"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S):
        out.append({"url": m.group(1), "title": _clean(m.group(2)), "snippet": ""})
        if len(out) >= n:
            break
    return out


def _wikipedia(query: str, n: int) -> list[dict]:
    api = ("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json"
           "&srlimit=%d&srsearch=%s" % (n, urllib.parse.quote(query)))
    data = json.loads(_get(api))
    return [{"url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(r["title"].replace(" ", "_")),
             "title": r["title"], "snippet": _clean(r.get("snippet", ""))}
            for r in data.get("query", {}).get("search", [])[:n]]


def _openalex(query: str, n: int) -> list[dict]:
    api = ("https://api.openalex.org/works?per-page=%d&search=%s"
           % (n, urllib.parse.quote(query)))
    data = json.loads(_get(api, {"User-Agent": CROSSREF_UA}))
    out = []
    for w in data.get("results", [])[:n]:
        # Prefer an actual PDF/full-text URL. Measured: OpenAlex's
        # `landing_page_url` is usually just the DOI again (unfetchable), while
        # `pdf_url` is frequently a real publisher URL that fetches cleanly.
        loc = (w.get("primary_location") or {})
        cands = [loc.get("pdf_url"), (w.get("best_oa_location") or {}).get("pdf_url"),
                 loc.get("landing_page_url"), w.get("doi"), w.get("id")]
        url = next((u for u in cands if u and "doi.org" not in u), None) or \
              next((u for u in cands if u), None)
        venue = ((loc.get("source") or {}).get("display_name")) or ""
        out.append({"url": url, "title": w.get("display_name") or "",
                    "snippet": "%s %s cited=%s" % (venue, w.get("publication_year") or "",
                                                   w.get("cited_by_count"))})
    return out


def _crossref(query: str, n: int) -> list[dict]:
    api = ("https://api.crossref.org/works?rows=%d&select=DOI,title,container-title,issued,"
           "is-referenced-by-count,abstract&query=%s" % (n, urllib.parse.quote(query)))
    data = json.loads(_get(api, {"User-Agent": CROSSREF_UA}))
    out = []
    for it in data.get("message", {}).get("items", [])[:n]:
        title = (it.get("title") or [""])[0]
        venue = (it.get("container-title") or [""])[0]
        year = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        abstract = _clean(it.get("abstract") or "")
        out.append({"url": "https://doi.org/" + it["DOI"], "title": title,
                    "snippet": (abstract[:300] or "%s %s cited=%s"
                                % (venue, year or "", it.get("is-referenced-by-count")))})
    return out


def _hn(query: str, n: int) -> list[dict]:
    api = "https://hn.algolia.com/api/v1/search?hitsPerPage=%d&query=%s" % (n, urllib.parse.quote(query))
    data = json.loads(_get(api))
    out = []
    for h in data.get("hits", [])[:n]:
        url = h.get("url") or ("https://news.ycombinator.com/item?id=%s" % h.get("objectID"))
        out.append({"url": url, "title": h.get("title") or h.get("story_title") or "",
                    "snippet": "HN points=%s comments=%s" % (h.get("points"), h.get("num_comments"))})
    return out



def _arxiv(query: str, n: int) -> list[dict]:
    """arXiv's own API. Keyless, and the abstract comes back in the response, so
    these results are readable even when the publisher blocks crawlers."""
    api = ("http://export.arxiv.org/api/query?max_results=%d&search_query=all:%s"
           % (n, urllib.parse.quote(query)))
    body = _get(api)
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", body, re.S)[:n]:
        idm = re.search(r"<id>(.*?)</id>", entry, re.S)
        tm = re.search(r"<title>(.*?)</title>", entry, re.S)
        sm = re.search(r"<summary>(.*?)</summary>", entry, re.S)
        if not (idm and tm):
            continue
        # Prefer the abs page over the raw id URL: it is the one that renders.
        url = _clean(idm.group(1)).replace("http://", "https://")
        out.append({"url": url, "title": _clean(tm.group(1)),
                    "snippet": _clean(sm.group(1))[:400] if sm else ""})
    return out


def _europepmc(query: str, n: int) -> list[dict]:
    """Europe PMC. Keyless, biomedical, and crucially it reports whether an open
    full text exists — so we can hand back a URL that actually fetches instead of
    a paywalled landing page."""
    api = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json"
           "&pageSize=%d&query=%s" % (n, urllib.parse.quote(query)))
    data = json.loads(_get(api))
    out = []
    for r in ((data.get("resultList") or {}).get("result") or [])[:n]:
        pmcid, doi = r.get("pmcid"), r.get("doi")
        if pmcid:
            url = "https://europepmc.org/article/PMC/" + pmcid
        elif doi:
            url = "https://doi.org/" + doi          # fetch() routes DOIs via Crossref
        else:
            continue
        out.append({"url": url, "title": r.get("title", ""),
                    "snippet": "%s %s cited=%s%s" % (r.get("journalTitle", ""), r.get("pubYear", ""),
                                                     r.get("citedByCount"),
                                                     " [open full text]" if pmcid else "")})
    return out


def _pubmed(query: str, n: int) -> list[dict]:
    """PubMed E-utilities. Two calls: esearch returns ids, esummary turns them
    into titles. Keyless, and NCBI asks only that you identify yourself."""
    ids = json.loads(_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json"
        "&retmax=%d&term=%s" % (n, urllib.parse.quote(query)),
        {"User-Agent": CROSSREF_UA})).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    summ = json.loads(_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id="
        + ",".join(ids), {"User-Agent": CROSSREF_UA})).get("result", {})
    out = []
    for pid in ids:
        r = summ.get(pid) or {}
        if not r.get("title"):
            continue
        out.append({"url": "https://pubmed.ncbi.nlm.nih.gov/%s/" % pid,
                    "title": r.get("title", ""),
                    "snippet": "%s %s" % (r.get("source", ""), r.get("pubdate", ""))})
    return out


def _searxng(query: str, n: int) -> list[dict]:
    """A SELF-HOSTED SearXNG instance, via DR_SEARXNG_URL.

    This is the only reliable way to get general-web results back when DuckDuckGo
    and Mojeek are challenging your IP (see issue #8). Public instances are not an
    option: every one tested disables `format=json` to prevent exactly this kind of
    automated use, so pointing this at someone else's instance will not work and is
    not polite. Run your own:

        docker run -d -p 8080:8080 searxng/searxng
        # in settings.yml:  search: { formats: [html, json] }
        export DR_SEARXNG_URL=http://localhost:8080
    """
    base = os.environ.get("DR_SEARXNG_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("DR_SEARXNG_URL not set")
    data = json.loads(_get(base + "/search?format=json&q=" + urllib.parse.quote(query)))
    # SearXNG answers 200 with an empty result list when its UPSTREAM engines are all
    # suspended, and it names them in `unresponsive_engines`. Measured 2026-09-06 after
    # one research run: brave "too many requests", google cse "too many requests",
    # duckduckgo "timeout", startpage "CAPTCHA" - 56 successful HTTP calls, 0 results.
    # Without this, health() reports `ok: 56, results: 0` and a reader concludes the web
    # has nothing to say, which is the exact failure self-hosting was meant to end.
    dead = [e[0] for e in (data.get("unresponsive_engines") or []) if e]
    if dead and not (data.get("results") or []):
        raise RuntimeError(
            "SearXNG answered but every upstream engine is unavailable: %s. Your instance "
            "is up and rate-limited, not broken - wait, or enable more engines in "
            "settings.yml (see contrib/searxng)." % ", ".join(sorted(set(dead))[:8]))
    return [{"url": r.get("url", ""), "title": r.get("title", ""),
             "snippet": (r.get("content") or "")[:300]}
            for r in (data.get("results") or [])[:n] if r.get("url")]


_IMPL = {
    "searxng": _searxng,
    "ddg-html": lambda q, n: _ddg(q, n, lite=False),
    "ddg-lite": lambda q, n: _ddg(q, n, lite=True),
    "mojeek": _mojeek,
    "wikipedia": _wikipedia,
    "openalex": _openalex,
    "crossref": _crossref,
    "hn": _hn,
    "arxiv": _arxiv,
    "europepmc": _europepmc,
    "pubmed": _pubmed,
}


def search(query: str, n: int = 8, backends: list[str] | None = None,
           all_backends: bool = False) -> list[dict]:
    """Search across backends until `n` unique results are gathered.

    Walks the chain itself rather than trusting any one engine: when the general
    web backends are challenged they return zero results *and report success*,
    so stopping at the first "successful" backend silently yields nothing.

    Set ``all_backends=True`` to query every backend concurrently instead of
    stopping early — useful as a cross-backend agreement check.
    """
    chain = backends or DEFAULT_CHAIN
    hits: list[dict] = []
    seen: set[str] = set()

    def run(b: str) -> list[dict]:
        try:
            got = [r for r in _IMPL[b](query, n) if r.get("url")]
            _note(b, "ok", len(got))
            return got
        except Exception:
            _note(b, "fail", 0)
            return []

    if all_backends:
        with ThreadPoolExecutor(max_workers=min(7, len(chain))) as ex:
            for f in as_completed({ex.submit(run, b): b for b in chain}):
                for r in f.result():
                    if r["url"] not in seen:
                        seen.add(r["url"])
                        hits.append(r)
        return hits[:n]

    for b in chain:
        for r in run(b):
            if r["url"] not in seen:
                seen.add(r["url"])
                hits.append(r)
        if len(hits) >= n:
            break
    return hits[:n]


# ── Fetching ────────────────────────────────────────────────────────────────
_DOI_URL = re.compile(r"^https?://(?:dx\.)?doi\.org/(10\.\d{4,9}/\S+)$", re.I)
_JATS = re.compile(r"<[^>]+>")


def doi_of(url: str) -> str | None:
    m = _DOI_URL.match((url or "").strip())
    return m.group(1) if m else None


def crossref_record(doi: str) -> tuple[str | None, dict | None]:
    """Full record for a DOI: title, journal, year, authors, abstract.

    This is the workaround for DOIs being unfetchable. Keyless.
    """
    try:
        body = _get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/.-_"),
                    {"User-Agent": CROSSREF_UA}, timeout=30)
        m = json.loads(body).get("message") or {}
    except Exception:
        return None, None
    title = (m.get("title") or [""])[0]
    journal = (m.get("container-title") or [""])[0]
    year = ((m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    authors = ", ".join(" ".join(x for x in (a.get("given"), a.get("family")) if x)
                        for a in (m.get("author") or [])[:8]) or "(authors not listed)"
    abstract = re.sub(r"\s+", " ", _JATS.sub(" ", m.get("abstract") or "")).strip()
    if not (title or abstract):
        return None, None
    text = ("# %s\n\nJournal: %s\nYear: %s\nType: %s\nCited by: %s\nAuthors: %s\nDOI: %s\n\n"
            "## Abstract\n%s"
            % (title or "(untitled)", journal or "(unknown)", year or "?", m.get("type") or "?",
               m.get("is-referenced-by-count", "?"), authors, doi,
               abstract or "(Crossref holds no abstract for this record — metadata only.)"))
    return text, {"journal": journal, "year": year, "title": title, "hasAbstract": bool(abstract)}


def _readable(html_text: str) -> str:
    """Strip a page to readable text. Uses trafilatura when installed, else a
    conservative tag strip. Optional dependency, never required."""
    try:
        import trafilatura  # type: ignore
        got = trafilatura.extract(html_text, include_comments=False, include_tables=True)
        if got and len(got) > 200:
            return got
    except Exception:
        pass
    body = re.sub(r"(?is)<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", " ", html_text)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()


_DOI_IN_URL = re.compile(r"(10\.\d{4,9}/[^\s?#]+)")


def doi_in_url(url: str):
    """A DOI anywhere in the URL, not just a doi.org resolver link.

    Publishers put the DOI in their own paths - pnas.org/doi/10.1073/...,
    dl.acm.org/doi/pdf/10.1145/... - and many of them answer a crawler with 403 behind
    Cloudflare. That is a real gap against a paid scraper with a headless browser and
    residential proxies, and it is not closable with the stdlib. What IS closable: the
    DOI is right there in the URL, so a blocked page can still yield its abstract
    through Crossref instead of yielding nothing.
    """
    m = _DOI_IN_URL.search(urllib.parse.unquote(url or ""))
    if not m:
        return None
    return m.group(1).rstrip(").,;").replace("/pdf", "")


def fetch(url: str, cap: int = 14000) -> tuple[str, dict]:
    """Return ``(text, meta)`` for a URL.

    DOIs are routed to the Crossref API rather than to the resolver, because the
    resolver is not fetchable — see the module docstring.
    """
    doi = doi_of(url)
    if doi:
        text, meta = crossref_record(doi)
        if text:
            return text[:cap], {"via": "crossref-api", **(meta or {})}
    try:
        raw, ctype = _get_bytes(url, timeout=30)
        if raw[:5] == b"%PDF-" or "application/pdf" in ctype.lower():
            text = pdf_text(raw, cap * 8)
            words = len([w for w in text.split() if len(w) > 3 and any(c.isalpha() for c in w)])
            if words < 40:
                # Refuse rather than hand binary downstream. An unreadable PDF is
                # UNREACHABLE, which the citation auditor already understands; passing
                # the bytes on made it look like a page that simply disagreed.
                return "", {"via": "pdf-unreadable",
                            "error": "PDF text extraction yielded %d words; refusing to pass "
                                     "binary as page text" % words}
            return text[:cap], {"via": "pdf", "pdfWords": words}
        return _readable(_decode(raw))[:cap], {"via": "http"}
    except Exception as e:
        # Blocked or broken. If the URL carries a DOI, the abstract is still reachable
        # through Crossref - an abstract is not the full text, and `via` says so, so the
        # citation auditor and the tier rules can both tell the difference.
        doi = doi_in_url(url)
        if doi:
            try:
                text, meta = crossref_record(doi)
                if text and text.strip():
                    return text[:cap], {"via": "crossref-fallback", "abstractOnly": True,
                                        "blockedBy": "%s: %s" % (type(e).__name__, e),
                                        **(meta or {})}
            except Exception:
                pass
        return "", {"via": "failed", "error": "%s: %s" % (type(e).__name__, e)}

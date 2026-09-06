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


def _get(url: str, headers: dict | None = None, timeout: int = TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


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
        return _readable(_get(url, timeout=30))[:cap], {"via": "http"}
    except Exception as e:
        return "", {"via": "failed", "error": "%s: %s" % (type(e).__name__, e)}

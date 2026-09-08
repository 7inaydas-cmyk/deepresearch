"""Source-quality tiering. Deterministic, testable, shared between runtimes.

Rules live in ``contract/tiers.json`` so the Python engine and the Claude Code
workflow grade a domain identically. A resolver graded T1 in one build and T?
in the other is exactly the silent divergence this file exists to prevent.

Why tiering is code and not a prompt: asking a model to rate a source
"primary/secondary/blog" is neither reproducible nor testable — the same URL can
come back graded differently on two runs. Host rules are a pure function.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONTRACT = os.environ.get(
    "DR_TIERS_FILE", os.path.join(_HERE, "..", "contract", "tiers.json"))

with open(os.path.normpath(_CONTRACT)) as _f:
    _C = json.load(_f)

RESOLVERS = set(_C["resolvers"])
RULES = [(t, re.compile(p, re.I)) for t, p in _C["rules"]]
FARM_TELLS = re.compile(_C["farm_tells"], re.I)
RANK = _C["rank"]
CITABLE = set(_C["citable"])

_HOST = re.compile(r"^[a-z][a-z0-9+.\-]*://(?:[^/?#\\]*@)?(?:www\.)?([^/:?#@\\]+)(?::\d+)?", re.I)


def host_of(url: str) -> str:
    m = _HOST.match(str(url or ""))
    return m.group(1).lower() if m else ""


def host_is_ambiguous(url: str) -> bool:
    """Do two competent parsers read two different hosts out of this URL?

    Measured 2026-09-08. `https://nature.com\\@evil.example/x` is read as `nature.com`
    by the host regex and as `evil.example` by urllib, which is the parser the fetcher
    itself uses - so the URL graded T2 (peer-reviewed journal) while the page would be
    served by evil.example. Tiering is the one thing this project grades in code rather
    than by vibes, and T2-versus-T5 decides whether a claim may be cited at all.

    The pre-existing test covered only the harmless ordering, with the untrusted host
    FIRST, where the regex happens to be right. Reversed, it is wrong.

    Checked across normal URLs - ports, `www.`, userinfo, backslashes in the PATH - the
    two parsers agree everywhere. They part company only on a backslash inside the
    authority, which is the attack shape and essentially never legitimate. So the answer
    is not to pick a winner: a URL two parsers disagree about has no single host, and
    grading it on either reading is a guess.
    """
    u = str(url or "")
    try:
        std = (urllib.parse.urlsplit(u).hostname or "").lower()
    except ValueError:
        # Unparseable is not ambiguous. Falling through is safe because the host regex
        # requires a scheme, so anything urllib rejects yields no host here either and
        # lands on the unclassified tier rather than a trusted one.
        return False
    mine = host_of(u)
    if not std or not mine:
        return False
    return mine != std and mine != std[4:] if std.startswith("www.") else mine != std


def tier_of(url: str, title: str = "", text: str = "", resolved_journal: str | None = None):
    """Return ``(tier, why)``.

    ``resolved_journal`` upgrades a resolver once we have actually seen the
    record behind it — a DOI that resolves to a journal article with an abstract
    is peer-reviewed literature, but the bare ``doi.org`` link is not evidence of
    anything.
    """
    if host_is_ambiguous(url):
        # Excluded, not merely downgraded. A URL two parsers read as two different
        # hosts is the shape of a tier-spoof, and the cost of being wrong is a content
        # farm published as a journal.
        return "T5", ("AMBIGUOUS HOST: the host regex and urllib read different hosts out "
                      "of this URL, which is what a tier-spoof looks like. Excluded rather "
                      "than graded on a guess.")
    h = host_of(url)
    if h in RESOLVERS:
        if resolved_journal:
            return "T2", "resolver resolved to %s" % resolved_journal[:60]
        return "T?", "resolver (%s) — provenance unverified, publisher unknown" % h
    for tier, pat in RULES:
        if pat.search(h):
            return tier, "host rule: %s" % h
    blob = (title or "")[:300] + " " + (text or "")[:1500]
    if FARM_TELLS.search(blob):
        return "T5", "content-farm tell in title/lead"
    return "T3", "unclassified host %s — defaulted to practitioner tier" % (h or "?")


def census(sources) -> dict:
    """Tier distribution. An all-T3 run is weak evidence however confident the
    prose sounds; an all-T? run never established provenance at all."""
    out: dict = {}
    for s in sources or []:
        t = (s.get("tier") if isinstance(s, dict) else None) or "?"
        out[t] = out.get(t, 0) + 1
    return out

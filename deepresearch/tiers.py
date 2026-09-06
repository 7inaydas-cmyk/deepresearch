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


def tier_of(url: str, title: str = "", text: str = "", resolved_journal: str | None = None):
    """Return ``(tier, why)``.

    ``resolved_journal`` upgrades a resolver once we have actually seen the
    record behind it — a DOI that resolves to a journal article with an abstract
    is peer-reviewed literature, but the bare ``doi.org`` link is not evidence of
    anything.
    """
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

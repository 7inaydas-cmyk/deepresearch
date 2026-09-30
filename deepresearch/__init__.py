"""deepresearch — multi-agent research that attacks its own output.

Search is keyless. Verification is adversarial. Citations are re-checked blind
against the live page, and the summary is audited for statements that trace to
no verified claim.
"""
import os as _os

# contract/ lives beside the package, not in it, and a plain `pip install .` wheel does
# not ship it: the import then died deep inside on FileNotFoundError for
# contract/providers.json (review 2026-09-27). Say what to do instead.
if not _os.path.isdir(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                                    "contract")):
    raise ImportError("deepresearch needs its checkout's contract/ directory, which a plain "
                      "`pip install .` does not ship. Install editable (pip install -e <checkout>) "
                      "or run `python3 -m deepresearch` from the checkout.")

from .engine import deepresearch, selftest, main  # noqa: F401,E402
from . import search  # noqa: F401

__version__ = "1.19.0"
__all__ = ["deepresearch", "selftest", "search", "main"]

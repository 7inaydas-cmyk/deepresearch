"""deepresearch — multi-agent research that attacks its own output.

Search is keyless. Verification is adversarial. Citations are re-checked blind
against the live page, and the summary is audited for statements that trace to
no verified claim.
"""
from .engine import deepresearch, selftest, main  # noqa: F401
from . import search  # noqa: F401

__version__ = "1.1.0"
__all__ = ["deepresearch", "selftest", "search", "main"]

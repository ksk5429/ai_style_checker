"""Hedging language detector.

Academic writing uses hedging legitimately (epistemic modality), but
AI text over-hedges — stacking modal verbs, using unnecessary qualifiers,
and wrapping every claim in uncertainty markers.

Based on Hyland (1998) hedging taxonomy + CoNLL 2010 shared task patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from checkers.base import CheckerResult, Issue, Severity

# ── Hedging categories (Hyland 1998 taxonomy) ────────────────────────

# Modal verbs (epistemic)
_MODAL_HEDGES = re.compile(
    r"\b(may|might|could|would|should|can)\s+(?:be|have|indicate|suggest|represent|lead|result)",
    re.IGNORECASE,
)

# Approximators
_APPROXIMATORS = re.compile(
    r"\b(approximately|roughly|about|around|nearly|almost|"
    r"somewhat|relatively|fairly|rather|quite|"
    r"to some extent|to a certain degree|more or less)\b",
    re.IGNORECASE,
)

# Epistemic verbs
_EPISTEMIC_VERBS = re.compile(
    r"\b(suggest|indicate|imply|appear|seem|tend|"
    r"assume|propose|hypothesize|speculate|conjecture|"
    r"believe|think|consider|expect|estimate|predict)\b",
    re.IGNORECASE,
)

# Shield expressions
_SHIELDS = re.compile(
    r"\b(it is possible that|it is likely that|it is plausible that|"
    r"it is conceivable that|it is probable that|"
    r"it appears that|it seems that|it would appear that|"
    r"there is evidence that|there is reason to believe)\b",
    re.IGNORECASE,
)

# AI-specific over-hedging (stacked hedges — strongest signal)
_STACKED_HEDGES = re.compile(
    r"\b(may potentially|might possibly|could perhaps|"
    r"would seemingly|appears to possibly|"
    r"seems to potentially|could conceivably|"
    r"may well be|might very well)\b",
    re.IGNORECASE,
)

_CATEGORIES = [
    ("modal_hedge", _MODAL_HEDGES, Severity.INFO),
    ("approximator", _APPROXIMATORS, Severity.INFO),
    ("epistemic_verb", _EPISTEMIC_VERBS, Severity.INFO),
    ("shield", _SHIELDS, Severity.WARNING),
    ("stacked_hedge", _STACKED_HEDGES, Severity.ERROR),
]


@dataclass
class HedgingChecker:
    """Detects excessive hedging language in academic writing."""

    name: str = "hedging"
    description: str = "Flags over-hedging patterns (Hyland taxonomy + AI stacking)"

    # Thresholds (per 1000 words)
    high_density_threshold: float = 25.0  # > 25 hedges per 1k words = excessive
    stacked_hedge_threshold: int = 2      # any stacked hedge is suspicious

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        issues: list[Issue] = []
        category_counts: dict[str, int] = {}
        total_hedges = 0

        for line_num, line in enumerate(lines, 1):
            if line.strip().startswith("#") or line.strip().startswith("!"):
                continue
            for cat_name, pattern, severity in _CATEGORIES:
                for m in pattern.finditer(line):
                    # Only flag as issue if stacked or shield; count others
                    if severity in (Severity.WARNING, Severity.ERROR):
                        issues.append(Issue(
                            checker=self.name,
                            severity=severity,
                            line=line_num,
                            message=f"{cat_name}: '{m.group()}'",
                            match=m.group()[:50],
                            context=line.strip()[:100],
                            suggestion="Remove or simplify the hedge. State findings directly.",
                        ))
                    category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
                    total_hedges += 1

        word_count = len(text.split())
        density = (total_hedges / max(word_count, 1)) * 1000

        if density > self.high_density_threshold:
            issues.insert(0, Issue(
                checker=self.name,
                severity=Severity.WARNING,
                line=0,
                message=f"Overall hedge density ({density:.1f}/1k words) exceeds threshold "
                        f"({self.high_density_threshold}/1k). AI text frequently over-hedges.",
                suggestion="Remove unnecessary hedges. Good academic writing hedges strategically, not habitually.",
            ))

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "total_hedges": total_hedges,
                "hedge_density_per_1k": round(density, 1),
                "by_category": category_counts,
            },
            summary=f"{total_hedges} hedges ({density:.1f}/1k words), "
                    f"{category_counts.get('stacked_hedge', 0)} stacked",
        )

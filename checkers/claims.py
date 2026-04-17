"""Claim and citation integrity checker.

Detects:
- Unsupported quantitative claims (numbers without citations)
- Vague attributions ("studies have shown", "research indicates")
- Potential hallucinated references
- Orphan claims (strong assertions without evidence)

This is the lightweight version — no LLM or NLI model required.
For deep fact-checking, use the optional `--deep` mode with transformers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from checkers.base import CheckerResult, Issue, Severity

# Quantitative claims that need citations
_QUANT_CLAIM = re.compile(
    r"(?:(?:approximately|about|nearly|over|more than|less than|up to|around)\s+)?"
    r"\d+(?:\.\d+)?(?:\s*(?:%|percent|times|fold|orders? of magnitude|kN|MPa|kPa|mm|cm|m|Hz|kg))",
    re.IGNORECASE,
)

# Citation patterns to detect nearby citations
_CITATION_NEARBY = re.compile(
    r"(?:\[@[^\]]+\]|\([A-Z][a-z]+(?:\s+(?:et al\.)?,?\s*\d{4})+\)|"
    r"\\cite[pt]?\{[^}]+\}|\[\d+(?:,\s*\d+)*\])"
)

# Vague attributions (AI hallucination risk)
_VAGUE_ATTRIBUTION = re.compile(
    r"\b(studies have shown|research has demonstrated|"
    r"it has been widely reported|literature suggests|"
    r"many researchers|numerous studies|several authors|"
    r"it is well established|it is well known|"
    r"previous research has indicated|"
    r"the existing body of literature|"
    r"a growing body of evidence|"
    r"scholars have noted)\b",
    re.IGNORECASE,
)

# Strong assertions needing evidence
_STRONG_ASSERTION = re.compile(
    r"\b(always|never|all|none|every|no one|"
    r"undoubtedly|unquestionably|definitively|"
    r"clearly demonstrates|conclusively proves|"
    r"has been conclusively|irrefutably)\b",
    re.IGNORECASE,
)

# Fabricated-sounding references (year in future or very specific patterns)
_SUSPICIOUS_REF = re.compile(
    r"\((?:[A-Z][a-z]+(?:\s+(?:et al\.)?)?(?:,\s*|\s+and\s+))*[A-Z][a-z]+(?:\s+et al\.)?,\s*(20[3-9]\d|2[1-9]\d\d)\)",
)


@dataclass
class ClaimChecker:
    """Detects unsupported claims and vague attributions."""

    name: str = "claims"
    description: str = "Flags unsupported quantitative claims, vague attributions, and suspicious references"

    # How many characters around a number to look for a citation
    citation_window: int = 200

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        issues: list[Issue] = []
        unsupported_claims = 0
        vague_count = 0

        for line_num, line in enumerate(lines, 1):
            if line.strip().startswith("#") or line.strip().startswith("!"):
                continue

            # Check quantitative claims without nearby citations
            for m in _QUANT_CLAIM.finditer(line):
                # Look for citation within window around the match
                start = max(0, m.start() - self.citation_window)
                end = min(len(line), m.end() + self.citation_window)
                window = line[start:end]
                if not _CITATION_NEARBY.search(window):
                    # Skip if it's in a methods/results context describing own work
                    if not re.search(r"\b(was measured|was computed|was calculated|we found|we obtained|our results)\b",
                                     line, re.IGNORECASE):
                        unsupported_claims += 1
                        issues.append(Issue(
                            checker=self.name,
                            severity=Severity.WARNING,
                            line=line_num,
                            message=f"Quantitative claim without citation: '{m.group()}'",
                            match=m.group()[:50],
                            context=line.strip()[:100],
                            suggestion="Add a citation for this quantitative claim, or clarify it as your own finding.",
                        ))

            # Check vague attributions
            for m in _VAGUE_ATTRIBUTION.finditer(line):
                vague_count += 1
                issues.append(Issue(
                    checker=self.name,
                    severity=Severity.ERROR,
                    line=line_num,
                    message=f"Vague attribution: '{m.group()}' — who specifically? Cite them.",
                    match=m.group()[:50],
                    context=line.strip()[:100],
                    suggestion="Replace with specific citation(s). 'Studies have shown' → 'Kim et al. (2024) demonstrated'",
                ))

            # Check strong unsupported assertions
            for m in _STRONG_ASSERTION.finditer(line):
                window_start = max(0, m.start() - 100)
                window_end = min(len(line), m.end() + 100)
                window = line[window_start:window_end]
                if not _CITATION_NEARBY.search(window):
                    issues.append(Issue(
                        checker=self.name,
                        severity=Severity.WARNING,
                        line=line_num,
                        message=f"Strong assertion without evidence: '{m.group()}'",
                        match=m.group()[:50],
                        context=line.strip()[:100],
                        suggestion="Soften the claim or add supporting evidence.",
                    ))

            # Check for future-dated or suspicious references
            for m in _SUSPICIOUS_REF.finditer(line):
                year = int(m.group(1))
                if year > datetime.now().year:
                    issues.append(Issue(
                        checker=self.name,
                        severity=Severity.CRITICAL,
                        line=line_num,
                        message=f"Potentially fabricated reference with future year: {m.group()}",
                        match=m.group()[:50],
                        context=line.strip()[:100],
                        suggestion="Verify this reference exists. Future-dated citations are a hallucination signal.",
                    ))

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "unsupported_quantitative_claims": unsupported_claims,
                "vague_attributions": vague_count,
                "suspicious_references": sum(1 for i in issues if "fabricated" in i.message.lower()),
            },
            summary=f"{unsupported_claims} unsupported claims, {vague_count} vague attributions",
        )

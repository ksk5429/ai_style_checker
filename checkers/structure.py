"""Structural checks for academic manuscripts.

Validates: abstract length, paragraph structure, acronym definitions,
section balance, and citation density.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from checkers.base import CheckerResult, Issue, Severity

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_ACRONYM_DEF = re.compile(r"\(([A-Z]{2,})\)")  # defined as "Full Name (ABC)"
_ACRONYM_USE = re.compile(r"\b([A-Z]{2,})\b")
_CITATION = re.compile(r"(?:\[@[^\]]+\]|\\\[\\cite\{[^}]+\}|\\citep?\{[^}]+\}|\([A-Z][a-z]+(?:\s+(?:et al\.)?,?\s*\d{4})+\))")

# Common abbreviations to exclude from acronym check
_EXCLUDE_ACRONYMS = frozenset({
    "FE", "FEM", "API", "CPU", "GPU", "RAM", "USA", "UK", "EU", "PhD",
    "DOF", "PDE", "ODE", "PDF", "CSV", "SQL", "HTML", "HTTP", "JSON",
    "YAML", "XML", "UN", "IEEE", "ASCE", "ASTM",
})


@dataclass
class StructureChecker:
    """Validates manuscript structure against academic standards."""

    name: str = "structure"
    description: str = "Checks abstract length, paragraphs, acronyms, citations, section balance"

    # Thresholds
    abstract_word_range: tuple[int, int] = (100, 300)
    paragraph_sentence_range: tuple[int, int] = (3, 8)
    min_citation_density: float = 1.0  # citations per 500 words minimum

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        issues: list[Issue] = []

        # ── Abstract detection ───────────────────────────────────
        abstract_text = ""
        in_abstract = False
        for i, line in enumerate(lines):
            if re.match(r"^#+\s*Abstract", line, re.IGNORECASE):
                in_abstract = True
                continue
            if in_abstract:
                if line.strip().startswith("#"):
                    break
                abstract_text += line + " "

        if abstract_text.strip():
            abs_words = len(abstract_text.split())
            abs_sents = len([s for s in _SENT_SPLIT.split(abstract_text.strip()) if len(s.strip()) > 5])
            if abs_words < self.abstract_word_range[0]:
                issues.append(Issue(
                    checker=self.name, severity=Severity.WARNING, line=0,
                    message=f"Abstract too short: {abs_words} words (min {self.abstract_word_range[0]})",
                ))
            elif abs_words > self.abstract_word_range[1]:
                issues.append(Issue(
                    checker=self.name, severity=Severity.WARNING, line=0,
                    message=f"Abstract too long: {abs_words} words (max {self.abstract_word_range[1]})",
                ))

        # ── Paragraph analysis ───────────────────────────────────
        paragraphs: list[tuple[int, str]] = []
        current_para: list[str] = []
        para_start = 0
        for i, line in enumerate(lines):
            if line.strip() == "" or line.strip().startswith("#"):
                if current_para:
                    paragraphs.append((para_start, " ".join(current_para)))
                    current_para = []
            else:
                if not current_para:
                    para_start = i + 1
                current_para.append(line.strip())
        if current_para:
            paragraphs.append((para_start, " ".join(current_para)))

        long_paras = 0
        short_paras = 0
        for line_num, para in paragraphs:
            if para.startswith("!") or para.startswith("|") or para.startswith("$$"):
                continue
            sents = [s for s in _SENT_SPLIT.split(para) if len(s.strip()) > 5]
            if len(sents) > self.paragraph_sentence_range[1]:
                long_paras += 1
                if len(sents) > 10:
                    issues.append(Issue(
                        checker=self.name, severity=Severity.WARNING, line=line_num,
                        message=f"Very long paragraph ({len(sents)} sentences). Consider splitting.",
                        context=para[:80],
                    ))
            elif len(sents) < self.paragraph_sentence_range[0] and len(para.split()) > 10:
                short_paras += 1

        # ── Acronym tracking ────────────────────────────────────
        defined_acronyms: set[str] = set()
        first_use: dict[str, int] = {}

        for i, line in enumerate(lines, 1):
            for m in _ACRONYM_DEF.finditer(line):
                defined_acronyms.add(m.group(1))
            for m in _ACRONYM_USE.finditer(line):
                acr = m.group(1)
                if acr not in first_use and acr not in _EXCLUDE_ACRONYMS:
                    first_use[acr] = i

        undefined = {
            acr: line_num for acr, line_num in first_use.items()
            if acr not in defined_acronyms and acr not in _EXCLUDE_ACRONYMS
        }
        for acr, line_num in sorted(undefined.items(), key=lambda x: x[1]):
            issues.append(Issue(
                checker=self.name, severity=Severity.INFO, line=line_num,
                message=f"Acronym '{acr}' used without definition",
                suggestion=f"Define '{acr}' on first use: 'Full Name ({acr})'",
            ))

        # ── Citation density ─────────────────────────────────────
        citations = _CITATION.findall(text)
        word_count = len(text.split())
        citation_density = (len(citations) / max(word_count, 1)) * 500

        if citation_density < self.min_citation_density and word_count > 500:
            issues.append(Issue(
                checker=self.name, severity=Severity.WARNING, line=0,
                message=f"Low citation density ({len(citations)} citations in {word_count} words = "
                        f"{citation_density:.1f} per 500 words). Academic papers typically have > 1 per 500 words.",
            ))

        # ── Section balance ──────────────────────────────────────
        sections: list[tuple[str, int]] = []
        current_heading = "Preamble"
        current_words = 0
        for line in lines:
            if line.strip().startswith("#"):
                if current_words > 0:
                    sections.append((current_heading, current_words))
                current_heading = line.strip().lstrip("#").strip()
                current_words = 0
            else:
                current_words += len(line.split())
        if current_words > 0:
            sections.append((current_heading, current_words))

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "abstract_words": len(abstract_text.split()) if abstract_text else 0,
                "total_paragraphs": len(paragraphs),
                "long_paragraphs": long_paras,
                "short_paragraphs": short_paras,
                "defined_acronyms": sorted(defined_acronyms),
                "undefined_acronyms": sorted(undefined.keys()),
                "citation_count": len(citations),
                "citation_density_per_500w": round(citation_density, 2),
                "section_word_counts": {h: w for h, w in sections},
            },
            summary=f"{len(paragraphs)} paras, {len(citations)} citations, "
                    f"{len(undefined)} undefined acronyms",
        )

"""Tests for all checker modules.

Run: python -m pytest tests/ -v
Or:  python tests/test_checkers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from checkers.ai_patterns import AIPatternChecker
from checkers.burstiness import BurstinessChecker
from checkers.vocabulary import VocabularyChecker
from checkers.readability import ReadabilityChecker
from checkers.hedging import HedgingChecker
from checkers.passive_voice import PassiveVoiceChecker
from checkers.structure import StructureChecker
from checkers.repetition import RepetitionChecker
from checkers.claims import ClaimChecker
from checkers.base import Severity
from report import compute_ai_score


# ── Fixtures ──────────────────────────────────────────────────────────

AI_TEXT = """
It is worth noting that digital transformation has become a pivotal aspect
of modern business operations. Furthermore, this study delves into the
multifaceted landscape of organizational change. Moreover, we leverage
comprehensive data to underscore the transformative potential of emerging
technologies. Additionally, the findings highlight the critical importance
of strategic alignment. Consequently, it is crucial to acknowledge that
organizations must harness cutting-edge approaches.

Studies have shown that approximately 25% of firms fail to achieve their
digital transformation goals. It is important to note that this represents
a significant challenge. Furthermore, many researchers have explored the
synergy between technology and outcomes. Moreover, it should be mentioned
that our approach could potentially lead to groundbreaking results.

In this context, the methodology leverages a mixed-methods design. The
framework endeavors to elucidate the complex interplay between variables.
To this end, we harness advanced analytical techniques to bolster our
understanding of the phenomena under investigation.

In conclusion, this study has demonstrated that digital transformation
represents a pivotal challenge. The findings highlight the critical
importance of strategic alignment and organizational culture. Furthermore,
it is worth noting that the results underscore the transformative potential.
"""

HUMAN_TEXT = """
We tested 14 model tripods at 100g in dry silica sand with relative densities
of 65% and 85%. Each tripod had three buckets of diameter 4 m and embedment
ratios from 0.5 to 2.0 at prototype scale.

Monotonic capacity normalised by unit weight times diameter cubed collapses
onto a single curve when plotted against embedment ratio. Relative density
had a secondary effect: capacity at 85% exceeded 65% by only 12%, while
doubling L/D from 0.5 to 1.0 increased capacity by 180%.

Cyclic tests at 0.6 times ultimate capacity showed two-phase behaviour. In
the first 200 cycles, stiffness increased as the sand densified. Beyond 200
cycles, stiffness degraded monotonically. Net capacity loss at 1000 cycles
was 18 plus or minus 3%.

At 0.4 times ultimate, no measurable degradation occurred. At 0.8 times
ultimate, rapid degradation led to failure at cycle 340 on average. Pore
pressure measurements confirmed drained conditions throughout.

The beam-on-nonlinear-Winkler-foundation model uses modified API p-y springs
with small-strain initial stiffness from finite element analysis. The model
predicts monotonic capacity within 7% and cyclic degradation within 11%.

Two findings matter. First, embedment ratio governs capacity more than soil
density. This contradicts the API assumption that capacity scales primarily
with soil strength. Second, cyclic degradation at moderate load levels is
gradual and predictable. The logarithmic law holds, which helps lifetime
predictions. But at 0.8 times ultimate, rapid failure suggests a threshold.
"""


# ── Test functions ────────────────────────────────────────────────────

def test_ai_patterns_detects_ai_text():
    checker = AIPatternChecker()
    result = checker.check(AI_TEXT)
    assert len(result.issues) > 15, f"Expected >15 AI patterns, got {len(result.issues)}"
    assert result.metrics["density_per_1k_words"] > 20

    # Should find specific patterns
    messages = [i.message for i in result.issues]
    assert any("filler phrase" in m.lower() for m in messages)
    assert any("transition" in m.lower() for m in messages)


def test_ai_patterns_low_on_human():
    checker = AIPatternChecker()
    result = checker.check(HUMAN_TEXT)
    assert result.metrics["density_per_1k_words"] < 10


def test_burstiness_flags_ai():
    checker = BurstinessChecker()
    result = checker.check(AI_TEXT)
    cv = result.metrics.get("cv_sentence_length")
    assert cv is not None
    assert cv < 0.45, f"AI text should have low CV, got {cv}"


def test_burstiness_human_is_higher():
    checker = BurstinessChecker()
    ai_result = checker.check(AI_TEXT)
    human_result = checker.check(HUMAN_TEXT)
    ai_cv = ai_result.metrics.get("cv_sentence_length", 0)
    human_cv = human_result.metrics.get("cv_sentence_length", 0)
    assert human_cv > ai_cv, f"Human CV ({human_cv}) should exceed AI CV ({ai_cv})"


def test_vocabulary_on_ai():
    checker = VocabularyChecker()
    result = checker.check(AI_TEXT)
    assert result.metrics["ttr"] > 0
    assert result.metrics["hapax_ratio"] > 0


def test_readability_on_both():
    checker = ReadabilityChecker()
    ai_result = checker.check(AI_TEXT)
    human_result = checker.check(HUMAN_TEXT)
    assert ai_result.metrics["flesch_reading_ease"] is not None
    assert human_result.metrics["flesch_reading_ease"] is not None
    assert ai_result.metrics["flesch_kincaid_grade"] > 0


def test_hedging_flags_high_density():
    checker = HedgingChecker()
    result = checker.check("The results could potentially suggest that this may possibly work.")
    # Even a short text with hedges should register non-zero
    assert result.metrics["total_hedges"] > 0
    # High density in a short sentence = flagged
    assert result.metrics["hedge_density_per_1k"] > 25


def test_hedging_low_on_human():
    checker = HedgingChecker()
    result = checker.check(HUMAN_TEXT)
    assert result.metrics["hedge_density_per_1k"] < 15


def test_passive_voice():
    checker = PassiveVoiceChecker()
    passive_text = (
        "The experiment was conducted by the team. "
        "The results were analyzed carefully. "
        "The data was collected over six months. "
        "The samples were prepared in the lab. "
        "The findings were presented at the conference. "
        "The hypothesis was supported by the evidence. "
        "The model was validated against field data. "
        "The parameters were calibrated iteratively. "
        "The boundary conditions were specified clearly. "
        "The mesh was refined until convergence. "
        "The simulation was run on a cluster. "
        "The output was post-processed in Python. "
    )
    result = checker.check(passive_text)
    assert result.metrics["passive_ratio"] > 0.3


def test_structure_abstract():
    checker = StructureChecker()
    text = "# Abstract\n\nShort.\n\n# Introduction\n\nSome intro text here with enough words."
    result = checker.check(text)
    has_short_abstract = any("abstract" in i.message.lower() and "short" in i.message.lower() for i in result.issues)
    assert has_short_abstract


def test_repetition_detects_restatement():
    checker = RepetitionChecker()
    text = (
        "# Introduction\n\n"
        "Digital transformation represents a pivotal challenge for modern organizations. "
        "The findings highlight the critical importance of strategic alignment.\n\n"
        "# Methods\n\nWe used surveys.\n\n"
        "# Conclusions\n\n"
        "Digital transformation represents a pivotal challenge for modern organizations. "
        "The findings highlight the critical importance of strategic alignment."
    )
    result = checker.check(text)
    assert result.metrics["intro_conclusion_similarity"] > 0.1


def test_claims_flags_vague():
    checker = ClaimChecker()
    text = "Studies have shown that 50% of buildings are at risk. Many researchers agree."
    result = checker.check(text)
    has_vague = any("vague" in i.message.lower() for i in result.issues)
    assert has_vague


def test_claims_flags_future_ref():
    checker = ClaimChecker()
    # Use format that matches the regex: (Author, Year) without "et al."
    text = "According to prior work (Smith, 2035), the results are compelling."
    result = checker.check(text)
    has_future = any("fabricated" in i.message.lower() or "future" in i.message.lower() for i in result.issues)
    assert has_future


def test_composite_score_ai_higher():
    checkers = [
        AIPatternChecker(), BurstinessChecker(), VocabularyChecker(),
        ReadabilityChecker(), HedgingChecker(), PassiveVoiceChecker(),
        StructureChecker(), RepetitionChecker(), ClaimChecker(),
    ]
    ai_results = [c.check(AI_TEXT) for c in checkers]
    human_results = [c.check(HUMAN_TEXT) for c in checkers]

    ai_score = compute_ai_score(ai_results)
    human_score = compute_ai_score(human_results)

    assert ai_score["score"] > human_score["score"], (
        f"AI score ({ai_score['score']}) should exceed human score ({human_score['score']})"
    )
    assert ai_score["score"] > 30, f"AI score should be > 30, got {ai_score['score']}"
    assert human_score["score"] < 30, f"Human score should be < 30, got {human_score['score']}"


# ── Runner ────────────────────────────────────────────────────────────

def run_all():
    """Simple test runner without pytest dependency."""
    tests = [
        test_ai_patterns_detects_ai_text,
        test_ai_patterns_low_on_human,
        test_burstiness_flags_ai,
        test_burstiness_human_is_higher,
        test_vocabulary_on_ai,
        test_readability_on_both,
        test_hedging_flags_high_density,
        test_hedging_low_on_human,
        test_passive_voice,
        test_structure_abstract,
        test_repetition_detects_restatement,
        test_claims_flags_vague,
        test_claims_flags_future_ref,
        test_composite_score_ai_higher,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        name = test.__name__
        try:
            test()
            passed += 1
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  FAIL  {name}: {e}")
        except Exception as e:
            failed += 1
            errors.append((name, f"{type(e).__name__}: {e}"))
            print(f"  ERROR {name}: {type(e).__name__}: {e}")

    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests")

    if errors:
        print("\nFailures:")
        for name, msg in errors:
            print(f"  {name}: {msg}")

    return failed == 0


if __name__ == "__main__":
    print("Running ai_style_checker tests...\n")
    success = run_all()
    sys.exit(0 if success else 1)

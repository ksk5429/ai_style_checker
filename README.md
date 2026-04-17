# AI Style Checker

Detect AI-generated writing patterns in academic manuscripts. 12 modular checkers including statistical analysis, personal writing fingerprinting, and sentence-opener diversity scoring.

## What It Detects

| Checker | What It Finds | Signal Strength |
|---------|---------------|-----------------|
| **sentence_openers** | Monotonous sentence starters (The/This/It domination) | Strongest |
| **burstiness** | Uniform sentence lengths (CV < 0.35) | Strong |
| **entropy** | Uniform paragraph information density | Strong |
| **ai_patterns** | Filler phrases, flowery verbs, promotional language | Strong |
| **vocabulary** | Low vocabulary diversity, uniform TTR across sections | Moderate |
| **fingerprint** | Deviation from author's personal writing style | Moderate |
| **hedging** | Stacked hedges, epistemic overload | Moderate |
| **repetition** | Repeated n-grams, conclusion restating introduction | Moderate |
| **claims** | Unsupported quantitative claims, vague attributions | Moderate |
| **structure** | Undefined acronyms, citation density, paragraph length | Structural |
| **passive_voice** | Excessive passive voice ratio (> 40%) | Weak |
| **readability** | Suspiciously uniform readability across sections | Weak |

## Quick Start

```bash
# Check a manuscript
python cli.py manuscript.qmd

# Check with Markdown report output
python cli.py manuscript.qmd -o report.md

# Check all .qmd files in a directory
python cli.py papers/ --glob "*.qmd"

# JSON output for CI integration
python cli.py manuscript.qmd --format json

# Fail CI if AI score exceeds threshold
python cli.py manuscript.qmd --threshold 30

# Run specific checkers only
python cli.py manuscript.qmd --checkers ai_patterns,sentence_openers,burstiness
```

## Personal Writing Fingerprint

Build a stylometric fingerprint from your published papers, then check new manuscripts against it:

```bash
# Build fingerprint from your known papers (one-time)
python -m checkers.fingerprint --build \
    --corpus-dir papers/paper1 papers/paper2 papers/paper3 \
    --output fingerprint.json

# Now every check automatically compares against your fingerprint
python cli.py new_manuscript.qmd
```

The fingerprint uses 14 stylometric features + sentence-transformers embedding centroid (389-dimensional). Paragraphs that deviate from your personal style are flagged -- whether AI-written or just inconsistent.

## AI Likelihood Score

Composite score (0-100) combining weighted signals from all 12 checkers:

| Score | Interpretation |
|-------|----------------|
| 0-20 | Very likely human-written |
| 20-40 | Mostly human, minor AI patterns |
| 40-60 | Mixed signals -- needs human review |
| 60-80 | Strong AI signals detected |
| 80-100 | Very likely AI-generated |

## Real-World Validation

Tested on 7 academic manuscripts (geotechnical engineering, 5,000-13,000 words each):

| Paper | Score | Sentence Openers | Burstiness CV | Verdict |
|-------|-------|-------------------|---------------|---------|
| J3 | 16.2 | 50% noun-phrase | 0.848 | Human-written |
| J2 | 20.6 | 52% noun-phrase | 0.536 | Human-written |
| V1 | 25.8 | 57% noun-phrase | -- | Mostly human |
| Op3 | 25.5 | 59% noun-phrase | 0.680 | Mostly human |
| AI sample | 58.8 | -- | 0.193 | Mixed signals |

Key finding: the strongest discriminator is **sentence-opener diversity** -- AI text starts 55%+ of sentences with "The/This/It", while human academic writing typically stays at 40-50%.

## Architecture

```
ai_style_checker/
├── cli.py                      # CLI entry point
├── report.py                   # Report generator (console + Markdown + JSON)
├── fingerprint.json            # Author's personal writing fingerprint
├── checkers/                   # 12 modular detectors
│   ├── base.py                 # Issue/CheckerResult dataclasses, Checker protocol
│   ├── sentence_openers.py     # POS-tag opener classification + Shannon entropy
│   ├── entropy.py              # Paragraph-level information density variance
│   ├── fingerprint.py          # Personal writing style comparison
│   ├── ai_patterns.py          # 15+ regex pattern banks (capped density)
│   ├── burstiness.py           # Sentence-length CV analysis
│   ├── vocabulary.py           # TTR, hapax ratio, section uniformity
│   ├── readability.py          # Flesch, Kincaid, Fog, Coleman-Liau
│   ├── hedging.py              # Hyland taxonomy + AI stacking patterns
│   ├── passive_voice.py        # Passive/active ratio + adjectival exclusion
│   ├── structure.py            # Acronyms, citations (numeric + author-year)
│   ├── repetition.py           # N-gram repetition, intro/conclusion similarity
│   └── claims.py               # Unsupported claims, vague attributions
├── tests/
│   └── test_checkers.py        # 14 tests
├── sample/
│   ├── ai_generated.md         # AI-written sample (scores ~59)
│   └── human_written.md        # Human-written sample (scores ~10)
└── pyproject.toml
```

## Key Design Decisions

1. **Zero core dependencies** -- base checkers run on Python 3.10+ stdlib only. Optional `sentence-transformers` for fingerprinting.

2. **12 modular checkers** -- each is independent. Add your own by implementing the `Checker` protocol (`check(text, lines=) -> CheckerResult`).

3. **Capped pattern density** -- each pattern type is capped at 5 occurrences for scoring, preventing technical terms (em-dashes, domain keywords) from dominating the score.

4. **Personal fingerprinting** -- not just "is this AI?" but "does this sound like YOU?" Built from your own corpus.

5. **CI-friendly** -- `--threshold` returns exit code 1 if score exceeds limit. `--format json` for programmatic consumption.

## Roadmap

- [x] Sentence-opener diversity (POS classification, Shannon entropy)
- [x] Paragraph entropy variance
- [x] Personal writing fingerprint (sentence-transformers)
- [x] A/B scoring integration with sentence_evolver
- [ ] GPT-2 perplexity scoring for deep detection
- [ ] Binoculars integration (zero-shot, model-based)
- [ ] DOCX input support (via python-docx)
- [ ] GitHub Actions workflow for automated checking

## Ecosystem

Part of the academic writing toolkit:

| Repo | Purpose |
|------|---------|
| **ai_style_checker** | Detect AI writing patterns (this repo) |
| [sentence_evolver](https://github.com/ksk5429/sentence_evolver) | Multi-agent sentence rewriting with 10 writer personas |
| [publishing_engine](https://github.com/ksk5429/publishing_engine) | .qmd to publication DOCX (7 document types) |
| [manuscript_pipeline](https://github.com/ksk5429/manuscript_pipeline) | Orchestrator chaining all engines |
| [pdf_search_engine](https://github.com/ksk5429/pdf_search_engine) | Multi-source academic PDF search and download |

## License

Apache 2.0

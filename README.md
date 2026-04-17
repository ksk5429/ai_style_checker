# AI Style Checker

Detect AI-generated writing patterns in academic manuscripts. Zero external dependencies — runs on pure Python stdlib.

## What It Detects

| Checker | What It Finds |
|---------|---------------|
| **ai_patterns** | ChatGPT/Claude fingerprints: filler phrases, flowery verbs, promotional language |
| **burstiness** | Uniform sentence lengths (AI signal: CV < 0.35 vs human > 0.5) |
| **vocabulary** | Low vocabulary diversity, uniform TTR across sections |
| **readability** | Suspiciously uniform readability across sections |
| **hedging** | Over-hedging, stacked hedges ("could potentially"), epistemic overload |
| **passive_voice** | Excessive passive voice ratio (> 40%) |
| **structure** | Abstract length, paragraph structure, undefined acronyms, citation density |
| **repetition** | Repeated n-grams, conclusion restating introduction, transition overuse |
| **claims** | Unsupported quantitative claims, vague attributions, future-dated references |

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
python cli.py manuscript.qmd --threshold 40

# Run specific checkers only
python cli.py manuscript.qmd --checkers ai_patterns,burstiness
```

## AI Likelihood Score

The composite score (0-100) combines signals from all checkers:

| Score | Interpretation |
|-------|----------------|
| 0-20 | Very likely human-written |
| 20-40 | Mostly human, minor AI patterns |
| 40-60 | Mixed signals — needs human review |
| 60-80 | Strong AI signals detected |
| 80-100 | Very likely AI-generated |

## Example Output

```
======================================================================
  AI STYLE CHECKER REPORT -- manuscript.qmd
======================================================================

  AI Likelihood Score: 58.8/100 — Mixed signals -- needs human review

  Checker summaries:
    ai_patterns    71 AI patterns flagged (102.7 per 1k words)
    burstiness     CV=0.193 (AI-like), 43 sentences, mean 15 words
    vocabulary     TTR=0.559, hapax=0.635
    hedging        5 hedges (7.2/1k words), 0 stacked

  Top issues:
    [ERROR] L5:  Zero-information filler phrase
                 match: 'It is worth noting that'
    [ERROR] L9:  Promotional / hype language
                 match: 'cutting-edge'
    [ERROR] L11: Vague attribution
                 match: 'studies have shown'
```

## Architecture

```
ai_style_checker/
├── cli.py                  # CLI entry point
├── report.py               # Report generator (console + Markdown + JSON)
├── checkers/               # Modular detection engine
│   ├── base.py             # Issue/CheckerResult dataclasses, Checker protocol
│   ├── ai_patterns.py      # 15+ regex pattern banks
│   ├── burstiness.py       # Sentence-length CV analysis
│   ├── vocabulary.py       # TTR, hapax ratio, section uniformity
│   ├── readability.py      # Flesch, Kincaid, Fog, Coleman-Liau
│   ├── hedging.py          # Hyland taxonomy + AI stacking patterns
│   ├── passive_voice.py    # Passive/active ratio + section analysis
│   ├── structure.py        # Abstract, paragraphs, acronyms, citations
│   ├── repetition.py       # N-gram repetition, intro/conclusion similarity
│   └── claims.py           # Unsupported claims, vague attributions
├── tests/
│   └── test_checkers.py    # 14 tests covering all checkers
├── sample/
│   ├── ai_generated.md     # AI-written text (scores ~59)
│   └── human_written.md    # Human-written text (scores ~10)
├── pyproject.toml
└── README.md
```

## Key Design Decisions

1. **Zero dependencies** — runs on Python 3.10+ stdlib only. No spaCy, no transformers, no NLTK required for base functionality. Optional `[nlp]` and `[deep]` extras for advanced features.

2. **Modular checkers** — each checker is independent. Add your own by implementing the `Checker` protocol (just a `check(text, lines=) -> CheckerResult` method).

3. **Composite scoring** — the AI likelihood score weights different signals. Burstiness and AI patterns are strongest signals; vocabulary and readability are modifiers.

4. **CI-friendly** — `--threshold` flag returns exit code 1 if score exceeds limit. `--format json` for programmatic consumption.

## Running Tests

```bash
python tests/test_checkers.py

# Or with pytest
pip install pytest
pytest tests/ -v
```

## Roadmap

- [ ] Optional spaCy-based passive voice detection (higher accuracy)
- [ ] GPT-2 perplexity scoring for deep detection
- [ ] Binoculars integration (zero-shot, model-based detection)
- [ ] Citation-claim alignment via NLI models
- [ ] DOCX input support (via python-docx)
- [ ] GitHub Actions workflow for automated checking
- [ ] Integration with [publishing_engine](https://github.com/ksk5429/publishing_engine) as pre-render validation

## Related Projects

- [publishing_engine](https://github.com/ksk5429/publishing_engine) — DOCX rendering pipeline for journal submissions
- [sentence_evolver](https://github.com/ksk5429/sentence_evolver) — Multi-agent sentence rewriting using writer personas

## License

Apache 2.0

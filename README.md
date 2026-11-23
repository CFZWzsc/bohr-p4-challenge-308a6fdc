# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-308a6fdc` (track: `academic-writing`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable entry point and all supporting scripts. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `source-faithful-manuscript-assembly`
- Summary: Assemble an editable multi-section manuscript draft strictly from supplied research materials, tagging every sentence with a traceable source locator instead of inventing facts. Use when a task asks to turn lab notes, results and references into a sectioned academic draft with verifiable provenance.

## Contents

| File |
|------|
| `SKILL.md` |
| `scripts/run_skill.py` |
| `scripts/skill_core.py` |
| `README.md` |

## How to run

```bash
python scripts/run_skill.py --case /input/case.json --output /app/output/result.json
```

The entry point is `SKILL.md`; input/output contracts, error handling and a minimal
usage example are documented there.

## Notes

- Pure Python standard library; no network access required.
- The result JSON keeps the input case id, the main results, per-item evidence,
  a run status and an uncertainty section.

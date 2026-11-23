# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-308a6fdc` (track: `academic-writing`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable entry point and all supporting scripts. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `source-faithful-manuscript-assembly`
- Summary: Use when a case supplies lab notes, results and references and asks for a sectioned academic draft with verifiable provenance; assembles an editable Markdown manuscript from supplied sentences, tags every sentence with a traceable source locator, marks gaps for human confirmation, and writes /app/output/result.json preserving case_id and every output_contract field. Deterministic standard library only; no network.

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

# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-308a6fdc` (track: `academic-writing`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable pipeline and all supporting documents. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `bohr-writing-01`
- Summary: 当需要写作科研材料并产出可复核的结构化结果时使用。 本题范围：写作01｜学术论文写作。 题目家族：学术论文写作。 任务要求：依据材料写出摘要、引言、方法、结果、讨论、结论六节齐全的论文全文，成段叙述而非要点罗列，数字与引用与来源一致。 产出 result.json，其中包含运行时 output_contract 要求的全部字段，每条结论附带原文证据（段落定位 + 短引），无法从材料判断的部分如实写入 uncertainty 而非编造。

## Contents

| File |
|------|
| `LICENSE` |
| `README.md` |
| `SKILL.md` |
| `assets/contract-aliases.json` |
| `assets/policy.json` |
| `assets/result-schema.md` |
| `environment/resources.yaml` |
| `environment/runtime.txt` |
| `examples/demo-case/agent_judgement.example.json` |
| `examples/demo-case/case.json` |
| `examples/demo-case/material.md` |
| `examples/demo-case/task.md` |
| `examples/quickstart.md` |
| `references/artifact-pipeline.md` |
| `references/contract-handling.md` |
| `references/evidence-discipline.md` |
| `references/failure-modes.md` |
| `references/two-phase-workflow.md` |
| `scripts/artifacts.py` |
| `scripts/pptxgen.py` |
| `scripts/sk_base.py` |
| `scripts/sk_entry.py` |
| `scripts/sk_selftest.py` |
| `scripts/skill_profile.json` |
| `scripts/specialize.py` |
| `scripts/taskgen.py` |
| `scripts/topic.py` |
| `README.md` |

## How to run

```bash
python scripts/sk_entry.py --input /input --work /app/work --out /app/output
```

A single deterministic pass reads `/input`, computes the deliverable and writes a
contract-complete `/app/output/result.json` plus the human-readable review files
described in `SKILL.md`. The same input always produces byte-identical output; no
network access is used, and fields the materials cannot support are reported
explicitly instead of being left empty.

## Notes

- Pure Python standard library; no network access required.
- Every claim is anchored to paragraph-level evidence; unknown items are reported
  in `uncertainty` instead of being fabricated.

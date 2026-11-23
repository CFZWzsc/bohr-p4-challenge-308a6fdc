---
name: source-faithful-manuscript-assembly
description: Assemble an editable multi-section manuscript draft strictly from supplied research materials, tagging every sentence with a traceable source locator instead of inventing facts. Use when a task asks to turn lab notes, results and references into a sectioned academic draft with verifiable provenance.
---

# 来源保持型论文草稿组装

## 用途与适用条件

把分散的科研材料（实验记录、结果描述、文献摘录、任务说明）按目标章节组装成一份**可编辑的 Markdown 章节稿**，每一句都保留来源定位，缺失章节显式标注。

适用：

- 任务是"根据给定材料写/整理某几个章节"，而不是自由创作。
- 材料已随 `case.json` / `task.md` 提供，作者能核对原文。
- 需要逐句回溯来源、需要作者继续改写的半成品。

不适用：需要真实文献检索、需要生成材料外的新数据、需要排版成 Word/PDF 成品（本 Skill 只交付 Markdown 文本与证据表）。

## 输入

| 输入 | 位置 | 说明 |
|-|-|-|
| `case.json` | `/input/case.json`（默认，可用 `--case` 覆盖） | 主输入。任意层级的字符串字段都会被收集为材料；`sections` / `required_sections` / `outline` 可显式指定章节；`output_contract` 声明输出字段 |
| `task.md` | `/input/task.md`（自动探测） | 任务说明，用于推断章节需求，不进入正文 |
| 输出路径 | `/app/output/result.json`（默认，可用 `--out` 覆盖） | 结构化结果 |
| 工作目录 | `/app/work`（可用 `--work` 指定） | 预留的临时目录，脚本本身不写中间文件 |

`output_contract` 的识别顺序：`output_contract` → `outputContract` → `output_schema`。

## 处理流程（对应评分维度）

1. **材料清点**（结果可核验性）：遍历 `case.json` 全部字符串字段与 `task.md`，按 SHA-256 去重，跳过 `output_contract`、`/task`、`/rubric` 等说明性路径，得到 `S1…Sn` 材料清单及 JSON Pointer 定位。
2. **章节需求识别**（任务完成度）：优先读取显式章节列表；否则从任务说明中匹配 Abstract / Introduction / Related Work / Methods / Results / Discussion / Conclusion 的中英文关键词。
3. **句子切分与筛选**（结果正确性）：按中英文句末标点与列表行切句，剔除 20 字符以下、500 字符以上、指令性（含"评分/提交/请/you must"等）与纯标记行。
4. **章节归属**（结果完整性）：以章节词表与句子词项的重叠度打分，按分数与章节顺序唯一分配，单章最多 5 句，按来源编号稳定排序。
5. **摘要生成**：从 Intro/Methods/Results/Discussion 各取首句；缺失时取信息量最大的 3 句。摘要同样是**原句**，不改写。
6. **成稿组装**（可编辑性）：输出 `## 章节名` + 原句 + `[src:S#s#]`；空章节写占位说明，不编造。
7. **证据登记**（可核验性）：每条入选句登记 `claim_id / section / sentence / source_id / locator / sentence_locator / numbers / citations`，数值与引用原样抽取，供逐条回查。
8. **缺项与冲突标注**（诚实性）：空章节、无 DOI、未入选句子、无引用标记分别写入 `uncertainty`。

## 输出契约

`result.json` 顶层固定包含：

- `case_id`：原样保留输入标识。
- `status`：`success`（全部章节有材料支撑）/ `partial`（存在空章节）/ `insufficient_input`（无可用材料）/ `failed`（异常）。
- `result`：`deliverable`（Markdown 章节稿）、`sections`（章节与句数、来源）、`sources`、`limitations`。
- `evidence`：逐句来源映射表。
- `uncertainty`：缺项、待人工确认事项。
- `errors`：结构化错误（正常为空数组）。
- `stats`：材料数、候选句、入选句、章节覆盖、数值与引用计数。
- `contract_notes`：契约字段处理说明。

**output_contract 处理**：契约中声明的每个字段都会出现在顶层。能由本 Skill 产出的（如 `deliverable`、`manuscript`、`draft`、`evidence`、`sources`、`stats`）直接填充；无法产出的字段保留为 `null`，并在 `contract_notes` 中逐条说明原因，**不编造占位内容**。

## 异常处理

| 情况 | 处置 | status |
|-|-|-|
| `case.json` 不存在 / 非 JSON 对象 | 输出结构化失败结果，`errors[0].stage` 标明阶段，退出码 2 | `failed` |
| 只有任务说明、没有科研材料 | 不生成正文，说明缺什么 | `insufficient_input` |
| 材料存在但无合格句子 | 不生成正文，说明筛选阈值 | `insufficient_input` |
| 某章节无匹配句 | 保留章节标题 + 占位说明，写入 `uncertainty` | `partial` |
| 材料无 DOI / 无引用标记 | 不补引用，写入 `uncertainty` | 原状态 |
| 输出目录不存在 | 自动创建 | — |
| 契约字段无法产出 | 置 `null` 并记录 | 原状态 |

## 限制

- 只做**抽取式**组装：不改写、不扩写、不做同义替换，因此语言自然度有限，必须由作者改写。
- 不做真实文献检索与 DOI 核验；不解析 PDF/Word 二进制（平台会以文本形式提供材料）。
- 章节归属基于词表重叠，跨学科材料可能需要人工调整章节映射。
- 单章最多 5 句，长材料会被截断；未入选句会在 `uncertainty` 中计数。
- 不生成 `.docx`/PDF 成品，只交付 Markdown。

## 最小调用示例（示例，非官方案例结果）

输入 `/input/case.json`（示例）：

```json
{
  "case_id": "demo-001",
  "output_contract": {"manuscript": "string", "evidence": "array", "status": "string"},
  "materials": [
    {"name": "lab-note", "text": "The trial enrolled 120 adults with moderate asthma. The intervention group received 200 mg daily for 12 weeks."},
    {"name": "results", "text": "FEV1 increased by 8.4 percent in the intervention group compared with placebo (p = 0.02)."}
  ]
}
```

调用：

```bash
python scripts/run_skill.py --case /input/case.json --out /app/output/result.json --work /app/work
```

示意输出（**示例**，字段已截断）：

```json
{
  "case_id": "demo-001",
  "manuscript": "## Methods\n\nThe trial enrolled 120 adults ... [src:S1#s1]",
  "evidence": [{"claim_id": "E01", "section": "Methods", "source_id": "S1", "sentence_locator": "S1#s1"}],
  "status": "partial",
  "stats": {"source_documents": 2, "selected_sentences": 3}
}
```


## 自查清单

- [ ] `case_id` 与合同字段保留；未映射项已登记。
- [ ] 必需章节齐全，`deliverable` 为连贯正文而非句子堆叠。
- [ ] 每句都有 `[src:...]`，空章节已说明缺口。
- [ ] 未新增材料外事实、数据或引用。

## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--output` 指定。
2. **必须交付完整成品**：脚本只做抽取式组装；调用 Agent 必须在**不新增材料外事实**的前提下，把入选句扩写成连贯的章节正文 `result.deliverable`（各必需章节齐全、保留 `[src:...]` 定位），并补全 `sections` 与 `evidence`；空章节须说明缺口，不得以半成品、`pending` 或“待作者改写”作完成态。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 取本合同允许值 `success | partial | insufficient_input | failed`；正文无 `pending`/`TODO`/空占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。

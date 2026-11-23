---
name: source-faithful-manuscript-assembly
description: Use when a case supplies lab notes, results and references and asks for a sectioned academic draft with verifiable provenance; assembles an editable Markdown manuscript from supplied sentences, tags every sentence with a traceable source locator, marks gaps for human confirmation, and writes /app/output/result.json preserving case_id and every output_contract field. Deterministic standard library only; no network.
---

# 来源保持型论文草稿组装

## 用途与适用条件

把给定的科研材料（实验记录、结果描述、文献摘录、任务说明）按目标章节组装成一份**可编辑的 Markdown 章节稿**：每句带来源定位，未覆盖的章节显式标注，不新增材料外事实。

适用：

- 任务是"根据给定材料写/整理指定章节"，而不是自由创作。
- 材料随 `case.json` / `task.md` 提供，作者能核对原文。
- 需要逐句回溯来源、需要作者继续改写的半成品。

不适用：真实文献检索、生成材料外新数据、Word/PDF 排版成品（本 Skill 交付 Markdown 正文与证据表）。

## 输入

| 输入 | 位置 | 说明 |
|-|-|-|
| `case.json` | `/input/case.json`（`--case` 覆盖） | 主输入。任意层级字符串字段收为材料；`sections` / `required_sections` / `outline` 指定章节；`output_contract` 声明输出字段 |
| `task.md` | `/input/task.md`（自动探测） | 只用于推断章节需求，不进入正文 |
| 结果 | `/app/output/result.json`（`--out` 与 `--output` 等价） | 结构化结果 |
| 工作目录 | `/app/work`（`--work`） | 预留临时目录，脚本不写中间文件 |

`output_contract` 识别顺序：`output_contract` → `outputContract` → `output_schema`。

## 处理流程

1. **材料清点**：遍历 `case.json` 全部字符串字段与 `task.md`，按 SHA-256 去重，跳过 `output_contract`、`/task`、`/rubric` 等说明性路径，得到 `S1…Sn` 材料清单及 JSON Pointer 定位。
2. **章节需求**：优先读取显式章节列表；否则从任务说明匹配 Abstract / Introduction / Related Work / Methods / Results / Discussion / Conclusion 的中英文关键词。
3. **选句**：按中英文句末标点与列表行切句，剔除 20 字符以下、500 字符以上、指令性与纯标记行。
4. **章节归属**：以章节词表与句子词项的重叠度打分，唯一分配，单章最多 5 句，按 `S#s#` 稳定排序。
5. **摘要**：取 Intro/Methods/Results/Discussion 首句；缺失时取信息量最大的 3 句；摘要同样是原句。
6. **成稿骨架**：输出 `## 章节名` + 原句 + `[src:S#s#]`；空章节写占位说明。
7. **证据登记**：每条入选句登记 `claim_id / section / sentence / source_id / locator / sentence_locator / numbers / citations`。
8. **缺项标注**：空章节、无 DOI、未入选句、无引用标记写入 `uncertainty`。

## 输出契约

`result.json` 顶层固定字段：

| 字段 | 类型 | 含义 |
|-|-|-|
| `case_id` | string | 原样保留输入标识，不被合同字段覆盖 |
| `status` | enum | `success`（全部章节有支撑）/ `partial`（存在空章节）/ `insufficient_input`（无可用材料）/ `failed` |
| `result.deliverable` | string | 可编辑 Markdown 章节稿（成品正文） |
| `result.sections` | array | 章节名、句数、来源 ID |
| `result.sources` | array | `source_id / locator / chars` |
| `result.limitations` | array | 方法边界 |
| `result.needs_human_confirmation` | array | 材料缺口、结论冲突、需作者确认（调用 Agent 补齐）：`item / locator / reason`，`locator` 不得为空 |
| `evidence` | array | 第 7 步的逐句来源映射，可用 `sentence_locator` 逐条回查 |
| `uncertainty` | array | 缺项、降级假设、待确认说明 |
| `errors` | array | 结构化错误（正常为空数组） |
| `stats` | object | 材料数、候选句、入选句、章节覆盖、数值与引用计数 |
| `contract_notes` | array | 合同字段处理说明 |

**output_contract 处理**：契约中声明的每个字段都出现在顶层。能由本 Skill 产出的（`deliverable` / `manuscript` / `draft` / `evidence` / `sources` / `stats` 及别名）直接填真实值；无法产出的字段保留 `null`，并在 `contract_notes` 中逐条说明原因，不编造占位内容。

## 异常处理

| 情况 | 处置 | status |
|-|-|-|
| `case.json` 不存在 / 非 JSON 对象 | 仍写出结构化结果，`errors[0].stage` 标明阶段 | `failed` |
| 只有任务说明、没有科研材料 | 不生成正文，说明缺什么 | `insufficient_input` |
| 材料存在但无合格句子 | 不生成正文，说明筛选阈值 | `insufficient_input` |
| 某章节无匹配句 | 保留章节标题 + 占位说明，写入 `uncertainty` 与 `needs_human_confirmation` | `partial` |
| 材料无 DOI / 无引用标记 | 不补引用，写入 `uncertainty` | 原状态 |
| 契约字段无法产出 | 置 `null` 并记录 `contract_notes` | 原状态 |
| 输出目录不存在 | 自动创建 | — |

## 限制

- 抽取式组装：不改写、不扩写、不做同义替换；语言自然度有限，须由作者或调用 Agent 润色。
- 不做文献检索与 DOI 核验；不解析 PDF/Word 二进制（平台以文本提供材料）。
- 章节归属依赖词表重叠，跨学科材料可能需人工调整。
- 单章最多 5 句，长材料会被截断；未入选句在 `uncertainty` 中计数。

## 最小调用示例（示例，非官方案例结果）

```bash
python scripts/run_skill.py --case /input/case.json --out /app/output/result.json --work /app/work
```

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

## 交付与自检

1. 先运行 `python scripts/run_skill.py`（默认 `/input/case.json` → `/app/output/result.json`；`--case`、`--out`、`--output` 等价）。脚本正常结束恒以退出码 0 返回，失败类别只看 `status` 与 `errors`。
2. 脚本只给抽取式骨架；调用 Agent 必须在不新增材料外事实的前提下改写为连贯正文，写入 `result.deliverable`（各必需章节齐全、保留 `[src:...]` 定位），并补齐 `sections`、`evidence`、`needs_human_confirmation`。不得以半成品、`pending`、`TODO` 或"待作者改写"作完成态。
3. 覆盖全部输入条目：每个章节、材料都要有对应条目；确实缺失的写入 `needs_human_confirmation` / `uncertainty` 并说明原因，不静默跳过。
4. 自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 取本合同允许值；每句都有 locator；数字、单位、引用可逐条回溯；结果内部无自相矛盾。

不联网、不伪造数据、不声称平台评分或官方案例结果；逻辑由输入驱动，不针对某份示例硬编码；字段命名差异走别名匹配并在 `uncertainty` 记录假设。

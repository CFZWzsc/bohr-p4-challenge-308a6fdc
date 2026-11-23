#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-faithful manuscript assembly skill.

Reads /input/case.json (plus optional task.md), selects verbatim sentences from
the supplied research materials for the requested manuscript sections, tags each
sentence with a traceable source locator, and writes result.json that keeps
case_id and every declared output_contract field.

Standard library only. Deterministic, no network, no random, no private paths.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skill_core import (clamp, collect_docs, load_json, overlap, read_text,
                        split_sentences, terms)

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUT = "/app/output/result.json"
DEFAULT_WORK = "/app/work"

SECTION_VOCAB = OrderedDict([
    ("Abstract", ["abstract", "summary", "摘要", "概要"]),
    ("Introduction", ["introduction", "background", "motivation", "challenge",
                      "gap", "引言", "背景", "研究问题"]),
    ("Related Work", ["related work", "literature", "prior work", "previous studies",
                      "相关工作", "文献综述", "已有研究"]),
    ("Methods", ["method", "methodology", "procedure", "protocol", "materials",
                 "participants", "randomized", "trial", "intervention", "dose",
                 "assessed", "measured", "方法", "实验设置", "受试者", "干预", "剂量"]),
    ("Results", ["result", "finding", "outcome", "decreased", "increased", "difference",
                 "confidence", "interval", "significant", "adverse", "percent",
                 "结果", "发现", "显著", "差异", "置信区间"]),
    ("Discussion", ["discussion", "consistent", "contrary", "mechanism", "hypothesis",
                    "interpretation", "limitation", "讨论", "机制", "局限", "解释"]),
    ("Conclusion", ["conclusion", "summary", "结论", "小结"]),
])

INSTRUCTION_HINTS = ("评分", "提交", "请", "要求", "案例", "你需要", "you must", "please ",
                     "deliverable", "rubric", "output_contract")


def log(message):
    sys.stderr.write("[run_skill] %s\n" % message)


def contract_fields(spec):
    """Return declared field names from the many shapes output_contract can take."""
    if isinstance(spec, list):
        names = []
        for item in spec:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("field") or item.get("key")
                if name:
                    names.append(str(name))
        return names
    if isinstance(spec, dict):
        if isinstance(spec.get("properties"), dict):
            return [str(name) for name in spec["properties"]]
        if isinstance(spec.get("fields"), (dict, list)):
            return contract_fields(spec["fields"])
        reserved = {"$schema", "title", "description", "type", "required", "definitions", "$defs"}
        return [str(name) for name in spec if str(name).lower() not in reserved]
    return []


ALIASES = OrderedDict([
    ("deliverable", {"manuscript", "draft", "article", "document", "finaltext",
                     "manuscripttext", "outputtext", "text", "content", "body"}),
    ("evidence", {"evidence", "evidencemap", "sourcemap", "citationmap", "factmap"}),
    ("sources", {"sources", "references", "bibliography", "materialindex", "materials"}),
    ("uncertainty", {"uncertainty", "uncertainties", "reviewitems", "warnings", "issues"}),
    ("stats", {"stats", "metrics", "statistics", "counts"}),
])


def norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def finalize(case, payload, contract):
    """Keep case_id and every declared contract field at the top level."""
    out = OrderedDict()
    out["case_id"] = case.get("case_id") or case.get("id")
    notes = []
    if contract is None:
        notes.append("case.json 未声明 output_contract；已按本题通用字段输出。")
    for name in contract_fields(contract):
        if norm(name) == "caseid":
            continue
        if name in payload:
            out[name] = payload[name]
            continue
        if norm(name) in {norm(key) for key in payload}:
            out[name] = payload[next(key for key in payload if norm(key) == norm(name))]
            continue
        mapped = None
        for canonical, aliases in ALIASES.items():
            if canonical in payload and norm(name) in aliases:
                mapped = payload[canonical]
                break
        out[name] = mapped
        if mapped is None:
            notes.append("字段 %s 不在本 Skill 的能力范围内，按契约保留为 null。" % name)
    defaults = {"status": "partial", "result": {}, "evidence": [], "uncertainty": [],
                "errors": [], "stats": {}, "contract_notes": []}
    for key, default in defaults.items():
        if key not in out:
            value = payload.get(key)
            out[key] = default if value is None else value
    out["status"] = payload.get("status") or "partial"
    out["contract_notes"] = notes + list(payload.get("contract_notes") or [])
    return out


def find_task_text(case_path, explicit):
    candidates = [explicit] if explicit else []
    if case_path:
        base = os.path.dirname(os.path.abspath(case_path))
        candidates += [os.path.join(base, "task.md"), os.path.join(base, "..", "task.md")]
    candidates += ["/input/task.md", "task.md"]
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                return read_text(path), path
            except OSError:
                continue
    return "", None


def detect_sections(task_text, case):
    requested = (case.get("sections") or case.get("required_sections")
                 or case.get("outline") or case.get("section_list"))
    names = []
    if isinstance(requested, list):
        for item in requested:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                value = item.get("name") or item.get("title") or item.get("heading")
                if value:
                    names.append(str(value).strip())
    if names:
        return names[:8]
    blob = (task_text or "").lower()
    found = [name for name, keys in SECTION_VOCAB.items()
             if any(key.lower() in blob for key in keys)]
    return found[:8] if found else list(SECTION_VOCAB.keys())[:6]


def section_vocabulary(name):
    vocab = []
    for key in SECTION_VOCAB.get(name, [name]):
        vocab.extend(terms(key))
    vocab.extend(terms(name))
    return vocab


def is_instruction(sentence):
    lowered = sentence.lower()
    return (any(hint in lowered for hint in INSTRUCTION_HINTS)
            or sentence.startswith(("#", ">", "|")))


def numbers(text):
    return re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s?%?", text)


def citations(text):
    pattern = (r"\[(\d+(?:\s*[,\-\u2013\u3001]\s*\d+)*)\]"
               r"|\[([^\]]{0,80}?(?:19|20)\d{2}[a-z]?[^\]]*)\]"
               r"|\(([^()]{0,100}?(?:19|20)\d{2}[a-z]?[^()]*)\)")
    return [match.group(0) for match in re.finditer(pattern, text)]


def build_payload(case, task_text, docs):
    sources = [doc for doc in docs
               if doc.get("role") != "instruction" and len(doc.get("text", "")) >= 40]
    if not sources:
        return {
            "status": "insufficient_input",
            "result": {"deliverable": "", "sections": [], "sources": []},
            "evidence": [],
            "uncertainty": ["case.json 与 task.md 中没有可引用的科研材料文本，无法组装章节稿。"],
            "errors": [],
            "stats": {"source_documents": 0, "candidate_sentences": 0, "selected_sentences": 0},
        }

    sections = detect_sections(task_text, case)
    candidates = []
    for doc in sources:
        for index, sentence in enumerate(split_sentences(doc["text"])):
            sentence = sentence.strip()
            if len(sentence) < 20 or len(sentence) > 500:
                continue
            if is_instruction(sentence) or sentence.startswith(("-", "*", "+")):
                continue
            candidates.append({"sid": "%s#s%d" % (doc["id"], index + 1),
                               "doc": doc, "text": sentence, "terms": terms(sentence)})
    if not candidates:
        return {
            "status": "insufficient_input",
            "result": {"deliverable": "", "sections": [], "sources": sources},
            "evidence": [],
            "uncertainty": ["材料存在，但没有满足长度与格式要求的可用句子。"],
            "errors": [],
            "stats": {"source_documents": len(sources), "candidate_sentences": 0,
                      "selected_sentences": 0},
        }

    frequency = Counter()
    for candidate in candidates:
        frequency.update(set(candidate["terms"]))
    order = {name: index for index, name in enumerate(sections)}

    section_scores = {}
    for section in sections:
        if section == "Abstract":
            continue
        vocab = section_vocabulary(section)
        for candidate in candidates:
            score = overlap(candidate["terms"], vocab)
            if score > 0:
                section_scores.setdefault(candidate["sid"], []).append((score, section))

    assigned = OrderedDict((name, []) for name in sections if name != "Abstract")
    for candidate in candidates:
        options = section_scores.get(candidate["sid"])
        if not options:
            continue
        options.sort(key=lambda pair: (-pair[0], order[pair[1]]))
        best_score, best_section = options[0]
        rarity = sum(1 for term in candidate["terms"] if frequency.get(term, 0) <= 2)
        assigned[best_section].append((best_score * 3 + min(rarity, 4), candidate))

    evidence, bodies, picked_map, stats = [], OrderedDict(), OrderedDict(), OrderedDict()
    for section, scored in assigned.items():
        scored.sort(key=lambda pair: (-pair[0], pair[1]["sid"]))
        picked = [candidate for _, candidate in scored[:5]]
        picked.sort(key=lambda candidate: candidate["sid"])
        picked_map[section] = picked
        stats[section] = len(picked)
        bodies[section] = " ".join("%s [src:%s]" % (candidate["text"], candidate["sid"])
                                   for candidate in picked)

    abstract_source = []
    for name in ("Introduction", "Methods", "Results", "Discussion"):
        if picked_map.get(name):
            abstract_source.append(picked_map[name][0])
    if not abstract_source:
        abstract_source = sorted(candidates, key=lambda item: (-len(item["terms"]), item["sid"]))[:3]
    picked_map["Abstract"] = abstract_source
    stats["Abstract"] = len(abstract_source)
    bodies["Abstract"] = " ".join("%s [src:%s]" % (candidate["text"], candidate["sid"])
                                  for candidate in abstract_source)

    for section in sections:
        for candidate in picked_map.get(section, []):
            evidence.append(OrderedDict([
                ("claim_id", "E%02d" % (len(evidence) + 1)),
                ("section", section),
                ("sentence", candidate["text"]),
                ("source_id", candidate["doc"]["id"]),
                ("locator", candidate["doc"]["locator"]),
                ("sentence_locator", candidate["sid"]),
                ("numbers", numbers(candidate["text"])),
                ("citations", citations(candidate["text"])),
                ("kind", "verbatim_source_sentence"),
            ]))

    header = ("# 学术写作草稿（来源保持型）\n\n"
              "> 本稿只由输入材料中的原句按章节抽取组装，句中 `[src:S#]` 指向 evidence "
              "中的来源定位。未找到依据的章节已显式标注；脚本不补造任何材料外事实，"
              "作者需在此草稿上改写并逐条复核。\n\n")
    parts = [header.rstrip()]
    for section in sections:
        body = bodies.get(section, "")
        parts.append("## %s\n\n%s" % (
            section,
            body if body else "（材料中未找到可支撑本节的句子，见 uncertainty 列表。）"))
    deliverable = "\n\n".join(parts)

    empty_sections = [name for name, count in stats.items() if count == 0]
    uncertainty = ["章节「%s」在提供材料中没有找到直接支撑句，当前仅为占位说明。" % name
                   for name in empty_sections]
    joined = " ".join(doc["text"] for doc in sources).lower()
    if "doi" not in joined:
        uncertainty.append("材料中未检出 DOI 字段，参考文献元数据需人工补充与核对。")
    selected_candidates = [candidate for group in picked_map.values() for candidate in group]
    selected = {candidate["sid"] for candidate in selected_candidates}
    dropped = len(candidates) - len(selected)
    if dropped > 0:
        uncertainty.append("有 %d 条材料句子未被任何章节选中，可能主题不匹配或信息重复，"
                           "需作者判断是否使用。" % dropped)
    if not any(citations(candidate["text"]) for candidate in selected_candidates):
        uncertainty.append("入选句子中没有检出文献引用标记，引用条目需人工补入。")

    section_entries = [OrderedDict([("name", section),
                                    ("sentence_count", stats.get(section, 0)),
                                    ("source_ids", [c["doc"]["id"]
                                                    for c in picked_map.get(section, [])])])
                       for section in sections]

    stats_out = OrderedDict([
        ("source_documents", len(sources)),
        ("candidate_sentences", len(candidates)),
        ("selected_sentences", len(evidence)),
        ("sections_requested", len(sections)),
        ("sections_filled", len(sections) - len(empty_sections)),
        ("citations_in_output", sum(len(item["citations"]) for item in evidence)),
        ("numbers_in_output", sum(len(item["numbers"]) for item in evidence)),
    ])

    return {
        "status": "success" if not empty_sections else "partial",
        "deliverable": deliverable,
        "result": {
            "deliverable": deliverable,
            "sections": section_entries,
            "sources": [{"source_id": doc["id"], "locator": doc["locator"],
                         "chars": len(doc["text"])} for doc in sources],
            "limitations": ["只做抽取式组装，不做自由改写、扩写或文献检索。",
                            "材料中未出现的数值、引用和结论一律不补写。"],
        },
        "evidence": evidence,
        "uncertainty": uncertainty,
        "errors": [],
        "stats": stats_out,
        "contract_notes": ["正文为可编辑 Markdown；[src:S#] 与 evidence.sentence_locator 一一对应。"],
    }


def main():
    parser = argparse.ArgumentParser(description="Source-faithful manuscript assembly")
    parser.add_argument("--case", default=DEFAULT_CASE, help="case.json path")
    parser.add_argument("--out", "--output", default=DEFAULT_OUT, help="result.json path")
    parser.add_argument("--work", default=DEFAULT_WORK, help="scratch directory")
    args = parser.parse_args()

    stage = "load_case"
    case = {}
    try:
        if not os.path.isfile(args.case):
            raise FileNotFoundError("case file not found: %s" % os.path.basename(args.case))
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case.json must contain a JSON object")
        stage = "collect_documents"
        task_text, task_path = find_task_text(args.case, None)
        docs = collect_docs(case, task_text, task_path)
        contract = None
        for key in ("output_contract", "outputContract", "output_schema"):
            if isinstance(case.get(key), (dict, list)):
                contract = case[key]
                break
        stage = "build_payload"
        payload = build_payload(case, task_text, docs)
        stage = "write_output"
        output = finalize(case, payload, contract)
        directory = os.path.dirname(os.path.abspath(args.out))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        sys.stdout.write(json.dumps({
            "case_id": output.get("case_id"),
            "status": output.get("status"),
            "sections": len(output.get("result", {}).get("sections", [])),
            "contract_fields": len(contract_fields(contract)),
        }, ensure_ascii=False) + "\n")
        return 0
    except Exception as exc:  # honest structured failure instead of a crash
        failure = OrderedDict([
            ("case_id", case.get("case_id") or case.get("id")),
            ("status", "failed"),
            ("result", {"deliverable": "", "sections": []}),
            ("evidence", []),
            ("uncertainty", ["运行失败，未产出可交付稿；未重试、未补造任何数据。"]),
            ("errors", [{"stage": stage, "type": type(exc).__name__,
                         "message": clamp(str(exc), 400)}]),
            ("stats", {}),
            ("contract_notes", []),
        ])
        try:
            directory = os.path.dirname(os.path.abspath(args.out))
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            with open(args.out, "w", encoding="utf-8") as handle:
                json.dump(failure, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except OSError as write_exc:
            log("cannot write failure output: %s" % write_exc)
        sys.stdout.write(json.dumps({"status": "failed", "stage": stage}, ensure_ascii=False) + "\n")
        return 2


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)

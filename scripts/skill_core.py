# -*- coding: utf-8 -*-
"""Shared deterministic utilities for the academic-writing skill scripts.

Standard library only. No network access, no randomness.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, OrderedDict

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUTPUT = "/app/output/result.json"
SKIP_KEYS = {"output_contract", "outputcontract", "output_schema", "result_schema"}

STOPWORDS = set("""a an the and or but if then than that this these those of to in on for with without by from as at is are was were be been being it its their we our you your they them he she his her not no can could may might must should would will do does did have has had also such using used use based between within into over under about more most less least other others which who whom whose what when where why how all any both each few many some own same so only very just""".split())

STANDARD_SECTIONS = ["Abstract", "Introduction", "Related Work", "Methods", "Results", "Discussion", "Conclusion"]

ALIASES = OrderedDict([
    ("case_id", ["case_id", "caseid", "input_id", "task_id", "record_id"]),
    ("status", ["status", "run_status", "state", "execution_status", "completion_status"]),
    ("deliverable", ["deliverable", "manuscript", "draft", "final_text", "final_document",
                     "output_text", "result_text", "revised_text", "polished_text",
                     "adapted_text", "rewritten_text", "annotated_text", "manuscript_text",
                     "article", "document", "content", "text", "output", "result", "body"]),
    ("summary", ["summary", "overview", "abstract_summary", "brief", "executive_summary", "description"]),
    ("evidence", ["evidence", "evidence_map", "evidence_table", "source_map", "source_mapping",
                  "fact_map", "materials_map", "citation_map", "citation_mapping",
                  "claim_evidence", "reference_map", "source_evidence", "parameter_table",
                  "template_map", "claim_map"]),
    ("sources", ["sources", "references", "bibliography", "source_list", "material_index",
                 "materials", "reference_list", "reference_entries", "cited_works"]),
    ("changes", ["changes", "change_log", "edit_log", "revision_log", "edits", "diff",
                 "modifications", "change_records", "patch", "edit_actions"]),
    ("uncertainties", ["uncertainties", "uncertainty", "review_items", "manual_review",
                       "open_questions", "warnings", "flags", "issues", "pending_items", "risks"]),
    ("limitations", ["limitations", "limits", "boundaries", "scope", "constraints"]),
    ("checks", ["checks", "checklist", "self_check", "validation", "validations",
                "quality_checks", "compliance", "format_report", "structure_report",
                "quality_report", "diagnostics"]),
    ("metrics", ["metrics", "statistics", "stats", "counts", "measurements", "numbers", "indicators"]),
    ("notes", ["notes", "note", "comments", "rationale", "method_notes", "provenance"]),
])


def log(msg):
    sys.stderr.write("[run_skill] %s\n" % msg)


def sanitize(text):
    text = str(text)
    text = re.sub(r"[A-Za-z]:\\[^\s\"']*", "<path>", text)
    text = re.sub(r"/(?:home|root|Users|tmp|app|input|skills)/[^\s\"']*", "<path>", text)
    return text[:2000]


def norm_name(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


ALIAS_INDEX = {}
for _canon, _names in ALIASES.items():
    for _name in _names:
        ALIAS_INDEX[norm_name(_name)] = _canon


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def find_task_text(case_path, explicit=None):
    candidates = []
    if explicit:
        candidates.append(explicit)
    if case_path:
        base = os.path.dirname(os.path.abspath(case_path))
        candidates += [os.path.join(base, "task.md"), os.path.join(base, "..", "task.md")]
    candidates += ["/input/task.md", "/app/input/task.md", "task.md"]
    for path in candidates:
        try:
            if path and os.path.isfile(path):
                return read_text(path), path
        except OSError:
            continue
    return "", None


def walk_strings(value, pointer="", skip=SKIP_KEYS):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).strip().lower() in skip:
                continue
            yield from walk_strings(item, pointer + "/" + str(key), skip)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_strings(item, pointer + "/" + str(index), skip)
    elif isinstance(value, str):
        text = value.strip()
        if text:
            yield pointer or "/", text


def walk_dicts(value, pointer="", skip=SKIP_KEYS):
    if isinstance(value, dict):
        yield pointer or "/", value
        for key, item in value.items():
            if str(key).strip().lower() in skip:
                continue
            yield from walk_dicts(item, pointer + "/" + str(key), skip)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_dicts(item, pointer + "/" + str(index), skip)


INSTRUCTION_PREFIXES = ("/task", "/instruction", "/prompt", "/rubric", "/evaluation",
                        "/scoring", "/requirements", "/description", "/query")


def collect_docs(case, task_text, task_path=None):
    docs, seen = [], set()
    for pointer, text in walk_strings(case):
        if len(text) < 12:
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        role = "instruction" if pointer.lower().startswith(INSTRUCTION_PREFIXES) else "source"
        docs.append({"id": "S%d" % (len(docs) + 1), "locator": pointer, "text": text, "role": role})
    if task_text and len(task_text.strip()) >= 12:
        docs.append({"id": "TASK", "locator": task_path or "/task.md", "text": task_text.strip(),
                     "role": "instruction"})
    return docs


def source_docs(docs):
    return [doc for doc in docs if doc.get("id") != "TASK" and doc.get("role") != "instruction"]


def split_sentences(text):
    result = []
    for paragraph in re.split(r"\n\s*\n", text):
        for line in paragraph.split("\n"):
            line = line.strip()
            if not line:
                continue
            if re.match(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|>\s|\|)", line):
                result.append(line)
                continue
            parts = re.split(r"(?<=[\u3002\uff01\uff1f\uff1b])|(?<=[.!?;])(?=\s)", line)
            for sentence in parts:
                sentence = sentence.strip()
                if sentence:
                    result.append(sentence)
    return result


def paragraphs(text):
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def cjk_terms(text):
    terms_out = []
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(run) == 1:
            terms_out.append(run)
        else:
            terms_out.extend(run[i:i + 2] for i in range(len(run) - 1))
    return terms_out


def terms(text):
    lowered = text.lower()
    words = [word for word in re.findall(r"[a-z][a-z0-9\-]{1,}", lowered)
             if word not in STOPWORDS and not word.isdigit()]
    return words + cjk_terms(text)


def overlap(left, right):
    a, b = Counter(left), Counter(right)
    return sum(min(a[key], b[key]) for key in a.keys() & b.keys())


def jaccard(left, right):
    a, b = set(left), set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def numbers(text):
    return re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s?%?", text)


def numeric_values(text):
    values = []
    for token in numbers(text):
        try:
            values.append(float(token.replace("%", "").strip()))
        except ValueError:
            continue
    return values


CITATION_RE = re.compile(
    r"\[(\d+(?:\s*[,\-\u2013\u2014\u3001]\s*\d+)*)\]"
    r"|\[([^\]]{0,80}?(?:19|20)\d{2}[a-z]?[^\]]*)\]"
    r"|\(([^()]{0,100}?(?:19|20)\d{2}[a-z]?[^()]*)\)"
)


def citations(text):
    found = []
    for match in CITATION_RE.finditer(text):
        raw = match.group(0)
        found.append({"raw": raw, "start": match.start(), "end": match.end(),
                      "numeric": match.group(1), "author_year": match.group(2) or match.group(3)})
    return found


def detect_lang(text):
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk and cjk * 4 >= latin:
        return "zh"
    return "en"


def clamp(text, limit=4000):
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …"


def unique(items):
    seen, result = set(), []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def get_contract(case):
    for key in ("output_contract", "outputContract", "output_contract_schema"):
        value = case.get(key)
        if isinstance(value, (dict, list)):
            return value
    return None


def contract_fields(spec):
    if spec is None:
        return []
    if isinstance(spec, list):
        fields = []
        for item in spec:
            if isinstance(item, str):
                fields.append((item, None, False))
            elif isinstance(item, dict):
                name = item.get("name") or item.get("field") or item.get("key") or item.get("id")
                if name:
                    sub = item.get("schema")
                    if not isinstance(sub, (dict, str, list)):
                        sub = {key: item[key] for key in ("type", "items", "properties", "description") if key in item}
                    fields.append((str(name), sub or None, bool(item.get("required", False))))
        return fields
    if isinstance(spec, dict):
        if isinstance(spec.get("properties"), dict):
            required = set(spec.get("required") or [])
            return [(str(key), value, key in required) for key, value in spec["properties"].items()]
        if isinstance(spec.get("fields"), (dict, list)):
            return contract_fields(spec["fields"])
        required_list = spec.get("required") if isinstance(spec.get("required"), list) else []
        required = set(str(item) for item in required_list)
        fields = []
        for key, value in spec.items():
            lowered = str(key).lower()
            if lowered in ("$schema", "title", "description", "type", "required", "definitions", "$defs"):
                continue
            fields.append((str(key), value, str(key) in required))
        return fields
    return []


def expected_type(spec):
    if isinstance(spec, str):
        lowered = spec.strip().lower()
        if lowered in ("array", "list"):
            return "array"
        if lowered in ("object", "dict", "map"):
            return "object"
        if lowered in ("number", "float", "double"):
            return "number"
        if lowered in ("integer", "int"):
            return "integer"
        if lowered in ("boolean", "bool"):
            return "boolean"
        return "string"
    if isinstance(spec, dict):
        declared = spec.get("type")
        if isinstance(declared, list):
            declared = next((item for item in declared if item != "null"), None)
        if declared in ("array", "object", "string", "number", "integer", "boolean"):
            return declared
        if isinstance(spec.get("properties"), dict):
            return "object"
        if "items" in spec:
            return "array"
    if isinstance(spec, list):
        return "array"
    return "any"


def lookup_payload(name, payload):
    normalized = norm_name(name)
    if normalized in ALIAS_INDEX:
        canonical = ALIAS_INDEX[normalized]
        if canonical in payload and payload[canonical] is not None:
            return payload[canonical]
    for key, value in payload.items():
        if norm_name(key) == normalized and value is not None:
            return value
    for canonical in ALIASES:
        if canonical not in payload or payload[canonical] is None:
            continue
        for alias in ALIASES[canonical]:
            alias_norm = norm_name(alias)
            if len(alias_norm) >= 4 and alias_norm in normalized:
                return payload[canonical]
    return None


def adapt(value, spec, path, unmapped, root):
    kind = expected_type(spec)
    properties = spec.get("properties") if isinstance(spec, dict) else None
    if isinstance(properties, dict):
        base = value if isinstance(value, dict) else root
        result = OrderedDict()
        for name, sub in properties.items():
            result[name] = fill_named(name, sub, base, path + "." + name, unmapped, root)
        return result
    if kind == "array":
        if isinstance(value, list):
            return value
        return [value]
    if kind == "object":
        if isinstance(value, dict):
            return value
        return {"value": value}
    if kind == "string":
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)
    if kind in ("number", "integer"):
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        return None
    if kind == "boolean":
        return value if isinstance(value, bool) else None
    return value


def fill_named(name, spec, payload, path, unmapped, root):
    value = lookup_payload(name, payload)
    if value is None:
        unmapped.append(path)
        if isinstance(spec, dict) and isinstance(spec.get("properties"), dict):
            result = OrderedDict()
            for child, sub in spec["properties"].items():
                result[child] = fill_named(child, sub, payload, path + "." + child, unmapped, root)
            return result
        return None
    return adapt(value, spec, path, unmapped, root)


def build_result(case, payload, contract):
    result = OrderedDict()
    case_id = payload.get("case_id") or case.get("case_id") or case.get("id")
    result["case_id"] = case_id
    fields = contract_fields(contract)
    unmapped, field_status = [], []
    for name, spec, required in fields:
        if norm_name(name) == "caseid":
            continue
        value = fill_named(name, spec, payload, name, unmapped, payload)
        result[name] = value
        field_status.append({"name": name, "required": bool(required), "filled": value is not None})
    for key in ("status", "summary", "deliverable", "evidence", "sources", "changes",
                "uncertainties", "limitations", "checks", "metrics", "notes"):
        if key not in result and payload.get(key) is not None:
            result[key] = payload[key]
    if contract is None:
        contract_status = "absent"
    elif unmapped:
        contract_status = "partial"
    else:
        contract_status = "complete"
    result["contract_status"] = OrderedDict([
        ("declared_fields", [item[0] for item in fields]),
        ("unmapped_fields", unmapped),
        ("status", contract_status),
        ("field_status", field_status),
        ("note", "Contract fields keep their original names; unresolved fields stay null and are never invented."),
    ])
    return result


def write_output(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def empty_payload(case, reason):
    return {
        "case_id": case.get("case_id") or case.get("id"),
        "status": "partial",
        "summary": "没有找到可用的输入材料，未生成任何实质性写作产物。",
        "deliverable": "",
        "evidence": [],
        "sources": [],
        "changes": [],
        "uncertainties": [reason],
        "limitations": ["输入材料为空或不可读，结果只保留结构，不包含任何补造事实。"],
        "checks": [{"check": "input_materials", "status": "failed", "detail": reason}],
        "metrics": {},
        "notes": "空输入下的诚实部分结果。",
    }


def run(builder, description=None):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--case", default=DEFAULT_CASE, help="Path to case.json (default /input/case.json)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to result.json (default /app/output/result.json)")
    parser.add_argument("--task", default=None, help="Optional explicit task.md path")
    args = parser.parse_args()
    case, stage = None, "load_case"
    try:
        if not os.path.isfile(args.case):
            raise FileNotFoundError("case file not found")
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case.json must contain a JSON object")
        stage = "load_task"
        task_text, task_path = find_task_text(args.case, args.task)
        stage = "collect_documents"
        docs = collect_docs(case, task_text, task_path)
        stage = "build_payload"
        payload = builder(case, task_text, docs)
        if not isinstance(payload, dict):
            raise ValueError("builder returned a non-object payload")
        if not payload.get("case_id"):
            payload["case_id"] = case.get("case_id") or case.get("id")
        stage = "build_result"
        result = build_result(case, payload, get_contract(case))
        write_output(args.output, result)
        sys.stdout.write(json.dumps({
            "case_id": result.get("case_id"),
            "status": result.get("status"),
            "output": args.output,
            "contract_status": result.get("contract_status", {}).get("status"),
            "declared_fields": len(result.get("contract_status", {}).get("declared_fields", [])),
        }, ensure_ascii=False) + "\n")
        return 0
    except Exception as exc:  # structured failure, never a silent crash
        case_id = case.get("case_id") if isinstance(case, dict) else None
        error = OrderedDict([
            ("case_id", case_id),
            ("status", "failed"),
            ("error", OrderedDict([
                ("type", type(exc).__name__),
                ("message", sanitize(exc)),
                ("stage", stage),
            ])),
            ("uncertainties", ["本次运行失败，未产出可交付结果；未重试、未补造任何数据。"]),
        ])
        try:
            write_output(args.output, error)
        except Exception as write_exc:
            log("failed to write error output: %s" % sanitize(write_exc))
        sys.stdout.write(json.dumps({"case_id": case_id, "status": "failed", "stage": stage,
                                     "error": type(exc).__name__}, ensure_ascii=False) + "\n")
        return 2

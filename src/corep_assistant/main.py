import argparse
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Tuple


@dataclass
class RegulationSection:
    section_id: str
    title: str
    text: str
    tags: List[str]


@dataclass
class FieldOutput:
    field_code: str
    line: str
    label: str
    value: float | None
    units: str
    rule_refs: List[str]
    validation_flags: List[str]


@dataclass
class StructuredOutput:
    template_id: str
    template_name: str
    entity_id: str
    reporting_date: str
    currency: str
    fields: List[FieldOutput]
    audit_log: Dict[str, List[str]]


def load_regulations(path: str) -> List[RegulationSection]:
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return [
        RegulationSection(
            section_id=item["id"],
            title=item["title"],
            text=item["text"],
            tags=item.get("tags", []),
        )
        for item in raw
    ]


def load_template_schema(path: str) -> Dict[str, str | List[Dict[str, str]]]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def tokenize(text: str) -> List[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return [token for token in cleaned.split() if len(token) > 1]


def retrieve_sections(question: str, scenario: Dict[str, object], sections: List[RegulationSection]) -> List[RegulationSection]:
    scenario_text = json.dumps(scenario)
    tokens = set(tokenize(question + " " + scenario_text))
    scored: List[Tuple[int, RegulationSection]] = []
    for section in sections:
        section_tokens = set(tokenize(section.text + " " + " ".join(section.tags)))
        score = len(tokens.intersection(section_tokens))
        if score:
            scored.append((score, section))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [section for _, section in scored[:5]]


def build_field_outputs(schema: Dict[str, object], scenario: Dict[str, object], section_refs: Dict[str, List[str]]) -> List[FieldOutput]:
    fields: List[FieldOutput] = []
    currency = str(schema["currency"])

    mapping = {
        "CA1.010": ("cet1_gbp_thousands", ["PRA_OF_010", "EBA_CA1_001"]),
        "CA1.020": ("at1_gbp_thousands", ["PRA_OF_020", "EBA_CA1_001"]),
        "CA1.030": ("t2_gbp_thousands", ["PRA_OF_030", "EBA_CA1_001"]),
        "CA1.060": ("total_own_funds", ["PRA_OF_001", "EBA_CA1_001"]),
    }

    cet1 = scenario.get("cet1_gbp_thousands")
    at1 = scenario.get("at1_gbp_thousands")
    t2 = scenario.get("t2_gbp_thousands")
    total = None
    if isinstance(cet1, (int, float)) and isinstance(at1, (int, float)) and isinstance(t2, (int, float)):
        total = cet1 + at1 + t2

    for field in schema["fields"]:
        field_code = field["field_code"]
        scenario_key, default_refs = mapping.get(field_code, (None, []))
        value = None
        if field_code == "CA1.060":
            value = total
        elif scenario_key:
            value = scenario.get(scenario_key)
        flags: List[str] = []
        if field.get("required") and value is None:
            flags.append("missing_required_value")
        if field_code == "CA1.060" and total is None:
            flags.append("total_unavailable")
        fields.append(
            FieldOutput(
                field_code=field_code,
                line=field["line"],
                label=field["label"],
                value=value,
                units=currency,
                rule_refs=default_refs,
                validation_flags=flags,
            )
        )
        section_refs[field_code] = default_refs
    return fields


def validate_totals(fields: List[FieldOutput]) -> None:
    values = {field.field_code: field.value for field in fields}
    if all(isinstance(values.get(code), (int, float)) for code in ["CA1.010", "CA1.020", "CA1.030", "CA1.060"]):
        expected = values["CA1.010"] + values["CA1.020"] + values["CA1.030"]
        if expected != values["CA1.060"]:
            for field in fields:
                if field.field_code == "CA1.060":
                    field.validation_flags.append("total_mismatch")


def render_template_markdown(schema: Dict[str, object], output: StructuredOutput) -> str:
    lines = [
        f"# COREP {output.template_id} - {output.template_name}",
        "",
        f"Entity: {output.entity_id}",
        f"Reporting date: {output.reporting_date}",
        f"Currency: {output.currency}",
        "",
        "| Line | Field | Value | Units | Validation flags | Rule refs |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for field in output.fields:
        value = "" if field.value is None else f"{field.value:,.0f}"
        flags = ", ".join(field.validation_flags) if field.validation_flags else ""
        refs = ", ".join(field.rule_refs) if field.rule_refs else ""
        lines.append(
            f"| {field.line} | {field.label} | {value} | {field.units} | {flags} | {refs} |"
        )
    return "\n".join(lines)


def build_audit_log(retrieved_sections: List[RegulationSection]) -> Dict[str, str]:
    return {
        section.section_id: f"{section.title}: {section.text}" for section in retrieved_sections
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-assisted COREP reporting assistant (prototype)")
    parser.add_argument("--question", required=True, help="Natural-language question from the analyst")
    parser.add_argument("--scenario", required=True, help="Path to JSON scenario input")
    parser.add_argument("--output", required=True, help="Output directory for generated artifacts")
    parser.add_argument("--regulations", default="data/regulations.json", help="Path to regulations JSON")
    parser.add_argument("--schema", default="data/template_schema.json", help="Path to template schema JSON")
    args = parser.parse_args()

    with open(args.scenario, "r", encoding="utf-8") as handle:
        scenario = json.load(handle)

    regulations = load_regulations(args.regulations)
    schema = load_template_schema(args.schema)

    retrieved = retrieve_sections(args.question, scenario, regulations)
    audit_log = build_audit_log(retrieved)
    section_refs: Dict[str, List[str]] = {}

    fields = build_field_outputs(schema, scenario, section_refs)
    validate_totals(fields)

    structured_output = StructuredOutput(
        template_id=str(schema["template_id"]),
        template_name=str(schema["template_name"]),
        entity_id=str(scenario.get("entity_id", "UNKNOWN")),
        reporting_date=str(scenario.get("reporting_date", datetime.utcnow().date())),
        currency=str(schema["currency"]),
        fields=fields,
        audit_log=section_refs,
    )

    os.makedirs(args.output, exist_ok=True)
    structured_path = os.path.join(args.output, "structured_output.json")
    template_path = os.path.join(args.output, "template_extract.md")
    audit_path = os.path.join(args.output, "audit_log.json")

    with open(structured_path, "w", encoding="utf-8") as handle:
        json.dump(asdict(structured_output), handle, indent=2)

    with open(template_path, "w", encoding="utf-8") as handle:
        handle.write(render_template_markdown(schema, structured_output))

    with open(audit_path, "w", encoding="utf-8") as handle:
        json.dump(audit_log, handle, indent=2)

    print(f"Wrote structured output to {structured_path}")
    print(f"Wrote template extract to {template_path}")
    print(f"Wrote audit log to {audit_path}")


if __name__ == "__main__":
    main()

# LLM-assisted COREP reporting assistant (prototype)

This repository contains a lightweight prototype for a regulatory reporting assistant focused on COREP own funds (template CA1). The assistant takes a natural-language question and a JSON reporting scenario, retrieves relevant PRA/EBA regulatory text, generates a structured output aligned to a template schema, renders a human-readable template extract, and produces an audit log of rule references.

## How it works

1. **Retrieval**: The assistant performs simple keyword-based matching over curated PRA/EBA regulatory excerpts.
2. **Structured output**: Scenario data is mapped into the CA1 template schema (CET1, AT1, Tier 2, Total own funds).
3. **Validation**: Basic checks ensure totals match component sums and required fields are present.
4. **Audit log**: Rule references are attached to each field and the retrieved regulatory excerpts are saved for review.

## Run the prototype

```bash
python src/corep_assistant/main.py \
  --question "How should we report own funds for year-end?" \
  --scenario examples/scenario.json \
  --output outputs/run-1
```

Artifacts are written to the output directory:

- `structured_output.json` – structured data aligned to the template schema
- `template_extract.md` – human-readable COREP template extract
- `audit_log.json` – retrieved regulatory excerpts used for justification

## Data files

- `data/regulations.json` – curated regulatory excerpts with IDs and tags
- `data/template_schema.json` – simplified CA1 template schema
- `examples/scenario.json` – sample reporting scenario

## Notes

This is a deterministic prototype with no external API calls. It is intended to demonstrate the end-to-end flow from question → retrieval → structured output → template extract for a narrow COREP scope.

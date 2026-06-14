# Coding Agent Harness Example

Runs one committed deterministic reference-agent prompt case and writes a compact
transcript that can be scored by `dicom-kb eval score`.

```bash
python examples/coding_agent_harness/run_reference_case.py \
  --db /tmp/dicom-kb-fixture.sqlite \
  --edition 2026b \
  --case agent.ct.required_modules \
  --out /tmp/dicom-kb-reference-run.json
dicom-kb eval score /tmp/dicom-kb-reference-run.json
```

The default case is known to work against the synthetic fixture KB. Use a real
local build by changing `--db`, `--edition`, and `--case`.

# MCP Example

Serve the query tools over stdio against the synthetic fixture KB:

```bash
dicom-kb build-fixture --edition 2026b --db /tmp/dicom-kb-fixture.sqlite --force
dicom-kb mcp serve --edition 2026b --db /tmp/dicom-kb-fixture.sqlite
```

The command is intended to be launched by an MCP client and will wait on stdio.
Install the optional MCP dependency group before using a real client:

```bash
uv sync --extra mcp
```

For a real local build, pass the concrete edition and the matching external
cache database path instead of the fixture DB.

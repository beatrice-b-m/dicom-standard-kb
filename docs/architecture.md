# Architecture

The v1 architecture is a Python core library with thin surfaces: CLI, MCP,
and local SQLite storage. Official artifacts are acquired into a local cache,
parsed into canonical records, imported transactionally, and queried through
edition-aware response contracts.

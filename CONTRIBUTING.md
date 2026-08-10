# Contributing

Contributions are welcome where they preserve PEA's controlled operating model.

## Before submitting a change

1. Keep source connectors, processing logic and destination adapters separate.
2. Do not commit credentials, OAuth material, application content or operational logs.
3. Require an explicit user action for every source read.
4. Preserve duplicate checks and final confirmation for external writes.
5. Add focused tests for changed behaviour.
6. Run `uvx ruff check .` and `uv run pytest -q`.

Report security vulnerabilities privately as described in [SECURITY.md](SECURITY.md); do not open
a public issue containing vulnerability details or credentials.

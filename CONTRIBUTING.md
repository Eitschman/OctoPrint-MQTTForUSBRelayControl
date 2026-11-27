# Contributing

This international project uses English source identifiers, comments, docstrings,
technical messages and primary documentation. The UI defaults to English and includes
German translations. Keep the companion small and readable; explain upstream internal
contracts and test failure paths alongside changes.

Use Python 3.9+, uv, Node.js and pnpm. Public tests and builds require no private tools,
account, secrets service or development launcher. See [development](docs/public/development.md)
and the [architecture decisions](docs/adr/0001-companion.md).

Do not add polling, a second MQTT connection, direct USB access, inter-plugin REST,
global class patches or permanent original-plugin changes. Never retry a hardware
write as an automatic error recovery. Test hardware behavior only in an explicitly
authorized environment; automated tests use synthetic HID and disposable loopback services.

Code changes were developed with AI assistance. Maintainers must review the actual
implementation and evidence before accepting release readiness. No human review or
real-hardware result is implied by passing software tests.

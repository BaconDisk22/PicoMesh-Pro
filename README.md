# PicoMesh Pro

An independently maintained, enhanced MMBasic companion client for MeshCore, derived from [Vigoleis912/PicoMeshCore](https://github.com/Vigoleis912/PicoMeshCore).

## Status
Pre-release development. `meshcore.bas` has been modified from its upstream baseline: local channel listing, selection, channel message sending, and name/index backup and restore have been added, alongside UART reliability guards and source-level regression tests. **Physical PicoMite/PicoCalc hardware testing is not yet complete.** Private-channel key configuration and path hash size switching are not confirmed implemented. No release candidate has been validated yet.

## Hardware
- Raspberry Pi Pico with PicoMite
- Compatible MeshCore companion radio (upstream documents Heltec V4)
- UART wiring and firmware instructions: [upstream README](docs/UPSTREAM_README.md)

## Planned enhancements
1. Discover supported channel protocol commands and radio firmware compatibility.
2. List and select channels, without changing existing #public behavior.
3. Configure additional public/private channels and protect channel secrets.
4. Save and restore settings, with explicit recovery on malformed data.
5. Investigate path hash size selection, only where firmware supports it.
6. Add reproducible tests and hardware validation.

See [ROADMAP.md](ROADMAP.md).

## Attribution and license
Based on PicoMeshCore by Vigoleis912. Original source and upstream documentation are retained. Distributed under the GNU GPL v3; see [LICENSE](LICENSE). Changes to the upstream baseline will be tracked in commits.

## Safety
Do not commit private channel keys or credentials. Test against a controlled radio before transmitting.

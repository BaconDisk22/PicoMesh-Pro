# PicoMesh Pro Roadmap

## Phase 0 — Baseline
- [x] Import upstream MMBasic source
- [x] Preserve upstream license and README
- [x] Create project README and roadmap
- [ ] Record upstream revision SHA and baseline hardware test results
- [ ] Audit UART frame parser, send/receive paths, and channel command IDs

## Phase 1 — Multi-channel support
- [ ] Identify firmware-supported channel list/configuration protocol
- [ ] Add safe channel enumeration and active-channel selection
- [ ] Send and receive on non-default public channels
- [ ] Add private channel setup with secret redaction
- [ ] Handle missing/invalid channel IDs and unsupported firmware
- [ ] Test on real PicoMite and companion radio

## Phase 2 — Routing and persistence
- [ ] Determine firmware support and valid values for path hash size
- [ ] Implement guarded path hash size selection
- [ ] Add persistent preferences with validation and recovery

## Phase 3 — Quality and release
- [ ] Build parser/packet fixtures and regression checks
- [ ] Document wiring, setup, and troubleshooting
- [ ] Publish first alpha only after hardware validation

No feature is marked complete until tested.

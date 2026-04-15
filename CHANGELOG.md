# Changelog

## 0.2.5 - 2026-04-15

- raised full pytest baseline to `298 passed`
- added `scripts/verify_native_installer_lane.py` for end-to-end native installer lane validation
- kept native installer lane in probe mode by default, with `--require-toolchain` / `--require-signed` for hard gates
- added `scripts/run_soak_validation.py` for repeated headless/smoke/preflight soak cycles
- added `--require-all-ready` strict gating plus per-cycle readiness/timing evidence to soak validation
- extended regression coverage for validation scripts
- added native installer MSI build CLI
- added native installer signature verification CLI
- advanced `PL-014` from scaffold/toolchain stage into MSI build/signature verification stage

## 0.2.3 - 2026-04-15

- raised full pytest baseline to `288 passed`
- added native installer toolchain verification CLI
- added WiX/MSI scaffold generation and verification CLI
- advanced `PL-014` from route planning into executable scaffold/toolchain stage

## 0.2.2 - 2026-04-14

- added formal native installer and signing route plan
- added formal extension contract and plugin boundary specification
- kept `PL-014` active with documented target shape, cutover conditions, verification strategy, and rollback boundary

## 0.2.1 - 2026-04-14

- raised full pytest baseline to `280 passed`
- hardened `verify_dist_install.py` for multi-version dist artifact selection
- added release-preflight blocking for recorded service shutdown failures
- added shutdown failure evidence regression coverage for session services

## 0.2.0 - 2026-04-14

- stabilized full pytest baseline at `274 passed`
- completed release-staging and fresh-install validation closure
- formalized README, handoff, risk register, validation, and task documents
- aligned UI/test contracts and hardened port-conflict regression cases
- reduced packaged delivery noise by filtering selected test/dev payloads


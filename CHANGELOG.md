# Changelog

## Unreleased - 2026-04-16

- raised full pytest baseline to `356 passed`
- formalized explicit Class A extension runtime loading via `--load-enabled-extensions`
- tightened plugin manifest entrypoint validation to require `module:function` format
- added runtime-loading coverage for lazy sibling imports, duplicate module-name isolation, and high-risk plugin non-auto-load behavior
- wired controlled Class A runtime loading into release-preflight and failure evidence recording
- made headless summary expose runtime gate counts without implicitly executing plugin code
- cleared formal GUI audit warnings for the dashboard and packet-console delivery layout at target resolutions
- added 2.0 project-flow / feature / issue / dependency / handoff documentation baseline
- removed obsolete temp probe directories and stale dist artifacts

## 0.2.5 - 2026-04-15

- raised full pytest baseline to `332 passed`
- reworked main window, packet console, complex protocol panels, and transport panels into tabbed/scrollable layouts
- reduced default packet-console dock footprint and restored primary working-area height
- added retry-tolerant authoritative full-suite execution for transient Windows UI test crashes
- tightened hero, quick-navigation sidebar, and small-window context auto-collapse for better first-screen focus
- made packet-console filters collapsed by default to reduce visual noise during normal operation
- added `scripts/build_release_deliverables.py` to materialize deliverable archives into `dist/deliverables`
- continued product-facing copy cleanup across dashboard, owner surfaces, Modbus pages, and transport drafts
- added `scripts/audit_gui_layout.py` for formal offscreen GUI layout and screenshot auditing
- added `scripts/run_full_test_suite.py` as the authoritative full-suite validation entry
- moved CI full-suite truth to `run_full_test_suite.py`
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


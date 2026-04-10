# ProtoLink Release Checklist

Last created: 2026-04-09

## Purpose

This checklist is the first release-preparation artifact for ProtoLink.

It does not claim packaging is complete.
It defines the minimum release-preparation truth that must exist before packaging is treated as a real active delivery path.

## Preconditions

- canonical backlog is current
- current active mainline is reflected in:
  - `docs/CURRENT_STATE.md`
  - `docs/PROJECT_STATUS.md`
  - `docs/ENGINEERING_TASKLIST.md`
  - `docs/MAINLINE_STATUS.md`
- full test suite is green
- smoke checklist is green

## Release-preparation checks

### 1. Workspace truth

- active workspace is known
- generated runtime artifacts are attributable to that workspace
- logs/captures/exports are not silently landing outside the intended workspace
- workspace manifest exists and is current:
  - `workspace_manifest.json`
- migration baseline works:

```powershell
uv run protolink --migrate-workspace
```

### 2. Verification truth

- `uv run pytest` passes
- targeted workflow acceptance passes for:
  - Modbus RTU
  - Modbus TCP
- offscreen UI smoke passes

### 3. Export truth

- runtime log export produces a real bundle from workspace logs
- latest profile export produces a real bundle from workspace profiles
- release bundle export produces a multi-artifact bundle from the active workspace
- one-shot release preparation can run:

```powershell
uv run protolink --workspace <workspace-path> --prepare-release bench-release
```

- archive packaging can run:

```powershell
uv run protolink --workspace <workspace-path> --package-release bench-release
```

- portable package build can run:

```powershell
uv run protolink --workspace <workspace-path> --build-portable-package bench-portable
```

- portable package extract/install can run:

```powershell
uv run protolink --install-portable-package <archive-path> <target-dir>
```

- portable package verify can run:

```powershell
uv run protolink --verify-portable-package <archive-path>
```

- portable package install validates `portable-manifest.json` and payload checksums before extraction

- distribution package build can run:

```powershell
uv run protolink --workspace <workspace-path> --build-distribution-package bench-distribution
```

- distribution package extract/install can run:

```powershell
uv run protolink --install-distribution-package <archive-path> <staging-dir> <target-dir>
```

- distribution package install rejects nested-archive checksum mismatches from `distribution-manifest.json`

- installer-staging package can run:

```powershell
uv run protolink --workspace <workspace-path> --build-installer-staging bench-installer
```

- installer-staging extract/install can run:

```powershell
uv run protolink --install-installer-staging <archive-path> <staging-dir> <target-dir>
```

- installer-staging install rejects distribution-archive checksum mismatches from `installer-manifest.json`

- installer-staging verify can run:

```powershell
uv run protolink --verify-installer-staging <archive-path>
```

- installer-package install rejects installer-staging checksum mismatches from `installer-package-manifest.json`

- installer-package verify can run:

```powershell
uv run protolink --verify-installer-package <archive-path>
```

- installer-package clean release-staging install can run:

```powershell
uv run protolink --install-installer-package <archive-path> <clean-staging-dir> <clean-install-dir>
```

- clean release-staging install produces:
  - staged `installer-package-manifest.json`
  - nested installer-staging and distribution manifests
  - portable payload files in the install dir
  - `install-receipt.json` in the install dir

- portable / distribution / installer installs reject zip path-traversal and symlink entries during extraction

- capture export path produces a real bundle from workflow-generated capture artifacts
- export manifests identify:
  - bundle kind
  - bundle name
  - payload file
  - source file when copied from an existing runtime artifact

### 4. Known warnings

Current known warnings allowed for this phase:

- None.

Any new warning class must be triaged before a release candidate is declared.

### 5. Documentation truth

- release-facing commands in `README.md` still work
- `docs/VALIDATION.md` matches actual passing validation commands
- `docs/CURRENT_STATE.md` does not describe invalidated counts or obsolete workflow status
- `.github/workflows/ci.yml` mirrors the current validation baseline

### 6. Product-surface truth

- owned workflow surfaces currently present in the main window:
  - Modbus RTU Lab
  - Modbus TCP Lab
  - Serial Studio
  - TCP Client
  - TCP Server
  - UDP Lab
  - MQTT Client
  - MQTT Server
  - Register Monitor
  - Automation Rules

### 7. Open blockers before real packaging

- project-local git baseline exists and `git status --short` is clean before release handoff
- installer packaging/distribution now exists and is verified here, but should still be exercised on a clean release-staging machine before a release candidate
- workspace migration baseline exists and now feeds release-prep flows, but release candidate sign-off still depends on a clean release environment

## Exit condition

This checklist is complete only when:

- the smoke checklist is green
- docs and verification are in sync
- packaging blockers are reduced enough to justify switching the active mainline from preparation to executable release work
- the current validation baseline stays reproducible in CI and on a clean release-staging machine

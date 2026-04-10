# ProtoLink Import / Export Conventions

## 1. 目标

导入导出必须服务于三个核心资产域：

- captures
- logs
- profiles

原则：

- 工作区目录仍然是运行期事实源
- `exports/` 只作为对外打包/交换目录
- 每个导出包都必须带 manifest

## 2. 当前约定

### 源目录映射

- `capture` -> `workspace/captures/`
- `log` -> `workspace/logs/`
- `profile` -> `workspace/profiles/`

### 导出包目录

所有导出包进入：

```text
workspace/exports/<timestamp>-<kind>-<sanitized-name>/
```

例如：

```text
workspace/exports/20260408-031530-capture-Bench-Port-01/
```

### 导出包内容

每个导出包至少包含：

- `manifest.json`
- 1 个主 payload 文件

## 3. manifest v1 最小字段

- `format_version`
- `kind`
- `bundle_name`
- `source_dir`
- `payload_file`
- `manifest_file`

## 4. 文件名规则

- 只保留 `A-Z a-z 0-9 . _ -`
- 其他字符统一折叠为 `-`
- 结果为空时回退为 `artifact`

## 5. 当前代码落点

`src/protolink/core/import_export.py` 现已提供：

- `ArtifactKind`
- `sanitize_artifact_name()`
- `source_directory_for_kind()`
- `build_export_bundle_plan()`
- `build_export_manifest()`

这意味着后续 capture/log/profile 导出功能可以先共用同一套 bundle 命名与 manifest 规范，再逐步扩展具体 payload 格式。

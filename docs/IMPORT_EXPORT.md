# ProtoLink Import / Export Specification

Last updated: 2026-04-14

## 目标

导入导出为工作区中的正式资产提供稳定交换格式，覆盖：

- captures
- logs
- profiles
- release bundles
- portable / distribution / installer packages

## 基本原则

- 工作区目录是运行时事实源
- `exports/` 仅承担对外打包职责
- 所有导出/交付产物都必须带 manifest
- manifest 必须声明 `format_version`

## 当前导出规范

### 资产域
- `capture` -> `workspace/captures/`
- `log` -> `workspace/logs/`
- `profile` -> `workspace/profiles/`

### 导出 bundle

目录形态：

```text
workspace/exports/<timestamp>-<kind>-<name>/
```

最小内容：
- `manifest.json`
- 1 个主 payload 文件

## 当前交付层级

1. release bundle
2. portable package
3. distribution package
4. installer-staging package
5. installer package

## 当前 manifest 版本

- `protolink-export-v1`
- `protolink-release-bundle-v1`
- `protolink-portable-package-v1`
- `protolink-distribution-package-v1`
- `protolink-installer-staging-v1`
- `protolink-installer-package-v1`
- `protolink-install-receipt-v1`

## 工程要求

- 新增导出格式必须先定义 manifest 版本与校验规则
- 文件名必须经过规范化处理
- install / uninstall / verify 必须形成闭环
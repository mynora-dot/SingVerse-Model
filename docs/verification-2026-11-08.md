# 模型归档和发布检查 · 2026-11-08

## 本地检查

- 收集 6 个模型变体：HTDemucs、Intel OpenVINO、PANNs Cnn6、UVR ONNX、RK3566 FP16、RK3566 INT8。包括配置和 manifest 共 10 个锁定文件，合计 273,306,186 字节。
- HTDemucs / OpenVINO / PANNs 的字节大小与 SHA-256 和 SingVerse 的 `application/audio_catalog.py` 一致；UVR ONNX 与固定 sherpa-onnx 来源一致。两份 RKNN 从当日测试 NAS 只读取回并匹配测试记录摘要。
- `scripts/models.py validate --tag v0.1.0`、`fetch`（本地已有有效文件）、`verify`、真实权重打包与 `verify-release` 通过。测试产物使用占位提交摘要，正式附件由 tag 工作流写入其实际提交 SHA。
- Python 3.12 标准库测试 21 项通过：下载上限 / 摘要 / 失败清理 / 保留原文件，芯片目标，实验模型默认选择限制，包内容及路径，缺失附件，不可覆盖，确定性，外层重算摘要仍拒绝篡改模型，服务器上传不完整时不发布。
- Actionlint 1.7.12 检查两份 GitHub Actions 工作流通过。
- 使用 SingVerse 当前 `AudioModels.install` / `import_bundle` 在临时隔离目录实际导入上述三类管理端模型，均 `SUCCEEDED` 且 `model_valid` 为真；两份 RKNN 通过实际 `local_manifest` 校验。没有执行 GPU / NPU 推理，没有改变 NAS 服务或在线模型。

## 发布与硬件边界

tag 工作流的在线下载 / 上传结果以本仓库 Actions 与 Release 记录为准。工作流校验不代替模型推理、主观音质或其他芯片验收；RK3566 数值与性能范围单独记录于 [硬件实测](validation-rk3566-2026-11-08.md)。

INT8 质量未通过，不作为默认模型。INT4 无文件。RK3568 / RK3588 尚无本项目已验证模型，未把 RK3566 改名后分发。

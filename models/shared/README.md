# 共用模型

`htdemucs/` 用于 CPU、NVIDIA CUDA、AMD ROCm 和 Apple MPS；后端选择不改变这份权重。`panns-cnn6/` 是可选快速角色识别模型。

上游权重由 `python3 scripts/models.py fetch` 按锁文件补齐，Release 提供可直接导入的原始 `.th` / PANNs ZIP。`htdemucs.yaml` 保存在 Git 中，供手动预置完整 HTDemucs 目录时使用。

# 模型来源、许可和归属

本仓库的模型保留各自上游许可，不能把仓库脚本的许可当作全部模型的统一许可。模型名称、固定来源、字节大小和 SHA-256 以 `catalog/models.lock.json` 为准。Release 的 `MODEL-NOTICES.zip` 保存本文件与 `licenses/` 全部内容，下载和再分发模型时请一并保留。

## Demucs / HTDemucs

- 作者及版权：Meta Platforms, Inc. and affiliates；模型工作由 Alexandre Défossez、Simon Rouard、Francisco Massa 等贡献。
- 上游：[facebookresearch/demucs](https://github.com/facebookresearch/demucs)。权重为 `955717e8-8726e21a.th`，未经重新训练或量化。
- 上游声明 MIT，全文保存在 `licenses/Demucs-MIT.txt`，来源固定到 `e976d93ecc3865e5757426930257e200846a520a/LICENSE`。
- 参考：Rouard, Massa, Défossez, *Hybrid Transformers for Music Source Separation*, ICASSP 2023；Défossez, *Hybrid Spectrogram and Waveform Source Separation*, ISMIR 2021 Workshop on Music Source Separation。

## Intel demucs-openvino

- 作者 / 转换贡献：Intel 的 demucs-openvino 与 OpenVINO AI plugins for Audacity 项目；基础模型仍为 Demucs。
- 上游：[Intel/demucs-openvino](https://huggingface.co/Intel/demucs-openvino)，固定修订 `efb3d2bc54f93899b13b72b12c57001e19f09ae2`，仅 `htdemucs_v4/` 的 forward XML / BIN。
- 模型卡声明 MIT。原模型卡完整保存在 `licenses/Intel-demucs-openvino-MODEL-CARD.md`，保留引用和 Intel 人权声明；Demucs MIT 全文同时随附。
- 本仓库只打包固定原文件，不重新转换或改写 IR。

## PANNs Cnn6

- 作者：Qiuqiang Kong、Yin Cao、Turab Iqbal、Yuxuan Wang、Wenwu Wang、Mark D. Plumbley。
- 作品：*PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern Recognition (Pretrained Models)*。
- 来源：[Zenodo 3987831](https://zenodo.org/records/3987831)，DOI `10.5281/zenodo.3987831`；`Cnn6_mAP=0.343.pth`。
- 模型权重许可为 **CC BY 4.0**，以该 Zenodo 记录元数据为依据；许可链接及归属保存在 `licenses/PANNs-CC-BY-4.0.md`。这与 PANNs 推理代码的 MIT 许可是不同对象。
- 本仓库保留原始权重字节，仅增加外层 ZIP，未重新训练或量化。

## UVR MDXNET 9482 / sherpa-onnx / RKNN

- 感谢 Ultimate Vocal Remover（UVR）及其开发者 Anjok07、Aufr33 和模型贡献者；MDX-Net 原始代码由 Kuielab 与 Woosung Choi 开发，相关实现也有 KimberleyJSN 等贡献。
- 原始公开模型：[TRvlvr/model_repo 的 all_public_uvr_models](https://github.com/TRvlvr/model_repo/releases/tag/all_public_uvr_models)。本仓库 ONNX 文件来自 [k2-fsa/sherpa-onnx 的 source-separation-models](https://github.com/k2-fsa/sherpa-onnx/releases/tag/source-separation-models)，其发布说明将 UVR 来源和转换代码指向 `scripts/uvr_mdx`。
- UVR 当前 [README 许可段](https://github.com/Anjok07/ultimatevocalremovergui/blob/a5f88453bfb2b38b05a965bcf67727243e0cbf19/README.md#license) 声明 MIT，并要求第三方使用模型时注明 UVR 与开发者。`licenses/UVR-MIT.txt` 保存其历史完整 MIT 文本（版权 2022 Anjok07, Aufr33），来源为删除 LICENSE 前的修订 `0fd6b751dbbe9da9c96660d0b4ec2b07108727b7/LICENSE`；当前 README 的归属要求仍予保留。
- sherpa-onnx 转换贡献归 k2-fsa/sherpa-onnx 作者与贡献者；代码为 Apache-2.0，许可全文附于 `licenses/sherpa-onnx-Apache-2.0.txt`。本仓库使用该项目发布的固定 ONNX 原文件，不把代码许可改写为模型原创权属。
- RK3566 FP16 / INT8 是 SingVerse 以 Toolkit2 2.3.2 从同一 ONNX 转换的派生格式。`manifest.json` 保留目标、工具版本和源摘要；INT8 增加量化元数据。转换及质量边界见 `docs/validation-rk3566-2026-11-08.md`。转换不改变上游归属或许可。
- FP16 不量化；INT8 使用自备音频校准，音频和校准张量不包含在此仓库或下载包中。INT8 数值质量未通过，不建议用于用户歌曲。

## 不包含的组件

RKNN Toolkit2 / Lite2、驱动、`librknnrt.so`、FFmpeg、PyTorch、OpenVINO 运行环境及其他 SDK 不随模型包分发，按各自官方条款另行安装。用户歌曲、分离输出、校准数据、账号凭据和 NAS 配置均不在模型发行包中。

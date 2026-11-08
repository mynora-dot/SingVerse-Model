# 下载与安装

从 [SingVerse-Model Releases](https://github.com/mynora-dot/SingVerse-Model/releases) 选择一个版本，按设备下载附件，同时保存 `SHA256SUMS`、`model-catalog.json` 和 `MODEL-NOTICES.zip`。附件列表及状态见同一版本的 `RELEASE-NOTES.md`。不要把 GitHub 的 Source code 包当成完整模型包。

## 校验下载

`SHA256SUMS` 覆盖该版本全部下载附件（不包含它自身）。Linux 完整下载后执行 `sha256sum -c SHA256SUMS`；macOS 使用 `shasum -a 256 -c SHA256SUMS`。只下载部分模型时，提取对应的一行到临时校验文件再检查，例如：

```sh
rg '  htdemucs-openvino\.zip$' SHA256SUMS > selected.sha256
sha256sum -c selected.sha256
# macOS: shasum -a 256 -c selected.sha256
```

Windows PowerShell 可执行 `Get-FileHash .\htdemucs-openvino.zip -Algorithm SHA256`，与 `SHA256SUMS` 对应值比较。每个 ZIP 内部原文件的大小和 SHA-256 也记录在 `model-catalog.json`。

## CPU / CUDA / ROCm / MPS

下载 `955717e8-8726e21a.th`。在 SingVerse 管理端「设备与服务 → 性能节点配置」选择 `htdemucs`，导入该原始 `.th`；导入成功后对实际计算后端试跑。四类后端使用同一权重，不需要按 CPU 指令集、显卡品牌重复下载。

若手动预置目录，将原始权重和本仓库 `models/shared/htdemucs/htdemucs.yaml` 放入同一目录，配置节点的 `COMPUTE_AUDIO_MODEL_REPO` 指向它。配置文件内容须为 `models: ['955717e8']`，末尾换行。不要替换已经存在、内容不同的模型目录；先保留旧目录再安排停机切换。内存不足的 NAS 不会因为权重下载完成就具备 CPU 分离能力。

## Intel OpenVINO

下载 `htdemucs-openvino.zip`。管理端选择 `htdemucs-openvino` 后导入 ZIP。ZIP 根目录恰好只有 `htdemucs_fwd.xml` 和 `htdemucs_fwd.bin`，不要添加许可、说明或多套模型。两者必须来自同一锁定修订，随后对实际 Intel GPU 试跑。

手动预置时，解压到 `COMPUTE_AUDIO_MODEL_REPO` 同级的 `htdemucs-openvino/`。模型只是网络 forward 部分；STFT、拼接等仍由运行环境完成。

## 可选快速识别 PANNs

下载 `panns-cnn6.zip`。管理端选择 `panns-cnn6` 后导入；ZIP 根目录只有 `Cnn6_mAP=0.343.pth`。该模型用于快速音频角色识别，不做伴奏分离。手动预置目录为 `COMPUTE_AUDIO_MODEL_REPO` 同级的 `panns-cnn6/`。

## RK3566 NPU FP16（实验）

下载 `EXPERIMENTAL-uvr-mdxnet-9482-rk3566-fp16.zip`。当前 RKNN **只支持节点本地部署，不能从管理端网页导入**。解压后应只有 `uvr.rknn` 与 `manifest.json`，把它们放入节点 `COMPUTE_AUDIO_MODEL_REPO` 同级的 `uvr-mdxnet-9482-rknn/`。

使用与 Toolkit2 2.3.2 转换结果兼容的板端驱动、`librknnrt.so` 和 RKNN Lite2，按 SingVerse 的 RKNN 部署说明配置实际 NPU 设备、设备树和容器权限，再进行真实试跑。本版仅有 RK3566 隔离 CLI 证据，未完成正式管理服务接入。模型文件不会解决 BSP 或容器权限问题。

不要将 RK3566 编译文件部署到 RK3568 / RK3588。它们需要以对应 target 重新转换并验证；本版没有这些设备的合格 RKNN 文件。

## INT8 与 INT4

`EXPERIMENTAL-uvr-mdxnet-9482-rk3566-int8.zip` 是仅供研究的 W8A8 对照。相同 8 秒输入的伴奏相对 ONNX 参考 RMS 误差为 41.41%，未通过数值质量检查。不要把它解压覆盖 FP16 目录；需要比较时使用独立目录和显式 CLI。

RK3566 + Toolkit2 2.3.2 不支持本次 INT4 W4A16 配置，没有可下载的 INT4 文件。锁文件保留拒绝结果，不用 INT8 或 CPU 模型代替 INT4。

## UVR ONNX 参考与 VPU

`UVR_MDXNET_9482.onnx` 用于 SingVerse 独立 UVR CPU CLI 或离线 RKNN 转换。当前管理端 CPU 后端仍使用 HTDemucs；这个 ONNX 文件不能作为其导入文件。

VPU 视频硬件编解码不需要上述 AI 权重；应配置驱动、FFmpeg 和设备权限。模型包不含驱动、运行库或用户媒体。

各模型上游许可与作者归属见 `MODEL-NOTICES.zip`，请随模型保留。

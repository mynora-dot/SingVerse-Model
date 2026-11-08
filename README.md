# SingVerse-Model

SingVerse 的模型目录、离线下载包和设备选型说明。用户从 [Releases](https://github.com/mynora-dot/SingVerse-Model/releases) 下载附件；每个版本提供 `SHA256SUMS` 和包含文件摘要、来源、设备及验证状态的 `model-catalog.json`。

## 按设备选择

| 设备 / 用途 | 下载文件 | 安装方式 / 状态 |
| --- | --- | --- |
| x86_64 / ARM64 CPU | `955717e8-8726e21a.th` | 管理端选择 `htdemucs`，导入原始文件；需满足运行环境和内存预算 |
| NVIDIA CUDA | 同一份 `.th` | 使用 CUDA 计算环境，模型无需另下 |
| AMD ROCm | 同一份 `.th` | 使用受支持的 ROCm 计算环境，模型无需另下 |
| Apple Silicon MPS | 同一份 `.th` | 本机计算节点，模型无需另下 |
| Intel GPU OpenVINO | `htdemucs-openvino.zip` | 管理端选择 `htdemucs-openvino`，导入 ZIP |
| Rockchip RK3566 NPU FP16 | `EXPERIMENTAL-uvr-mdxnet-9482-rk3566-fp16.zip` | 解压到节点本地模型目录；隔离 CLI 已验证，正式服务接入仍待验证 |
| Rockchip RK3566 NPU INT8 | `EXPERIMENTAL-uvr-mdxnet-9482-rk3566-int8.zip` | 仅供量化研究；音质数值未通过，不建议安装 |
| ONNX CPU 对照 / RKNN 转换源 | `UVR_MDXNET_9482.onnx` | 独立 UVR CLI，不参与管理端后端自动选择 |
| 快速音频角色识别（可选） | `panns-cnn6.zip` | 管理端选择 `panns-cnn6`，导入 ZIP；不生成人声 / 伴奏 |
| RK3568 / RK3588 NPU | 本版没有已验证文件 | 须按目标芯片分别转换并在板端验证，见 [转换说明](conversion/README.md) |
| VPU 视频编解码 | 无需 AI 模型 | 配置驱动、FFmpeg 与硬件设备权限 |

详细安装与校验见 [下载说明](docs/downloads.md)。模型文件不能替代运行环境、驱动和设备试跑；相同权重也不代表所有设备都能运行。

## 目录

```text
catalog/models.lock.json                   固定来源、大小、SHA-256、设备映射
models/shared/htdemucs/                    CPU / CUDA / ROCm / MPS 共用权重
models/shared/panns-cnn6/                  可选快速识别权重
models/intel/openvino/htdemucs/            Intel IR 文件
models/portable/uvr-mdxnet-9482/            UVR ONNX 参考
models/rockchip/rk3566/fp16/                已实测的非量化 RKNN + manifest
models/experimental/rockchip/rk3566/int8/   质量未通过的 INT8 + manifest
conversion/                               固定版本转换脚本与环境说明
licenses/                                 上游许可和模型说明
docs/                                     安装及实测边界
```

所有已收集的权重保存在本地 `models/` 对应目录。上游大文件通过锁定地址下载并校验，不放入 Git 历史；两个 RK3566 RKNN 权重共约 29.7MB，与 manifest 一起存入 Git，确保 Release 使用经过板端对照的确切文件。clone 仓库后运行 `fetch` 可补齐其余权重。GitHub 自动生成的 Source code 包不含所有上游权重，用户应下载 Release 附件。

## 本地整理和打包

脚本仅使用 Python 3.11+ 标准库，不安装推理库，不加载或执行权重。

```sh
python3 scripts/models.py validate
python3 scripts/models.py fetch
python3 scripts/models.py verify
python3 -m unittest discover -s tests -v
python3 scripts/models.py build --tag v0.1.0 --revision "$(git rev-parse HEAD)" --output dist
python3 scripts/models.py verify-release --tag v0.1.0 --revision "$(git rev-parse HEAD)" --directory dist
```

`fetch` 只补缺失文件，已有文件大小或摘要不同会失败；临时文件校验后才安装。`build` 要求所有模型有效、tag 与 `VERSION` 完全一致、输出目录不存在；全部附件及校验通过后才生成最终目录。模型 ZIP 固定时间戳、文件顺序和权限，同一 tag、提交及输入可重现相同附件。

## 发布新版本

更新 `catalog/models.lock.json`、上游许可、实测记录和 `VERSION`，完成检查并提交后，创建对应的 **annotated tag**：

```sh
git push origin main
git tag -a v0.1.0 -m 'SingVerse models v0.1.0'
git push origin v0.1.0
```

[release-models.yml](.github/workflows/release-models.yml) 在 `v*` tag 推送时执行：校验 tag / 目录 → 测试 → 下载固定权重 → 核验所有摘要及 RKNN 目标 → 生成并复核附件 → 上传到草稿 Release → 校验服务器端附件 → 公开发布。只有发布任务持有 `contents: write`；不需要自建 token。普通分支 / PR 只执行检查，不发布。

已发布的 tag 和附件不覆盖，更新模型需新版本。若上传失败留下草稿，检查该草稿后删除未公开草稿再重跑；不要改动已公开的历史版本。首次 CI 通过表示下载与打包链路通过，不代表新增 GPU / NPU 真机验收。

## 已知边界

RK3566 FP16 在 2026-11-08 的隔离 CLI 上完成 112 秒歌曲分离，耗时约 662 秒；正式管理服务接入、主观音质仍待验证。INT8 虽将同一 8 秒输入的分离阶段从约 63.8 秒降至 49.4 秒，但伴奏相对 ONNX 参考的 RMS 误差约 41.41%，没有质量资格。当前 RK3566 + Toolkit2 2.3.2 拒绝 W4A16 配置，INT4 没有模型文件。详见 [RK3566 实测记录](docs/validation-rk3566-2026-11-08.md)。

上游权重保持原许可及归属，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本仓库只分发模型、必要配置和说明，不包含用户歌曲、校准音频、SDK、驱动或计算运行环境。

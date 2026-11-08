# 离线 RKNN 转换

Release 使用 `models/` 中已保存并锁定摘要的 RK3566 文件，不在发布时重新编译，以保留与板端数值对照完全一致的产物。

新增 RK3568 / RK3588 时，在独立、受 RKNN Toolkit2 支持的 Linux 转换环境准备 **Toolkit2 2.3.2**，下载已固定的 ONNX，分别指定目标：

```sh
python3 scripts/models.py fetch
python3 conversion/convert-rknn.py \
  models/portable/uvr-mdxnet-9482/UVR_MDXNET_9482.onnx \
  --target rk3568 --output /absolute/path/to/new-rk3568-model
```

支持的转换参数为 `rk3566`、`rk3568`、`rk3588`。转换前校验源模型 SHA-256；固定输入 `[1,4,2048,256]` 和输出 `output`，不量化。输出目录必须不存在，成功后才写 `uvr.rknn` 与 `manifest.json`。转换成功只表明生成了图，不能据此给予设备可用资格。

2026-11-08 验证过的 ARM64 / Python 3.12 转换环境为 Toolkit2 2.3.2、Torch 2.2.0、ONNX 1.16.1、NumPy 1.26.4、Protobuf 4.25.4、SciPy 1.13.1、OpenCV headless 4.10.0.84、setuptools 75.8.2；ToolKit 的 ARM64 Torch 要求与在线服务不同，需分开安装。此处是实测直接依赖记录，不是完整跨平台依赖锁；请按官方安装说明准备兼容环境，不在在线服务或网页请求中安装转换工具。

将新结果用于用户下载前，应在对应板卡核对驱动 / 运行库、实际 NPU 执行、CPU 算子边界、完整歌曲耗时、内存、时间轴及相对 ONNX 质量，记录模型摘要和验证范围。通过后把文件放入对应 target 目录，在锁文件增加独立模型项和设备映射，并使用新版本 tag 发布。不要改 RK3566 manifest 的 target 来伪造其他芯片产物。

本仓库 INT8 仅保存现有不合格对照模型；所用私有校准输入不分发，不能声明从公开仓库重建同一 INT8 文件。INT4 在本次 RK3566 / 2.3.2 环境被 SDK 明确拒绝，没有转换成功或性能证据。相关结果见 [实测记录](../docs/validation-rk3566-2026-11-08.md)。

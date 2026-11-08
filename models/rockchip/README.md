# Rockchip

`rk3566/fp16/` 保存已做隔离 CLI 实机对照的确切 RKNN 文件和 manifest；仍标为实验，因为正式服务接入尚未完成。INT8 对照位于 `models/experimental/rockchip/rk3566/int8/`，音质数值未通过。

RK3568 / RK3588 必须分别转换并在板端验证，本版不提供它们的合格 RKNN 文件。VPU 视频编解码不需要模型文件。

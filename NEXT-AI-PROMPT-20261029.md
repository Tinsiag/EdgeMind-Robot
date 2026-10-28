# 下一位 AI 提示词（2026-10-29）

你正在接手 `C:/Users/sc/Documents/Dev/Hardware/EdgeMind-Robot`。先读 `AGENTS.md`、`HANDOFF-20261029.md` 和本文件，再读两个运动审查目录的 `STATUS.json`、`TIMING-REVIEW.json`、`TFT-PAD-TIMING.json` 以及 `output/20261029-release-sha256.json`。

当前 FPGA 是断电状态；本轮没有烧录 A742/A743，没有 ARM，没有 VM，没有实车运动。不要因为 ZIP 或 PNR 通过就宣称自动避障已在车上完成。冷启动摄像头雪花问题仍留待后续，A741 显示恢复位流必须保留。

两个最终候选：

- 五秒顺序：`code/camera-car-control/a741-fpga-fusion/.local/gowin-basic-tft800-sequence-test/impl/pnr/a741.fs`，UserCode `0xA742`，SHA-256 `6c4cdbf7dd0d7b3dd4eff1e49d90cd2e91ff0c5d10580ba307657f898d95437e`。
- S1 自主避障：`code/camera-car-control/a741-fpga-fusion/.local/gowin-basic-tft800-button-autonomous/impl/pnr/a741.fs`，UserCode `0xA743`，SHA-256 `8bb2a55b64316265266d31831af6d3fc10583bb53cbf7291c38df016cd914710`。

交付 ZIP 和校验值见 `output/EdgeMind-Robot-motion-sequence-5s-final2-20261029.zip`、`output/EdgeMind-Robot-button-autonomous-avoidance-final2-20261029.zip`、`output/EdgeMind-Robot-display-recovery-final2-20261029.zip`。

代码要点：S1 是 A20、低有效；去抖要求上电先松键；S1 请求等待自动 IMU 静止校准，使用有界本地 250 ms 租约续租 LD06，二次按键停止；自主避障在前方和左右都堵时停车→200 ms 后倒车 300 ms→搜索侧向开口，最多 800 ms，无出口就停止。五秒序列每阶段 500 个 100 Hz tick，切换有 100 ms 零目标窗口。两种模式均保留 IMU、CPU、编码器、通信、雷达和 STOP 保护。

验证已完成：完整 WSL Verilator/RTL/主机回归通过，主机 41 项；两个最终 PNR setup/hold/recovery/removal 违例端点均 0；屏端 SDF 审查通过。实板测试尚未完成。

恢复实板时遵守：VM 关闭开始，先只读检查和 STOP；轮子架空；确认电机 PAD 没有物理 GND 锁；短时低速；再做 S1 避障。使用 `scripts/fpga/program_flash.py` 时记录位流路径、SHA、UserCode、状态轮询、真实日志和冷启动结果。不要烧录 A741 显示恢复位流以外的候选来“试试看”而不保留审计；不要覆盖历史交接记录。

# EdgeMind-Robot

当前工程是 [A745 片上自主避障](code/camera-car-control/a745-autonomous/README.md)。上电未 ARM，S1 本地启停，网口只发送遥测。摄像头初始化与采集、应用控制、网络发送和文字界面已重构。

- 使用与接线：[A745 说明](code/camera-car-control/a745-autonomous/README.md)。
- 当前状态、位流和烧录证据：[最新交接](HANDOFF-20261031.md)。
- 后续接手：[提示词](NEXT-AI-PROMPT-20261031.md)。
- 电脑只读遥测：`code/camera-car-control/launch.cmd`。
- FPGA 摄像头视频到 Lichee Pi 4A 的路线、运行教程和当前记录：[视觉视频链路交接](VISION-VIDEO-HANDOFF-20261031.md)。
- 机械设计：`model/chassis/v5-rgb-touch-display/`；电源板：`pcb/power/`；当前接线依据：`doc/电机/实物接线更正_2026-10-15.md`。

旧固件把电机输出锁为低电平的限制已在 A745 解除。这是内部逻辑锁，不是拆除公共地的指令。左轮 LAIN1/2 对应 FPGA A18/A19，右轮 RAIN1/2 对应 F13/F14；FPGA 与驱动板保持公共 GND。

项目清理已完成，删除18,685个旧文件，约15.92GB，当前源码和硬件设计保留。详见[清理记录](PROJECT-CLEANUP.md)。

用户已授权本次交接提交、推送 GitHub，并同步清理远端 main 当前目录；不关机。重新加载后的显示、真正断电冷启动、轮子运动和落地避障分别验收，具体结论见交接。

当前固化FW74506故障快照诊断版，Flash校验和被动健康通过；74505的前进/转弯已由用户确认，但落地ERR0001仍未解决。接手先读[当前交接](.agent/main/handoff.md)和[诊断字段](output/refactor-autonomous-20261030/imu-fault-20261031/DIAGNOSTICS.md)。本次修改尚未推送，上次[fw74504发布](output/releases/fw74504/manifest.json)为历史镜像。

## FPGA 摄像头视频与 Lichee Pi 4A

当前视觉链路保留 FPGA 原有 TFT、状态栏和运动安全逻辑。FPGA 从现有 800×480 显示像素流裁剪中心 640×480 RGB565，通过 UDP 6104 分片发送；Lichee Pi 4A 接收后转换为 MJPEG，由浏览器访问 TCP 8080 观看。原有 EMS1/EMF1/EML1 遥测继续使用原端口，视频不进入状态包。

Lichee Pi 4A 端运行：

```bash
cd /path/to/a745-autonomous/host
python3 -m pip install -r requirements-video.txt
python3 fpga_video_web.py
```

浏览器打开 `http://<lichee-ip>:8080/`。完整接线、IP、端口、分片格式、故障排查和后续 YOLO 路线见 [VISION-VIDEO-HANDOFF-20261031.md](VISION-VIDEO-HANDOFF-20261031.md)。

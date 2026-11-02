# EdgeMind-Robot

当前 FPGA 工程是 [A745 片上自主避障](code/camera-car-control/a745-autonomous/README.md)。上电未 ARM，S1 本地启停，网口发送视频和遥测。Lichee Pi 4A 接收摄像头画面，在 TH1520 NPU 上做目标检测并提供浏览器预览。

## FPGA 摄像头 → Lichee Pi 4A 实时识别（2026-11-02）

浏览器访问 **[http://192.168.40.101:8090/](http://192.168.40.101:8090/)**，可查看带目标框、类别和置信度的实时画面。

| 项目 | 当前配置 |
|---|---|
| FPGA 视频 | 640×480 RGB565，EV10 每行一个 UDP 包，端口 6104 |
| FPGA → 4A 有线链路 | 192.168.0.2 → end1 192.168.0.3 |
| 4A 远程连接及网页地址 | 192.168.40.101 |
| 推理后端与模型 | TH1520 NPU，量化 YOLOv5n，COCO 80 类 |
| 推理输入 | 640×384；等比缩至 512×384，左右各填充 64 像素 |
| 网页画面 | 640×480，目标 15 fps |
| 检测频率 | 目标 5 次/秒，独立于视频渲染 |
| 安装目录 | `/home/debian/fpga` |
| 服务 | 用户 systemd `fpga-video.service`，已启用开机启动及 linger |

本次修复了输入文件路径协议与二进制数据混用导致的进程死锁、YOLOv5 检测框解码及缩放映射错误，以及 Linux UDP 接收缓冲上限导致的丢包。增加了实际生效的超时、NPU 故障恢复和过期框隐藏。

最终连续 **60.078 秒**实测：摄像头 **29.76 fps**、网页 **14.95 fps**、识别 **4.98 次/秒**，完成 **299 次推理**；错误包、不完整帧、缺失行和推理错误均为零。另完成 7 项协议/图像测试、NPU 原始头独立解码比对，以及 NPU 卡住后的自动恢复验证。真实摄像头画面已显示人物识别框。

![真实 FPGA 摄像头经 4A NPU 识别的人物画面](output/vision-inference-20261102/live-verified.jpg)

在 4A 上管理服务：

```sh
cd /home/debian/fpga
sh start_video.sh 1 npu      # 视频和 NPU 识别
sh start_video.sh 0 npu      # 只看视频
systemctl --user status fpga-video.service
journalctl --user -u fpga-video.service -b -f
```

网页接口：`/video.mjpg` 为 MJPEG，`/snapshot.jpg` 为当前 JPEG，`/status.json` 为帧率、推理耗时、检测框和错误状态。

完整部署、构建、参数和排障说明见 [README-video.md](code/camera-car-control/a745-autonomous/host/README-video.md)；验证汇总见 [RESULT.json](output/vision-inference-20261102/RESULT.json)，原始监测见 [final-live-monitor.json](output/vision-inference-20261102/final-live-monitor.json)。

当前使用轻量目标检测模型，识别范围为 COCO 80 类；未完成标注集精度验收。新服务及驱动参数已持久化，**新配置的真实断电启动尚未实测**。本次没有编译/烧录 FPGA，没有发送运动指令。

## FPGA 与硬件资料

- 使用与接线：[A745 说明](code/camera-car-control/a745-autonomous/README.md)。
- 当前实板版本、位流及验收状态：[STATUS.json](output/refactor-autonomous-20261030/STATUS.json)。
- 历史交接：[HANDOFF-20261031.md](HANDOFF-20261031.md)；维护约定：[AGENTS.md](AGENTS.md)。
- 电脑只读遥测：`code/camera-car-control/launch.cmd`。
- 视频链路历史诊断：[VISION-VIDEO-HANDOFF-20261031.md](VISION-VIDEO-HANDOFF-20261031.md)，当前使用方法以上文及 README-video.md 为准。
- 机械设计：`model/chassis/v5-rgb-touch-display/`；电源板：`pcb/power/`。
- 当前接线依据：`doc/电机/实物接线更正_2026-10-15.md`。

左轮 LAIN1/2 对应 FPGA A18/A19，右轮 RAIN1/2 对应 F13/F14；FPGA 与驱动板保持公共 GND。4A 只接收视频，不通过网络 ARM、调速或清除运动故障。

项目清理已完成，删除 18,685 个旧文件，约 15.92 GB，当前源码和硬件设计保留。详见 [清理记录](PROJECT-CLEANUP.md)。

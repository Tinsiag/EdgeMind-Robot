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

## 最新状态（2026-11-01，覆盖本文旧视频说明）

FPGA 视频链路的现场故障已经定位：原来的共享 Ethernet 帧 FIFO 只有 512 字节，而 EV10 视频单个 Ethernet 帧约 1334 字节，帧 FIFO 会把超长视频帧丢弃；因此 UDP 6104 无视频包，而 UDP 6103 的 EMS1/EMF1/EML1 遥测仍可正常接收。

当前最后一次成功写入 Flash 的调试位流 SHA-256 为 `5085c51dee4d1d3a79c5c9124b67db34b5915da29756b1b11102861fdb5d6607`。Flash54、Reprogram、配置状态 `0x70022020` 和 UserCode `0xA745` 通过；该位流没有完成真实视频现场验收。后续视频 FIFO/分片修复候选仍有 PNR setup/hold 违例，禁止烧录违例位流。

Lichee Pi 4A 已配置有线 `end1=192.168.0.3/24`。视频服务安装在 `/home/debian/fpga`，服务名为 `fpga-video.service`。系统控制中心占用 TCP 8080，本项目视频/YOLO 服务使用 TCP 8090；浏览器地址为 `http://10.0.0.237:8090/`，状态接口为 `/status.json`，FPGA 视频端口仍为 UDP 6104。

Lichee 已安装 NumPy、OpenCV、Pillow 和 `shl-python`，并部署 YOLOv5n FP32 ONNX。TH1520 NPU 驱动模块/设备节点尚未出现；OpenCV CPU 推理会使板端过载，因此实时 YOLO 必须等待 HHB/SHL NPU 可执行模型和驱动验收。软件合成 EV10 测试帧已经通过分片重组、RGB565 转换和 MJPEG 输出验证；这不等于 FPGA 实时视频已验收。

软件链路最近一次合成 EV10 验收：frames=1、packets=686、bad_packets=0；测试帧来自开发机，不代表实板 UDP6104 已恢复。

## ��Ƶ UDP �� TH1520 NPU ��չ��2026-11-01��

��ǰ��Ƶ��·��������֤�ύ `49959551ad26e8011566e6acc13b46314c95b3e4` �ع������ύʹ�� `Gowin_PLL` �� 125 MHz ����ʱ�ӡ�`eth_mac_1g_fifo` �� `ethernet_udp_router`����ǰ A745 �� `axis_gmii_tx` �� UDP ������δͨ��ʵ����Ƶ���ա�

Lichee Pi 4A �� TH1520 NPU �����Ѽ���Ϊ `img_mem`��`vha`��`vha_info`���豸�ڵ�Ϊ `/dev/vha0`���ٷ� MBS ����������ʵ NPU ��ִ�У�Լ 1.45 ms��YOLOv5n ����ʹ�ÿ����� `F:\conda-env\test` ��ƥ��汾�� HHB/imgdnn ����ת��Ϊ MBS �� SHL ��ִ������ģ�͡�

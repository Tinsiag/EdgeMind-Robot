# EdgeMind-Robot

当前 FPGA 工程是 [A745 片上自主避障](code/camera-car-control/a745-autonomous/README.md)。上电未 ARM，S1 本地启停，网口发送视频和遥测。Lichee Pi 4A 接收摄像头画面，在 TH1520 NPU 上做目标检测并提供浏览器预览。

## 当前实板：FW74513 ED10 全模式显示（2026-11-03）

本轮固件保持 RGMII RX 接收，使 4A 回传的 ED10 推理框在模式1、模式2和模式3都可进入显示解析；ET10 运动任务仍独立限制为本地模式3、S1会话、有效传感器和安全联锁，模式1/2或未 ARM 网络包不能驱动电机。当前位流 SHA 为 `96626b87fb5afaff0b5052bd16e39145bf644bf20f786357bbfad5ebcf74ee16`，Flash写入校验、重载、`0x70022020`及UserCode `0xA745`核对通过，审计见 `code/camera-car-control/.local/programming/20261103T063008.029218Z/audit.json`。

4A `fpga-video.service` 已 active，NPU输入640×384、推理约5Hz、网页约15fps；模式1被动15秒收到150组状态，FPGA检测接受计数增加74、4A `display_sent`增加75（采样边界相差1包），期间74513/IDLE/ERR0000/未ARM/轮速为零。检测接收链路已验证，模式1/2屏幕绿色框仍需用户肉眼确认；没有电脑模拟S1或自动ARM。历史74511回退审计保留在[回退记录](output/rollback-74511-20261103/README.md)，当前源码和实板记录见 [AGENTS.md](AGENTS.md) 及本轮输出目录。

## FW74513 模式与寻物联调（2026-11-03）

FW74513已完成编译布线与Flash写入、校验、重载。S2/S3待机选择模式，数码管显示1绕障行驶、2原地一圈、3视觉寻物；S1启动/停止，S0复位停车。新增车体几何出口检查、局部四转绕行、有限视觉任务通道；原摄像头→4A NPU→FPGA检测框与HUD链路保留。网页支持COCO类别、预设颜色筛选和点击框锁定；标定未验证时不会把框大小当实测距离。

45秒被动监测：451组状态/姿态/任务状态，均74513、IDLE、ERR0000、未ARM、目标轮速零；视频29.76fps、推理4.98Hz、网页14.90fps，224次框回传被接收，无新增坏包/缺行。44项RTL、CPU及15项导航/任务/显示独立原语、协议/几何/回放和同次时序审核通过。

此前 RX 门控候选曾在模式1/2启动测试中出现 ERR0011/SRC37，记录保留在[故障记录](output/motion-task-20261103/startup-err0011/USER-REPORT.json)；本轮新位流已改为全模式保持 ED10 接收并重新烧录。当前模式1被动 ED10 接收已验证，模式2屏幕、运动和冷启动仍按实物范围单独验收；相机/雷达未标定，自动接近禁用。操作与边界见 [README-MODES-AND-TARGET-74513.md](code/camera-car-control/a745-autonomous/docs/README-MODES-AND-TARGET-74513.md)，最新证据见 [RESULT.json](output/detection-task-20261103/RESULT.json)。下文74512及此前视频验收为历史记录，不代替74513验收。

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

## 4A 检测框 → FPGA 屏幕（FW74512，已烧录验收）

4A 每次推理后将最多8个检测框通过 UDP6105 回传，FPGA 在本地摄像头视频上叠加绿色边框，
原状态参数 HUD 保持最上层。TFT 继续800×480/33MHz扫描，摄像头输出640×480，
NPU输入640×384、目标5次/秒，网页目标15fps。无结果或过期约1秒清框。
类别及置信度继续在网页显示；本地视频叠加最新结果，存在推理延迟。

部署与协议见 [README-video.md](code/camera-car-control/a745-autonomous/host/README-video.md)，
编译、烧录和实板联调结果见 [本轮证据](output/detection-display-20261102/README.md)。
FW74512 已完成外部 Flash 写入/校验和重载；用户已确认“有绿色框，参数文字正常”。
一分钟实测：600状态/600姿态健康、未ARM，接受检测结果298次，摄像头29.77fps、
推理4.98次/秒、网页14.92fps，无新增坏包/缺行。新位流真实断电冷启动尚未验证。
结果见 [RESULT.json](output/detection-display-20261102/RESULT.json)。

## FPGA 与硬件资料

- 布局布线优化与时序审核：[TIMING-CLOSURE.md](code/camera-car-control/a745-autonomous/docs/TIMING-CLOSURE.md)。
- 使用与接线：[A745 说明](code/camera-car-control/a745-autonomous/README.md)。
- 当前实板版本、位流及验收状态：[STATUS.json](output/refactor-autonomous-20261030/STATUS.json)。
- 历史交接：[HANDOFF-20261031.md](HANDOFF-20261031.md)；维护约定：[AGENTS.md](AGENTS.md)。
- 电脑只读遥测：`code/camera-car-control/launch.cmd`。
- 视频链路历史诊断：[VISION-VIDEO-HANDOFF-20261031.md](VISION-VIDEO-HANDOFF-20261031.md)，当前使用方法以上文及 README-video.md 为准。
- 机械设计：`model/chassis/v5-rgb-touch-display/`；电源板：`pcb/power/`。
- 当前接线依据：`doc/电机/实物接线更正_2026-10-15.md`。

左轮 LAIN1/2 对应 FPGA A18/A19，右轮 RAIN1/2 对应 F13/F14；FPGA 与驱动板保持公共 GND。4A 接收视频并回传仅用于显示的检测框，不通过网络 ARM、调速或清除运动故障。

项目清理已完成，删除 18,685 个旧文件，约 15.92 GB，当前源码和硬件设计保留。详见 [清理记录](PROJECT-CLEANUP.md)。

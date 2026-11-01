# CHANGE-74509 — EV10 视频链路修复与 sys_clk 时序收敛（2026-11-01）

本次目标：FPGA 摄像头画面经以太网送到 Lichee Pi 4A，4A 跑大模型识别并用浏览器
看实时带框画面。**视频部分已烧录并实板验收通过；4A 上的推理未打通。**

## 实板验收（2026-11-01）

已烧录。审计 `output/refactor-autonomous-20261030/flash/20261101T141334.568469Z/audit.json`：
写入+校验、Reprogram、74 只读就绪、73 版本比对全部通过，最终状态 `0x70022020`，
UserCode `0x0000A745`。

> 第一次烧录以 rc 50 在 0.01 秒失败，未写入任何内容。没有盲目重试：先用只读的
> `exFlash Detect ID`（op 51）确认 SPI flash 可达（Macronix `0xC22018`，状态
> `0x30020020`），再手动复现 op 54，第二次正常写入 56 秒。属于下载器接入后首次
> 操作的偶发失败，不是位流或 flash 问题。

4A 上实测视频链路：

```
packets 2,031,598   bad_packets 0   frames 2974   fps 28.6
UDP 6104 抓包：100,669 包全部 EV10、全部 1292 字节、行号 0..479 齐全
end1: errors 0  dropped 0
```

并两次从浏览器 MJPEG 流取下真实画面解码确认（640×480，构图正常、无错行，
两次场景不同，确认是实时流）。**旧版"有遥测、无视频"的问题已解决。**

访问地址 `http://10.0.0.237:8090/`（4A 的 wlan0）。当前以 `YOLO_ENABLE=0`
运行，只做视频。

## 推理未打通（已排查，非视频问题）

- `ShlExecutionProvider` 对 fp32 报 "not quantization"，CPU 回退路径 **SIGILL**。
- `yolov5n_int8.onnx` 是动态量化（`ConvInteger`），SHL 不认，本版 onnxruntime
  也 `NOT_IMPLEMENTED`。
- `yolov5n_th1520.mbs.bin` **文件损坏**：magic `65746548`，应为 `42beef42`。
- 开发机 `hhb.exe` 在但 `import hhb` 失败（`tvm.contrib` 缺 `graph_executor`）。
- CPU：640×640 fp32 单帧分钟级；换 320×320 后服务进程首次推理即静默消失
  （内存充足无 OOM，特征同 SIGILL）。

详见 `code/camera-car-control/a745-autonomous/host/README-video.md`。

## 交付物

| 项 | 值 |
|---|---|
| 位流 | `code/camera-car-control/a745-autonomous/.local/gowin-a745-autonomous/impl/pnr/a745.fs` |
| SHA-256 | `82affbef06d0e16d9959dbfd9822c8311873014bb0cf9586e4654dcf35845a02` |
| 大小 | 19,335,819 字节 |
| UserCode | `0x0000A745` |
| 固件版本号 | snapshot[159:128] = 74509 |
| 构建选项 | place_option=2, route_option=2（默认 1 时 DDR hold 有 5~6 个违例） |

## 时序签核

同一次 PNR/STA/SDF/PAD：

```
setup 0   hold 0   recovery 0   removal 0   max_delay 0
sys_clk 51.954MHz (约束50)   tx125m 140.969MHz (约束125)
display33m 65.028MHz (约束33)   ddr_ui100m 124.069MHz (约束100)
```

三个 SDF 审计均针对上述同一 SHA 通过：

- `audit_tx_sdf.py`：RGMII 最差绝对偏斜 **0.026ns**，裕量 **+0.239ns**（Table58 ±0.5ns，
  含 0.2ns PCB 预算与 0.035ns 不确定度）。时钟源已随 PLL 直出改为自 SDF 读取并断言六路同源。
- `audit_tft_sdf.py`：裕量 +2.440ns。
- `audit_camera_input.py`：通过。

## FPGA 改动

### 1. 以太网时钟（承接用户给出的结论）

`ODIV1_SEL` 原为 3（经 CLKDIV/2），用户要求改为 PLL 直出 125MHz。实际正确值为
**6**：VCO = 50 × MDIV(15) / IDIV(1) = 750MHz，750/6 = 125MHz。`ODIV1_SEL=7` 会得到
107.1MHz。同时 `timing.sdc` 的 `tx125m` 原写成 `-multiply_by 5`（250MHz），与实际
125MHz 不符，造成 **157 个虚假 setup 违例**；已改为 `-multiply_by 5 -divide_by 2`。

### 2. EV10 协议改为"一包一行"

旧实现按固定 896 字节分片、帧内像素计数，丢一包即整帧错位；且 IP 校验和与长度
不一致。新实现每个 UDP 包正好一行 640 像素 RGB565（以太网帧 1334 字节），头部携带
**绝对行号**，丢包只影响该行。IP 校验和由 localparam 在编译期计算，不再硬编码。

- `a745_video_capture_tx.v`：取中心 640×480，隔帧（FRAME_DIV=2，约 30fps / 18.3MB/s）。
  行首检查写侧余量，放不下整行就整行跳过并计数，FIFO 不会截断半行。
- `a745_video_udp_tx.v`：要求 `fifo_level>=640` 才起包，payload 不可能中途欠载。
- `a745_top.v`：**包锁定仲裁器**，遥测与视频只在帧边界换手，不会交织进同一以太网帧
  （旧版"有遥测、无视频"的原因之一是共享帧 FIFO 只有 1024 字节，装不下 1334 字节的
  视频帧而被整帧丢弃）。`axis_async_fifo` DEPTH 1024→2048。
- `async_fifo.v`：新增可选占用计数 `LEVELS` 参数。默认关闭——先前无条件启用会给
  DDR `ui_clk` 域增加寄存器，导致 hold 违例；现在只有视频 FIFO 启用。

### 3. sys_clk 时序收敛（本次关键）

构建后发现 sys_clk 有 16~18 个 setup 违例（TNS 最差 −14.087ns，Fmax 47.3MHz）。
关键路径与视频无关，完整落在导航逻辑：

```
sensors/heading/yaw -> autonomy/wrapped_delta -> turn_progress
-> turn_remaining/turn_reached -> target_l/target_r -> feedback/raw_l
```

两处等价变换（`a745_autonomy.v`）：

1. **turn_speed 打拍**。17 位钳位后寄存，数值与原 32 位表达式完全一致。
   `turn_reached`/`clearance_ok`/`motor_enable` 等安全联锁仍组合读取 `turn_progress`，
   **不增加任何延迟**；只有转弯速度幅值比陀螺仪晚 20ns，而它由 100Hz 控制 tick 采样。
2. **比较改在 16 位 wrapped_delta 上做**，避开 17 位取反进位链。右转时
   `turn_progress>=T` 恒等于 `wrapped_delta<=-T`，`turn_progress<-2731` 恒等于
   `wrapped_delta>2731`，**已对全部 65536×2×2 = 262144 种组合穷举验证完全一致**
   （含 −32768 半圈端点）。

结果：setup 违例 18 → **0**，Fmax 47.3 → 51.95MHz。

**一次被测试拦下的错误尝试**：曾把 `safe && clearance_ok` 也打拍，`autonomy_tb` 与
`reverse_escape_tb` 立刻报 "300mm boundary not gated immediately" / "front stop not
immediate"。该门控必须保持组合，已回退并加注释说明不要再改。

## 4A 主机侧（`host/`）

`fpga_video_yolo_web.py` 重写：三线程（UDP 组帧 / 推理 / 渲染）互不阻塞，推理只跑最新
整帧，慢推理不拖慢视频流。640×480 letterbox 到 640×640 送 YOLOv5n，输出框 + MJPEG。
新增 `ev10_test_sender.py` 可在无 FPGA 时自测。部署见 `host/README-video.md`。

开发机实测：合成 EV10 40 帧 / 19022 包，`bad_packets=0`、`frames=40`、`partial_frames=0`，
1% 丢行仍出完整帧；YOLOv5n 正确识别 4 个 person 与车辆，MJPEG 解出 640×480 带框图像。

## 验证工具变更

开发机原 `Ubuntu-26.04` WSL 发行版已不存在，`scripts/check.py` 无法运行。新增
`scripts/check_modelsim.py`，用 ModelSim 10.6d 跑同一套源码与 benchmark。

ModelSim 比 iverilog 严格，暴露出两处**前向引用**（变量先用后声明，Verilog-2001 与
SystemVerilog 均不合法）：`a745_video.v` 的 `av_sync`、`ld06_parser.v` 的 `span`。
已把声明移到使用之前，仅调整声明顺序，逻辑不变。

当前 **27 通过 / 3 失败**。3 个失败在改动前的 HEAD 基线上以完全相同的信息失败，
与本次改动无关：

- `bare_cpu_tb` — "bare CPU watchdog"
- `camera_tft800_tb` — 原本用 verilator `--binary --timing` 跑，ModelSim 下无输出
- `reverse_escape_tb` — "rear 351mm failed to allow reverse"

顺带修好两个陈旧测试（只改测试，不改 RTL，不影响位流）：
`encoder_diagnostic_tb` 仍断言版本号 74508（实际已是 74509）；
`attitude_filter_tb` 用了 ModelSim 10.6d 不支持的 `$abs`，改为局部 `rabs`。
两者修复后恢复为真实检查并通过。

## 未验证（重要）

- **位流未烧录**，实板未收到任何 EV10 包，4A 上未实跑本服务。
- 上述为器件模型与仿真结论，不是实测；PCB 偏斜未测。
- NPU 未接入，当前是 OpenCV CPU 推理（4A 上约 1~2fps），视频流本身 30fps。
- `HEAD`(ef0dce7) 本身无法综合：`a745_top.v` 传 `FRAME_PIXELS`，而该提交的
  `a745_video_udp_tx.v` 没有这个参数。故无法做"纯 HEAD"时序基线对比。

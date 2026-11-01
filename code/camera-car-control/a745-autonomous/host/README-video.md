# FPGA 摄像头 → Lichee Pi 4A → 浏览器实时识别

FPGA 采集 800×480 摄像头画面，裁出中心 640×480 窗口，经千兆以太网以 UDP
发到 Lichee Pi 4A；4A 组帧后用 MJPEG 把画面推到浏览器，并叠加 YOLO 检测框。

## 链路

```
OV5640 → a745_video(DDR3 缓冲) → a745_video_capture_tx（取中心 640×480，隔帧）
       → async_fifo(2048×28, display33m→sys_clk, LEVELS=1)
       → a745_video_udp_tx（每行一个 UDP 包）
       → 包锁定仲裁器 → axis_async_fifo → eth_mac_1g_fifo → RGMII 125 MHz
       → 4A end1 192.168.0.3  UDP 6104
       → fpga_video_yolo_web.py（组帧 + YOLO + MJPEG）→ 浏览器 8090
```

## EV10 包格式（`rtl/a745_video_udp_tx.v`）

每个 UDP 数据报正好一行 640 像素 RGB565，共 1334 字节以太网帧：

| 偏移 | 长度 | 内容 |
|---|---|---|
| 0 | 14 | 以太网头（广播 DA，SA 02:00:00:00:00:02，0x0800）|
| 14 | 20 | IPv4，总长 1320，192.168.0.2 → 192.168.0.3 |
| 34 | 8 | UDP，6104 → 6104，长度 1300，校验和 0 |
| 42 | 4 | 魔数 `EV10` |
| 46 | 4 | frame_id u32 LE |
| 50 | 2 | line u16 LE：图像绝对行号 0..479 |
| 52 | 2 | bytes u16 LE = 1280 |
| 54 | 1280 | 640 × RGB565 小端 |

行号是绝对行号，所以丢包只会让该行保持旧内容，不会让画面错位。

## 实板验收结果（2026-11-01）

位流 SHA-256 `82affbef06d0e16d9959dbfd9822c8311873014bb0cf9586e4654dcf35845a02`
烧录后（UserCode `0x0000A745`，配置状态 `0x70022020`），在 4A 上实测：

```
packets 2,031,598   bad_packets 0   frames 2974   fps 28.6
UDP 6104 抓包：100,669 包全部为 EV10，全部 1292 字节，行号 0..479 齐全
ip -s link 的 end1：errors 0  dropped 0
```

并已两次从浏览器流中取下真实画面解码确认（640×480，构图正常、无错行，
两次场景不同，确认是实时流而非缓存帧）。

**视频服务当前在跑**（纯视频，未开推理）：

```
http://10.0.0.237:8090/            网页
http://10.0.0.237:8090/video.mjpg  纯 MJPEG 流
http://10.0.0.237:8090/status.json 状态
```

走 4A 的 wlan0，局域网任意设备可访问；FPGA↔4A 是另一条网线
（192.168.0.2 → 192.168.0.3），互不影响。

开机不会自动拉起，重启后需手动执行：

```bash
ssh debian@10.0.0.237 'sh /home/debian/fpga/start_video.sh 0'
```

## 4A 端部署

```bash
scp fpga_video_yolo_web.py start_video.sh debian@<4A>:/home/debian/fpga/
ssh debian@<4A> 'sh /home/debian/fpga/start_video.sh 1 /home/debian/fpga/yolov5nu_320.onnx'
```

浏览器打开 `http://<4A地址>:8090/`，状态接口 `/status.json`。
（8080 已被系统控制中心占用，本服务固定用 8090。）
`start_video.sh <YOLO_ENABLE> <YOLO_MODEL>`；传 `0` 可只看视频不推理。

必须用 `venv-system/bin/python`（系统 numpy 1.24 + OpenCV 4.6 + onnxruntime 1.14）。
`venv/` 里没有 numpy。

服务内部三个线程互不阻塞：UDP 收包组帧、推理（只跑最新整帧）、渲染出 JPEG。
**推理慢不会拖慢视频流**，只是框会滞后。

### 不带 FPGA 自测

```bash
python3 ev10_test_sender.py --host 127.0.0.1 --image any.jpg --frames 40 --drop 0.01
curl -s localhost:8090/status.json
```

## NPU / 推理现状（未打通，视频不受影响）

`/dev/vha0` 存在，已 `chmod a+rw`。但四条路都断了：

- `ShlExecutionProvider` 对 fp32 模型报 *"current model is not quantization, use cpu
  install of npu"*，随后在 CPU 回退路径上 **SIGILL** 崩溃。
- `yolov5n_int8.onnx` 是动态量化（`ConvInteger`），SHL 不认，本版 onnxruntime 也
  `NOT_IMPLEMENTED: ConvInteger(10)`。
- `yolov5n_th1520.mbs.bin` **文件本身损坏**：`invalid magic number 65746548
  (expecting 42beef42)`，vendor `cnn_testbench` 拒绝加载。
- 开发机 `F:\conda-env\test\Scripts\hhb.exe` 存在，但 `import hhb` 失败
  （`tvm.contrib` 缺 `graph_executor`），无法重新编译 MBS。

CPU 推理同样不可用：

- `yolov5n_cpu_fp32.onnx` 640×640 在本板 onnxruntime 上是**分钟级**单帧，不可用。
- 换 `yolov5nu_320.onnx`（320×320、opset 12）后，服务进程在首次推理时**静默消失**，
  内存充足（15.8G 总 / 14.7G 空闲）、无 OOM 记录，特征与 onnxruntime CPU EP 的
  SIGILL 一致。

因此 **4A 上的实时识别尚未打通**，当前服务以 `YOLO_ENABLE=0` 运行，只做视频。
要恢复推理，需先修好 HHB/imgdnn 工具链生成合法 NPU 模型，或换一个在 RISC-V
上可用的推理运行时。

注意：在板子上跑多线程推理测速会把这块 4 核 RISC-V 压垮（出现过 ping 丢包 75%、
SSH 超时，最终需要手动重启）。后续测速请限制线程数并避开视频服务运行时段。

## 模型与后端（踩过的坑）

`Detector` 先试 onnxruntime，失败再退回 OpenCV DNN，并自动识别两种输出头：

- v5：`[1,N,85]`（cx,cy,w,h,obj + 80 类）
- v5u/v8：`[1,84,N]`（cx,cy,w,h + 80 类，无 objectness）

4A 上 **OpenCV 4.6 装不下**下列模型：

| 模型 | 问题 |
|---|---|
| 板上原 `yolov5n.onnx` | v5u/DFL 头，`model.24/dfl/Reshape` 报错 |
| 仓库 `yolov5n.onnx` | 权重是 **FLOAT16**，OpenCV 4.6 不支持（本机 4.8 可以，所以本地测试没暴露） |
| 仓库 `yolov5n_fp32.onnx` | 半成品：initializer 是 fp32，但图 I/O 和 18 个 Constant 仍是 fp16，onnxruntime 报 Conv 类型不一致 |
| `yolov5n_cpu_fp32.onnx`（`convert_onnx_fp16_to_fp32.py` 生成） | 类型一致了，但 opset 17 的 `Split`（split 走输入而非属性）OpenCV 4.6 仍解析不了；onnxruntime 可以 |

`yolov5nu_320.onnx`（ultralytics 导出，imgsz=320、opset 12、全 fp32，输出
`[1,84,2100]`）在**开发机**上实测正确：4 person + bus 0.54。板上则见上节。


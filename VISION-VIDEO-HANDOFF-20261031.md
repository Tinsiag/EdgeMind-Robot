# FPGA 摄像头视频到 Lichee Pi 4A 交接

更新时间：2026-10-31（Asia/Shanghai）

## 目标和边界

本次实现的第一阶段目标是：FPGA 继续负责摄像头采集、原有 TFT 状态显示和运动安全；FPGA 额外发送 640×480 RGB565 视频到 Lichee Pi 4A；Lichee Pi 4A 接收视频并提供浏览器预览。YOLO 人员/物体识别属于下一阶段，当前脚本只做接收和 MJPEG 网页展示。

Lichee 端只接收视频，不发送 ARM、速度、配置或故障清除命令。检测结果以后如需回到 FPGA，应增加独立的检测结果协议，不能复用运动控制入口。

## 已完成的 FPGA 修改

- `rtl/a745_video_capture_tx.v`：从现有 800×480 显示流裁剪中心 640×480。
- `rtl/a745_video_udp_tx.v`：UDP 6104 视频发送器，RGB565 分片，每片 1280 字节有效像素。
- `rtl/a745_top.v`：加入显示时钟到控制时钟的异步 FIFO，并把视频流接入现有 RGMII TX。
- 原有状态、姿态、雷达遥测和 TFT OSD 路径保持。

视频 UDP 负载格式：

```text
offset 0..3   ASCII EV10
offset 4..7   frame_id，小端
offset 8..9   packet_id，小端
offset 10..11 payload_size，小端
offset 12..   RGB565 像素数据
```

640×480 RGB565 一帧为 614400 字节，使用 1280 字节分片时约 480 个 UDP 包。FPGA 发送目标为现有广播网络，视频端口为 6104。

## Lichee Pi 4A 运行教程

将 FPGA 和 Lichee Pi 4A 接入同一千兆局域网。确认 Lichee 网卡已经获得地址，然后在 Lichee 上执行：

```bash
cd code/camera-car-control/a745-autonomous/host
python3 -m pip install -r requirements-video.txt
python3 fpga_video_web.py
```

脚本默认监听：

```text
UDP 6104：FPGA 视频
TCP 8080：浏览器 MJPEG 页面
```

浏览器访问：

```text
http://<lichee-pi-ip>:8080/
```

也可以先检查端口是否收到 UDP：

```bash
sudo tcpdump -ni any udp port 6104
```

脚本依赖 Pillow 将 RGB565 转换为 JPEG。若网页能打开但没有图像，先检查 `tcpdump` 是否有 UDP 6104，随后检查 Pillow、Lichee 防火墙和 FPGA/Lichee 是否处于同一网段。

## 规划路线

1. 先完成 FPGA 到 Lichee 的静态图案、真实摄像头帧和网页预览。
2. 测量实际帧率、丢包率、端到端延迟和 DDR/UDP 资源占用。
3. 在 Lichee 上加入轻量 YOLO 模型，先做人员识别，再加入需要的物体类别。
4. 将检测框和类别通过独立 UART 或 UDP 6105 返回 FPGA。
5. FPGA 只在 OSD 层叠加检测框，保留原 ARM/IMU/CAM、R/P/Y、F/L/R、MODE、NET、ERR 等信息。
6. 检测数据增加 frame_id、置信度和超时；结果过期时自动隐藏，不能影响原有运动安全逻辑。
7. 最后才评估视觉结果是否参与导航，任何运动目标仍必须经过 FPGA 安全状态机。

## 本次构建记录

本地执行：

```text
python code/camera-car-control/a745-autonomous/scripts/build.py prepare
python code/camera-car-control/a745-autonomous/scripts/build.py build --timeout 1800
```

结果：Gowin 综合和完整 build/PNR 通过；setup、hold、recovery、removal 统计为 0 违例。当前构建位流 SHA-256：

```text
2792eb24109e08e319fe90ff33ea712d2f13f0596a7bd17f4e2d6946e9ddf996
```

位流路径：`code/camera-car-control/a745-autonomous/.local/gowin-a745-autonomous/impl/pnr/a745.fs`。

该记录只证明本地构建完成。尚未完成实板烧录、FPGA-Lichee 实际视频接收、浏览器实图、稳定 30fps 测量和 YOLO 推理验收。没有得到这些实物证据前，不能把视频链路写成已完成现场验收。

## 当前已知限制

- 当前输出是中心裁剪的 640×480，尚未做完整 800×480 到 640×480 的缩放。
- 当前 Lichee 脚本只提供浏览器预览，不包含 YOLO。
- 视频和原有遥测共享 FPGA 以太网发送路径，需要实测确认 30fps 时遥测周期和丢包情况。
- UDP 没有重传，丢包时当前帧会被丢弃。
- 本次没有烧录 FPGA，也没有改变电机控制、ARM、故障联锁或网络控制边界。

# FPGA 视频接收与 Web 预览

Lichee Pi 4A 与 FPGA 通过同一局域网连接。FPGA 视频使用 UDP `6104`，网页服务使用 TCP `8090`（系统控制中心占用 8080）。

```bash
python3 -m pip install -r requirements-video.txt
python3 fpga_video_web.py
```

浏览器访问 `http://lichee-pi-ip:8090/`。视频格式为中心裁剪的 `640x480 RGB565`，网页服务转换为 MJPEG。

脚本只接收视频，不发送 ARM、速度或配置命令。丢失或不完整的帧会被丢弃。

## 当前状态（2026-11-01）

FPGA UDP6104 视频目前仍受共享帧 FIFO 超长丢弃问题影响，修复候选尚未通过完整 PNR 时序门，不能烧录。Lichee 使用 `end1=192.168.0.3/24`，服务由 `fpga-video.service` 管理，网页端口为 `8090`（8080 属于系统控制中心），地址为 `http://10.0.0.237:8090/`。

服务脚本 `fpga_video_yolo_web.py` 支持 frame_id、分片长度检查、RGB565 转换、MJPEG 和检测框输出。4A 已加载 `/dev/vha0`，并安装 `onnxruntime` 的 `ShlExecutionProvider`；`LD_LIBRARY_PATH=/usr/lib python` 可看到 `['ShlExecutionProvider', 'CPUExecutionProvider']`。服务会优先尝试 SHL/NPU 后端，失败才回退 OpenCV CPU。当前原始 FP32 YOLOv5n 会被运行库拒绝为非量化模型，必须提供量化 ONNX 或 HHB 生成的 MBS。

已验证真实 NPU 执行：

```bash
sudo /sbin/modprobe img_mem
sudo /sbin/modprobe vha onchipmem_phys_start=0xffe0001000 onchipmem_size=0x100000 freq_khz=792000
sudo /sbin/modprobe vha_info
sudo chmod a+rw /dev/vha0 /dev/vha_scope
python3 host/th1520_npu_infer.py \
  --model /usr/share/npu/test/resource/cnn_testbench/lenet/OCM_1M5/model.mbs.bin \
  --input /usr/share/npu/test/resource/cnn_testbench/lenet/m1.tensor.bin
```

该测试在 4A 上实际经过 VHA/NPU，网络执行约 1.45 ms。原始 FP32 YOLOv5n 不能直接作为 NPU 模型，转换工具 HHB/imgdnn 编译器不在当前系统中。

2026-11-01 ���£�FPGA ���緢����������֤�ύ `49959551ad26e8011566e6acc13b46314c95b3e4` �ָ� `eth_mac_1g_fifo + 125 MHz` ����ʱ�Ӽܹ���TH1520 NPU �ѳ��� `/dev/vha0`���ٷ� MBS ���� NPU ��ʵ��Լ 1.45 ms����ͨ FP32 ��̬���� ONNX ������Ϊ NPU ģ�ͣ�YOLOv5n �����ڿ����� `F:\conda-env\test` �о���ƥ�� HHB/imgdnn ת����

## 视频链路诊断记录（2026-11-01）

本次调查针对“Lichee Pi 4A 网页服务正常但收不到 FPGA 摄像头 UDP 视频”的问题。4A 网页服务、UDP 6104 监听和 Python 接收线程均可正常启动；轻量 UDP 监听脚本持续 8～10 秒的结果为 `packets=0`、`EV10=0`。4A `end1` 的 `rx_errors` 在旧位流下持续增加，原始二层抓包为 `total=0`，因此坏帧在 Linux UDP 层之前已经被 PHY/网卡丢弃。

已确认的 FPGA 错误有两项：

- 网络时钟路径错误。A745 原先使用 PLL 250 MHz 再经过 `CLKDIV/2` 得到 RGMII 125 MHz；已验证的旧提交使用 PLL 直接输出 125 MHz。当前已改为 `Gowin_PLL clkout1` 直接作为 MAC/RGMII 125 MHz，并移除网络时钟路径中的 `CLKDIV`。
- IPv4 校验和错误。视频 payload 改为 896 字节后，IP 总长度为 `0x03a8`，源地址 `192.168.0.2`，目的地址 `192.168.0.3`，正确 checksum 为 `0x75ef`；旧值 `0x756b` 已修正。

修正时钟后的位流已完成 PNR、Flash 写入、校验和重载：

```text
SHA-256: debabe9345cae64e4b39368358f0378a20e5cf5f0cf57845bf6bdb74d7a19b5c
UserCode: 0x0000A745
配置状态: 0x70022020
```

时钟修正后 4A 的 CRC/frame 错误不再继续增长，说明原先的 RGMII 时钟路径确实会产生坏帧。当前仍未收到合法 EV10 包，剩余排查边界为：`a741_phy_config` 是否发布 `phy_ready`、`eth_mac_1g_fifo` 的 TX enable 是否打开、`video_tx` 是否产生 valid，以及真实摄像头/显示 FIFO 是否产生视频 token。4A 网页服务和 UDP 监听已排除为首要根因。

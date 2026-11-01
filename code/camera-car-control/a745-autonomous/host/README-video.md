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

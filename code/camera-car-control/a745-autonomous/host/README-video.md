# FPGA 视频接收与 Web 预览

Lichee Pi 4A 与 FPGA 通过同一局域网连接。FPGA 视频使用 UDP `6104`，网页服务使用 TCP `8080`。

```bash
python3 -m pip install -r requirements-video.txt
python3 fpga_video_web.py
```

浏览器访问 `http://lichee-pi-ip:8080/`。视频格式为中心裁剪的 `640x480 RGB565`，网页服务转换为 MJPEG。

脚本只接收视频，不发送 ARM、速度或配置命令。丢失或不完整的帧会被丢弃。

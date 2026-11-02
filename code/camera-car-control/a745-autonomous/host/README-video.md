# FPGA 摄像头 → Lichee Pi 4A → 网页识别

## 当前已部署（2026-11-02）

浏览器打开 **http://192.168.40.101:8090/**。

- FPGA 发出 640×480 RGB565，EV10 每行一包，UDP 6104；4A 有线口 end1 为 192.168.0.3。
- 4A 在 TH1520 NPU 上运行量化 YOLOv5n，COCO 80 类，输入固定为 640×384。
- 原画面等比缩至 512×384，左右各填充 64 像素；检测框逆变换回 640×480。
- 网页目标 15 fps，检测目标 5 次/秒。推理、收包和 JPEG 渲染独立；超时或进程退出后恢复 NPU，过期两秒的框隐藏。
- `/video.mjpg` 为浏览器 MJPEG，`/snapshot.jpg` 为当前带框 JPEG，`/status.json` 为实时计数、耗时和错误。
- 安装目录 `/home/debian/fpga`，Python 使用 `venv-system/bin/python`。

本次读过的最近提交：`a48af99`（NPU 主机流程）、`0651fbf`（EV10 按行视频实板验证）、`ef0dce7`（链路诊断）、`14eb916`/`3f53f6f`（HHB 模型转换）。本次只修改 4A 主机软件及配置，没有编译/烧录 FPGA，也没有启动运动。

## 本次故障和修复

1. 旧 Python 给 daemon 标准输入写入约 2.95 MB tensor；实际 daemon 用 `fgets` 接收**输入文件路径**，随后自行读 float32 文件。双方堵在 pipe_write，`infer_runs=2` 不再增长。`npu_daemon.py` 改用内存文件路径协议，完整检查 TIME/DET/END，并对启动、请求、读取实施真实超时。
2. 旧 daemon 用 YOLOv3 的 exp 宽高公式解码 YOLOv5 原始头，造成重复/超大框。新源码 `yolov5_npu_daemon.c` 用 `(sigmoid*2-.5+grid)*stride` 和 `(sigmoid*2)^2*anchor`，按类别 NMS，直接加载现有合法的序列化 `npu/shl.hhb.bm`。旧测试图的 7 个 person 框修正为 3 个 person，另有 1 个 kite；独立 NumPy 解码逐框吻合。
3. 旧代码把 640×480 横向不变、纵向压成 384，又只对 y 逆缩放。现改为等比 letterbox 和 x/y 完整逆变换。
4. Linux 原有 `net.core.rmem_max=212992` 限制了 SO_RCVBUF，推理并发时收包溢出。安装 `fpga-video-sysctl.conf` 后请求 16 MiB，内核报告 32 MiB（Linux 双倍计账），视频恢复约 30 fps。
5. 视频关闭模式不再初始化 NPU；使用 systemd 管理整个进程组，替代可能杀到无关进程的端口 fuser 清理。

## 运行与日志

```sh
cd /home/debian/fpga
sh start_video.sh 1 npu       # 视频和 NPU 检测；保存配置并重启服务
sh start_video.sh 0 npu       # 只看视频，不初始化 NPU
systemctl --user status fpga-video.service
journalctl --user -u fpga-video.service -b -f
curl -s localhost:8090/status.json
```

用户服务已启用，debian 的 linger 已启用，退出 SSH 后持续运行。配置 `video.env` 由启动脚本写入；额外模型/阈值/限帧配置可写入该 EnvironmentFile。默认置信度 0.30、NMS 0.45。CPU 后端仍为历史诊断入口，本板不建议使用，未宣称解决旧 CPU ONNX SIGILL。

NPU 驱动的持久化参数在 `/etc/modprobe.d/fpga-npu.conf`，启动模块清单在 `/etc/modules-load.d/fpga-npu.conf`；当前运行时已确认 1 MiB OCM 和 792 MHz。接收缓冲设置在 `/etc/sysctl.d/90-fpga-video.conf`。本次没有重启 4A，故这些新配置的真实断电启动仍未实测。

## 重建与部署

源码和配置从本 host 目录复制到 `/home/debian/fpga/`。保留已有 `venv-system`、`npu/shl.hhb.bm` 和匹配的 SHL 2.4.5 运行库，执行：

```sh
cd /home/debian/fpga
sh build_npu_daemon.sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 ./venv-system/bin/python -m unittest -v test_video_npu.py
sh start_video.sh 1 npu
```

构建脚本使用板上 `/home/debian/shl-c920/c920/include` 的兼容 CSI-NN 头文件、GCC rv64gc 和 `libshl_th1520.so.2`；可用 `CSINN_INCLUDE` 指定匹配头文件路径。不要把不同模型的 anchors/类别/输出头直接套入该固定 YOLOv5n 解码器。

首次配置接收缓冲和驱动持久化时，以管理员身份将提供的 `fpga-video-sysctl.conf`、`fpga-npu.conf` 分别安装到上述 `/etc` 位置，并应用 `sysctl -p /etc/sysctl.d/90-fpga-video.conf`。驱动若已加载且缺 OCM，仅在停止所有 NPU 使用者后执行已有 `npu_reload.sh`；运行中不能卸载。

开发机的 `lpi4a_run.py` / `lpi4a_put.py` 默认地址已更新为 `192.168.40.101`；支持 `LPI4A_HOST`、`LPI4A_USER`、`LPI4A_PASSWORD` 环境变量。

## 验证证据与限制

证据在仓库根 `output/vision-inference-20261102/`：7 项协议/超时/图像变换测试、真实 NPU 的独立解码对照、真实 FPGA 视频与网页快照、连续状态采样和 NPU 卡住恢复试验。以 `RESULT.json` 汇总的最终实测为准。

识别属于轻量 YOLO 目标检测。COCO 80 类之外物体不能据此保证识别；容器被标为 cup、低分误检或未检出仍可能出现，没有标注集精度验收。本次没有更换权重、重训模型或宣称任意物体识别能力。

4A 只收视频，不发送 ARM、速度、配置或故障清除指令；不把视觉结果接入运动控制。当前 FPGA 运动版本与验收继续以原 STATUS.json 为准。

## EV10 UDP 负载

| 偏移 | 长度 | 内容 |
|---|---|---|
| 0 | 4 | ASCII EV10 |
| 4 | 4 | frame_id，u32 LE |
| 8 | 2 | line，u16 LE，0..479 |
| 10 | 2 | payload bytes，u16 LE，1280 |
| 12 | 1280 | 640 个 RGB565 小端像素 |

每包一行，完整一帧 480 包。接收器保留 95% 行数发布门槛，丢失行保持旧内容；最终正常监测期间无需依赖此容错。

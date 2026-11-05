# 4A 视频、NPU 与视觉任务

FPGA 向 Lichee Pi 4A 发送摄像头视频，4A 运行量化 YOLOv5n、提供网页，并回传检测框。
FW74513 还支持本地模式3的有限视觉任务。当前固件及验收以[项目状态](../../../../docs/project-status.md)为准；下面的地址和部署状态最后核实于2026-11-03，本轮资料整理未连接4A。

## 使用

最后部署地址为 **http://192.168.40.101:8090/**，服务目录 `/home/debian/fpga`，Python 为 `venv-system/bin/python`。

```sh
cd /home/debian/fpga
sh start_video.sh 1 npu
systemctl --user status fpga-video.service
journalctl --user -u fpga-video.service -b -f
curl -s localhost:8090/status.json
```

`sh start_video.sh 0 npu` 切换为纯视频，不初始化 NPU。启动脚本写入 `video.env` 并重启用户服务；已有 linger 让退出 SSH 后服务继续运行。
`/video.mjpg` 为实时 MJPEG，`/snapshot.jpg` 为当前 JPEG，`/status.json` 提供计数、耗时和错误。

网页支持 COCO 类别选择、HSV 预设颜色筛选、点击框锁定以及 `follow`/`search` 任务。颜色筛选依赖 OpenCV，不等于任意物体的语义颜色识别。
跟随模式未锁定框不发运动；丢目标、旧帧或 FPGA 状态异常会撤销动作。
相机/雷达标定默认 `verified=false`，目标雷达可观测性也未验证，**自动接近和到达判定保持禁用**。
按键与任务限制见[三种模式](../docs/README-MODES-AND-TARGET-74513.md)。网页不能 ARM，任务仅在本地模式3由 S1 建立会话后才可能驱动电机。

## 图像与推理

| 环节 | 配置 |
| --- | --- |
| FPGA→4A | 640×480 RGB565，EV10 UDP6104，每行一包 |
| NPU | TH1520、量化 YOLOv5n、COCO80类，640×384输入，目标5Hz |
| 输入变换 | 原画面等比缩至512×384，左右各64灰边，检测框完整逆映射 |
| 网页 | 目标15fps，收包、推理和JPEG渲染独立 |
| 4A→TFT | ED10 UDP6105，最多8框；无检测发送空结果 |

NPU daemon 通过输入文件路径读取 tensor，Python 对启动、请求和读回实施超时，异常后恢复。
解码使用 YOLOv5 的 sigmoid 平方宽高公式与按类 NMS；不要套用 YOLOv3 的 exp 宽高或其他模型头。
固定序列化模型在 [npu/shl.hhb.bm](npu/shl.hhb.bm)，来源及哈希见[模型说明](npu/README.md)。
这不是通用多模态模型，COCO之外类别与检测准确率未做标注集验收。

## 重建与部署

将本 `host/` 源码和配置部署到 `/home/debian/fpga/`，包括 `npu/shl.hhb.bm`；保留板上已有 `venv-system`、匹配的 SHL 2.4.5 运行库及驱动。

```sh
cd /home/debian/fpga
sh build_npu_daemon.sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 ./venv-system/bin/python -m unittest -v test_video_npu.py
sh start_video.sh 1 npu
```

构建脚本使用板上 `/home/debian/shl-c920/c920/include`、GCC rv64gc 和 `libshl_th1520.so.2`；可用 `CSINN_INCLUDE` 指定兼容头文件。
4A 使用系统 OpenCV/Pillow 等依赖，开发机依赖文件不用于覆盖板上系统库。
本地 `lpi4a_run.py` / `lpi4a_put.py` 支持 `LPI4A_HOST`、`LPI4A_USER` 和 `LPI4A_PASSWORD` 环境变量；凭据不得写入仓库。

接收缓冲配置 `fpga-video-sysctl.conf` 对应 `/etc/sysctl.d/90-fpga-video.conf`；申请16MiB，Linux socket统计会双倍计账。
驱动配置 `fpga-npu.conf` 对应 `/etc/modprobe.d/` 和 `/etc/modules-load.d/`。最后观察为 OCM1MiB、792MHz，4A真实断电启动仍未验收。
驱动已加载且缺 OCM 时，只能停止所有 NPU 使用者后运行 `npu_reload.sh`，不能运行中卸载。

## 网口与协议

固定有线链路：FPGA `192.168.0.2` / `02:00:00:00:00:02`，4A end1 `192.168.0.3` / `48:da:35:60:00:99`。
FPGA 不应答 ARP，需启用提供的静态邻居配置。更换网卡必须同步接收端限定源 MAC。

```sh
sudo install -m 644 fpga-detection-neighbor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fpga-detection-neighbor.service
sudo install -m 755 fpga-detection-neighbor-dispatcher /etc/NetworkManager/dispatcher.d/90-fpga-detection-neighbor
```

`FPGA_DETECTION_RETURN=0` 禁用检测回传。
EV10 每包负载为12字节头加1280字节像素：魔数4字节、frame_id(u32 LE)、line(u16 LE)、payload bytes(u16 LE)，随后640个小端RGB565像素。480行组成一帧，收包器保留95%行数发布门槛，缺行沿用旧内容。
ED10固定16字节头及每框12字节坐标/类别/分数，具体编解码由 `detection_return.py` 和对应RTL/测试共同维护。

模式1/2/3均接收 ED10，显示域场消隐原子更新，约1秒过期清框。640×480框映射到本地800×480画面的x+80，HUD置顶；最新框叠实时画面，有推理延迟，不是逐帧锁定。
ET10是独立的UDP6106有限动作协议，要求本地模式3、S1会话、新鲜视频/观测和全部传感器/几何保护。整个RX不再与电机结构隔离；ED10框数据的隔离和共享接收流控的限制见模式说明。

## 证据边界

当前记录汇总在[当前固件证据](../../../../output/current-firmware/README.md)。模式1被动接收计数增长证明链路接收，不能替代模式1/2实屏绿色框、冷启动或模式3运动验收。
此前74512绿色框实屏和74511直行验收不转用于当前SHA。当前标定和寻物到达仍未完成。

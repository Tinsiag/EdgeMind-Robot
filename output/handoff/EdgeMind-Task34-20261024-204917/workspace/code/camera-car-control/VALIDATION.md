# 验证记录

验证日期：2026-10-19。A740 已由用户完成实板运行；本次用户运行摘要见 [实板运行摘要](verification-2026-10-19-user-run.md)。时序尚未闭合，详见 [编译记录](BUILD-2026-10-19.md)。

## README交接复核

本次提交前重新运行：50项运动Python测试、19项融合非GUI测试通过，109个本地Markdown链接检查通过。GUI全量测试此次未正常结束，已终止测试进程，未关闭用户运行中的上位机；不把历史22项通过记录当成本轮GUI复验结果。本次只完善交接文档、归档完整性和提交既有工作，没有执行硬件动作或重新编译位流。

## 已通过

以下测试数量为各阶段留存记录：首版全量5项RTL、后续PI单用例、Python回归分别执行，未完成当前PI修改版的全量RTL复验。A740同User Code存在不同构建，当前归档哈希见release；实板日志未独立证明具体新版哈希。最新待办及234 mm标定见 [当前状态](CURRENT-STATUS.md)。

- Gowin V1.9.12.04完整综合、布局布线、位流生成，输入哈希未变化。全部47个端口的最终球号与CST一致。
- 上位机22项Python测试：UDP/TCP/UART、EMC1会话/序号/CRC、取消与停车、能力探测、EMV1完整帧和坏帧组装、RGB565、UDP loopback、Tk布局和模拟运动。
- 原运动上位机50项Python回归测试，保留右桥修正识别及平滑共同减速行为。
- `board_platform_tb`：实际254项ROM写入、0x5640 ID、9项配置回读，错误ID或测试图案设置拒绝启动。使用事务级SCCB模型，未验证电气波形。
- `camera_ethernet_core_tb`：带输出反压的Ethernet入口/出口，ARP及IPv4/UDP校验和、EMC1回复、ARM/目标轮速/STOP生效、旧序号/异会话/错CRC/错端口/错IP拒绝。Python独立解码回复和一帧DVP视频。
- `camera_motion_core_tb`：DVP/FIFO/EMV1、坏帧、UART能力/状态回复、空闲无PWM。
- `rgmii_rx_tb`：Gowin官方IDDR模型验证半字节顺序、DV/ER、连续字节对齐。
- `video_udp_packetizer_tb`：同步RAM预取、分包、反压、正常/坏/截断帧，并由主机接收器交叉验证像素内容。

GUI停车测试等待已更新的界面遥测和界面idle事件，避免后台已空闲但Tk尚未刷新时误判；实际控制行为未因此改变。最终22项全量测试通过。

## 实板运行结果

用户确认网口控制连接成功，前进、后退、左转、右转和停止均有实际动作。多次短距离动作完成；部分长动作出现 `faults=4` 无反馈保护，另有串口回复超时。后续应检查编码器线缆/接插件，并继续标定减速参数。

## 未完成

- 时序签核：当前归档3项setup、27项hold端点违例；首版为3/26。包含异步FIFO/复位路径和RGMII输入hold，详细数值以对应归档报告为准。
- RGMII双沿I/O延迟是初始预算，尚无实测，输出时序和PHY延迟设置未确认；仅支持1Gbps协商。
- 没有运行MAC完整FCS线速回环或真实PHY链路验证。完整网络仿真以无前导/FCS的Ethernet AXI帧为边界；RGMII单独验证。
- 用户已有实车运行反馈；持续收图吞吐/丢帧、距离和角度精度未量化验收。模拟模式和RTL小尺寸红色图像不代表实机性能。

## 复现

```powershell
.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s tests -p 'test_*.py' -v
.venv/Scripts/python.exe -X utf8 -B scripts/run_rtl_tests.py
python -X utf8 -B scripts/build_fpga.py build
python -X utf8 -B scripts/package_firmware.py
```

原厂依赖首次用 `scripts/prepare_platform.py` 导入。工具路径默认匹配本机安装，可通过脚本参数覆盖；RGMII测试默认使用本机Gowin `simlib/gw5a/prim_sim.v`。

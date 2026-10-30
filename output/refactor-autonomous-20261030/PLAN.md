# 2026-10-30 全面重构现场

> 历史起始计划。此处的旧位流、备份目录和GND未知记录均已被后续开发、清理和实板验收替代，不作为当前执行指令。最新现场读根目录AGENTS.md/HANDOFF-20261031.md及本目录STATUS.json；2026-10-31转弯需求见TURNING-PLAN-74504.json。

用户明确要求全部重构，以旧工程与原厂例程作参考。原目标仍为修复摄像头显示在重新烧录/冷启动两种路径下的稳定性、片上 S1 自主避障、网口只传数据、移除活动工程的网络控制与多余分支，并在验证后直接烧录。不上传 GitHub、不关机。

## 已确认
- 当前 A744 最后烧录 SHA 8761b83aae4cf6d2e448599b9c0a4d27e15ac70118fa643944b0cf44635030ec，0xA744；真实审计 code/camera-car-control/.local/programming/20261029T134248.547289Z/audit.json。
- 用户现时确认 FPGA/屏幕/下载器已通电连接、VM 关闭、轮子架空；电机物理 GND 锁未知。可以在 VM 关闭时烧录；不能启动运动。
- 文字正常，只有摄像头区域雪花/错乱。实际生成 A744 顶层 LED 为 D0 时钟锁/D1 camera_ready/D2 PHY/D3 DDR/D4 frame_available/D5视频DDR错/D6溢出/D7电机故障；用户报告仅 D0 D2 D3 亮。摄像头 init 未就绪，不能沿用旧 screen-test 灯位。
- 被动监听 192.168.0.3:6103 八秒没有包，没有发送任何命令；记录 output/display-autonomous-fix-20261030/INITIAL-TELEMETRY.json。
- 用户原有未提交代码已备份到 output/display-autonomous-fix-20261030/before，保留全部原工作树变更，不 reset/clean。

## 实施结构
- 新活动主工程 code/camera-car-control/a745-autonomous；A741/A744 保留作历史参考，不混合烧录证据。
- 单一 S1 片上自主避障人格：上电未 ARM、松键后新按键请求、二次按键停止；保留 IMU/编码器/雷达/CPU/STOP 联锁。
- 新摄像头初始化序列、单总线控制权、硬复位/完整等待/有界重试/关键寄存器回读与可见诊断。优先参考官方第45章 TFT 摄像头例程及第47章 RGB 表，保留 TY-OV5640 P7 已验证接法（自带晶振），不用官方 P4 的 XCLK/引脚覆盖当前接线。
- 视频只接收完整有效 RGB565 帧；DVP 输入寄存器与帧边界、冷启动、热复位、坏帧恢复都必须测试。面板继续800x480/33MHz，AB22 DE/AB21 BL 不改。
- Ethernet 单向广播 UDP 遥测，删除活动工程的命令解析、配置/ARM/雷达控制和 PC 发指令入口；不让链路状态影响本地运动。仅保留 TX 与必要 PHY 配置，缩小综合网表和跨域/高扇出。
- 原厂加密 DDR IP、PLL 及经过验证的底层驱动作为库复用；应用顶层、初始化/会话、网络和主机入口重新组织，单一 filelist，无历史人格宏堆叠。

## 验证/交付
1. 离线故障注入及 RTL/主机测试，保留真实输入 SHA。
2. 综合资源/时钟/高扇出检查后，算法1/布局1/timing-driven/hold完整PNR；同次STA/SDF、动态电机PAD与输出时序审查。
3. 核对路径/SHA/UserCode，VM保持关闭，program_flash.py 操作54@0、校验、Reprogram、只读就绪与UserCode核对。
4. 用户观察摄像头与文字，真正完全断电复测单独记。物理 GND 锁未知，不 ARM/不运动。

# A745 摄像头与片上自主避障

当前入口为 [a745-autonomous/README.md](a745-autonomous/README.md)。运行本目录 `launch.cmd` 打开只读遥测窗口；车辆只通过FPGA上的S1启停，S0复位急停，网口没有运动控制接收路径。

A745已重构摄像头启动、完整帧采集、本地自主会话、UDP发送和屏幕状态栏。真实状态、位流SHA和实物验收见 [交接](../../HANDOFF-20261031.md)；运行方法与当前引脚见新工程说明。

目录维护范围：`a745-autonomous/` 当前源码、`third_party/verilog-ethernet/` 三个TX相关库文件及许可、`.venv/` 运行环境、此入口和launch.cmd。旧工程、备份和历史产物已按用户要求删除，清理及保留校验记录见根目录PROJECT-CLEANUP.md。
# 当前接手补充（2026-11-01）

视频链路当前仍以根目录 `README.md`、`VISION-VIDEO-HANDOFF-20261031.md` 和 `code/camera-car-control/a745-autonomous/host/README-video.md` 的最新状态为准。Lichee 网页服务使用 `http://192.168.40.101:8090/`，UDP 视频端口为 `6104`；系统控制中心占用 `8080`。当前 FW74513 位流已完成完整时序签核并烧录，模式1 ED10接收已通过被动计数验证；模式2屏幕观察和模式3运动仍需实体验收。

# 代码目录

- [ACG720 / AT8236 电机控制](fpga/acg720-motor-test/README.md)：A712 启动和编码器活动、A713 左右持续启停已实测通过；当前 A717 为 50 kHz，占空比从 0% 到 100% 每 0.5 秒增加 5% 后循环，已下载，实物表现待反馈。S1/S2 独立启停，S0 停止，仅操作 SRAM。
- [电机启动排查与实现文档](fpga/acg720-motor-test/MOTOR-IMPLEMENTATION-2026-10-10.md)：接线、电源、三个 PWM 对照版本、通过证据及复现方法；尚未实现速度 PID 或与摄像头合并。
- [ACG720 GW5AT-60 DDR3 验证工程](fpga/acg720-ddr3/README.md)：原有 800×480 静态、彩条、实景单帧验证均通过。另已合入 [实景 HDMI 交付包](fpga/acg720-ddr3/verification/verified-20261008/README.md)，包含位流、实物反馈与完整验证资料；有图像显示反馈，时序尚未闭合，包内未提供完整 RTL。许可证已解决。
- [DDR3 帧缓存排查与实现文档](fpga/acg720-ddr3/DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md)：旧诊断缺陷、时钟与缓存实现、摄像头配置、仿真/实板证据、复现步骤和断电保存边界。

原厂配套源码、加密 IP 和位流保留在工程的 `.local/` 中，不直接并入公开仓库。我们编写的说明和构建入口纳入版本管理。

# EdgeMind-Robot

基于 ACG720 FPGA 的自主移动机器人项目。当前底盘概念采用两台 MG513X 驱动后轮、两只前万向轮支撑的四轮结构，左右后轮差速转向。目标是先完成轮速闭环、传感器感知、视频链路与安全保护，再按需要扩展 Lichee Pi 4A 视觉计算。

## 文档与设计

- [项目功能需求书](doc/项目功能需求书.md)
- [系统设计文档](doc/文档.md)
- [电源预算与电源板架构初稿](doc/电源板/电源预算与架构初稿.md)
- [拟用电机资料核对](doc/电机/拟用电机资料核对.md)
- [FPGA 资料索引](doc/fpga/README.md)
- [代码目录](code/README.md)（含 ACG720 摄像头、DDR3 和电机工程入口与联调记录）
- [ACG720 双轮运动控制工程](code/fpga/acg720-motion-control/README.md)（编码器闭环、差速运动、定点旋转、CH340E Type-C 串口和 Python CLI；数字验证通过，实车标定待完成）
- [OV5640 与 DDR3 帧缓存排查及实现](code/fpga/acg720-ddr3/DDR3-FRAMEBUFFER-IMPLEMENTATION-2026-10-08.md)（800×480 静态、彩条、实景单帧链路通过）
- [DDR3 实景 HDMI 固件与验证资料](code/fpga/acg720-ddr3/verification/verified-20261008/README.md)（导入位流、实景显示反馈、照片与构建报告；完整时序尚未闭合）
- [硬件机械模型与参考图](model/README.md)（电源驱动板、荔枝派、MG513X、ACX720 V2/V3；含 STEP、DWG 和离线查看器）
- [四轮底盘概念与尺寸说明](output/chassis-concept-2026-10-12/四轮版本说明.md)
- [嘉立创 EDA 电源板工程](pcb/power/power——1.eprj3)（当前现板对应资料）
- [ACG720 与现有电源板接线](doc/电机/ACG720与现有电源板接线_2026-10-10.md)

当前电源驱动板以用户正在使用的嘉立创 EDA 现板资料及 2026-10-12 导出的 STEP 为机械参考。`pcb/power/kicad/` 为历史对照设计，不用于当前现板的接口和结构布局。板卡、电机、驱动、电池以及模块的供电范围和实际电流仍须按实物复核。

仓库收录项目文档、可编辑设计文件、底盘概念图，以及用户于 2026-10-12 提供并要求收纳的硬件机械模型。模型索引与文件校验清单位于 `model/`，荔枝派的大型 STEP 使用 Git LFS 保存。其他 WHEELTEC、ACG720 等厂家随附的原始 PDF、安装包、视频与示例工程仍保留在本地；这些模型的加入不改变其余原厂资料的收录范围，原始设计文件的权利归相应提供方所有。

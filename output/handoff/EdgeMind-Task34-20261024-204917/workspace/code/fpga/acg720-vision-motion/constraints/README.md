# 板级约束边界

当前不提供可下载 CST：ToF 空闲引脚及 Bank 电平尚未确认，原厂 DDR3/HDMI 完整约束缺失。

保留运动工程的 Y18 时钟、F15/S0、J21/M15 串口及八根电机信号；摄像头使用现有外接 P7 映射，不改回旧板载相机针脚。`scripts/build.py` 会逐项检查，具体表见项目 README。

板级 SDC 必须覆盖原始 50 MHz、相机 PCLK、DDR UI、33 MHz 像素时钟、165 MHz TMDS 及 DDR PHY 生成时钟。异步时钟域：相机采集、UI、显示与控制。`cdc_mailbox` 的 held 总线在 req/ack 往返前保持；同步器只对第一级使用精确的异步输入例外，held 数据要给出最大延时/稳定性依据；`async_fifo` Gray 指针需按各源时钟周期约束跨域最大延时和偏斜。不要直接复制旧工程的全端口 false path。

`reset_sync` 每个域独立同步释放；所有域必须共用异步复位。若 DDR 校准丢失或重启 PHY，板级包装层应拉低整个系统复位，清空双方 FIFO/mailbox；不能仅复位其中一个域。

camera_pclk 为摄像头源同步采样时钟，须根据模块输出延迟/布线建立 input delay；不要将摄像头同步数据逐位加普通双触发器同步。

对 DDR PHY 内部 setup/hold/recovery 违反，依据同器件官方基线排查；不修改加密网表，也不以全局例外掩盖。构建审计明确区分“摘要为零”与完整时序签核。

# A741 接口

本文件保留原 EMC1/EMS1/EML1 的兼容接口。融合扩展命令 0x50～0x57、EMM1、EMF1 与配置 CRC 见 [融合协议](FUSION-PROTOCOL.md)，不得将二者的不同快照布局混用。

新载荷均为小端。EMC1 外层沿用会话号、递增请求号及 CRC16，内层沿用 AA55/V1/type/length/seq/TTL/payload/CRC16。一个控制所有者、一个在途请求，不重试运动命令。

## 控制

C0 能力回复：EVM1、flags:u16、最大速度:u16，共 8 字节。flags bit0 右桥已修正，bit4 A741 接口，bit5 P4 已启用。诊断构建为 0011；不能仅凭 User Code 推断完整接口。

MPU6050独立测试能力为00D1：bit6表示IMU物理接口启用，bit7表示电机硬件锁定；不设置bit5，不能将其误认为全传感器/运动版。测试版校准只要求key0～3、5～11，机械轮距key4可缺省，ARM始终拒绝。

新增只读key14为诊断字：bits0～6总线地址、bits8～15最近WHO_AM_I、bits16～23故障码、bit24初始化就绪、bit25近似水平、bit26采样有效；key15错误计数，key16采样序号。key17低/高16位为ax/ay，key18为az/gx，key19为gy/gz，key20低16位为温度，均有符号原始值。加速度除16384为g，角速度除16.4为°/s；温度raw/340+36.53。查询是分次读取，不承诺跨key同一采样原子性。详见 [IMU测试步骤](IMU-TEST.md)。

测试固件现显式接受MPU6500身份0x70，并单独核对ACCEL_CONFIG2；MPU6500温度改为raw/333.87+21，MPU6050身份0x68保持原换算。key12=6050是既有接口族标识，不是本轮实物自动检测值；上位机从key14显示实际sensor_model。sample_valid=false时上位机不输出三轴/温度伪测量。

| 请求 | 载荷 | 回复 |
| --- | --- | --- |
| 01/20 查询，02 ARM，03 DISARM，04 STOP，21 清故障 | 空 | 80，兼容 25 字节状态 |
| 05 HEARTBEAT | 空，主机 TTL=250 ms | 无 |
| 11 轮速 / 45 直行航向保持 | 左/右 i32 mm/s | 无 |
| 30 配置写入，限 disarmed | key:u8、value:u32 | 80 |
| 40 能力查询 | 空 | C0 |
| 41 传感器 / 43 静止校准 | 空，43 限未 ARM 且静止 | C1，32 字节 |
| 42 相对 IMU 旋转 | 角度:i32（65536 单位/圈）、最大轮速:u16 | 80，状态 4 才表示接受 |
| 44 配置回读 | key:u32 | C4，key/value/revision，各 u32 |

配置 key 0/1 左右 CPR，2/3 左右轮径 µm，4 机械轮距 µm，5 最大轮速，6 revision，7 航向符号（1 或 FFFFFFFF），8 ToF 偏移，9 PWM 限幅，10 每周期速度步长，11 PWM 步长。只读 key12=6050（MPU6050 模型），key13 安装轴（2=Z）。主机须核对模型，拒绝变更前 JY901 位流。

MPU6050 原始角速度按量程换算后仍保持现有 gz 遥测单位；yaw 是静止校准后 Z 轴积分的相对航向，不是绝对方位。加速度用于平放/静止检查，当前 EMS1 不传输三轴加速度。

0～11 全部有效写入后才允许校准/ARM；参数写入使校准失效。错误版本/长度/CRC、未知命令不进入运动控制。ARM 即开始有效期，空闲 ARM 也过期；STOP/故障后不自动恢复。

C1：

| 偏移 | 数据 |
| --- | --- |
| 0/1 | 版本 u8=1 / flags：armed、rotating、calibrated、calibrating 对应 bit0～3 |
| 2/3 | valid：angle、gyro、ToF 对应 bit0～2 / 校准结果 u8 |
| 4/6 | yaw/gz，i16；单位分别 180/32768°、2000/32768°/s |
| 8/10 | ToF mm:u16 / faults:u16 |
| 12/16/20 | FPGA ms:u32 / 累计相对航向:i32 / revision:u32 |
| 24 | gyro_bias:i16，余下保留为 0 |

校准结果：0未完成/运行，1成功，2移动或角速度异常，3超时/移动，4取消。

fault bit0 超时，bit2 编码器无反馈，bit4 IMU 失效，bit5 ToF 无效/过近，bit9 稳定后转角超差。模式：0未 ARM、1已 ARM 静止、2驾驶、3故障、4旋转。

## EMS1 遥测，UDP 6103

112 字节，每 50 ms 发最新快照。发送中保持原快照，拥塞可合并更新。

| 偏移 | 数据 |
| --- | --- |
| 0/4/6 | EMS1 / version:u16=1 / length:u16=112 |
| 8/12/16 | 快照序号、FPGA ms、revision，各 u32 |
| 20/22/23/24 | flags:u16、模式:u8、ToF 原始状态:u8、faults:u16 |
| 26 | flags bit15置位时为网络诊断u16；否则保留 |
| 28/32/36/40 | 左右目标/左右实测速度，各 i32 mm/s |
| 44/48 | 左右编码器 i32 |
| 52/54 | yaw/gz，i16 原始值 |
| 56/58/60/62 | ToF、雷达前/左/右最近距离 u16 mm；雷达 FFFF 为无有效值 |
| 64/68/72 | IMU 角度、ToF、LD06 的 FPGA 采样时间 u32 ms |
| 76/80/84/88 | IMU/ToF/LD06 错误计数、雷达/遥测合计丢包计数，u32 |
| 92/96/98 | 角速度 FPGA ms:u32、零偏:i16、校准结果:u8；99保留 |
| 100/104/108 | IMU 角度、ToF、LD06 各自采样序号，u32 |

flags bit0～12：角度有效、角速度有效、ToF 有效、LD06 流有效、已校准、已 ARM、校准中、旋转中、DDR 就绪、显示帧可用、摄像头错误、DDR/显示错误、视频 FIFO 溢出。

flags bit15标明当前编译包含网络诊断扩展，保持version=1/length=112兼容。偏移26的bit0～3为MAC接收有效帧计数模16，bit4～7为MAC接收坏FCS计数（饱和15），bit8～11为控制桥状态，bit12～15为控制桥拒绝计数模16。桥状态0～8依次为RECEIVE、CHECK_CRC、VALIDATE、SEND、WAIT_BUSY、WAIT_DONE、REPLY、MAKE_CRC、TRANSMIT。模计数可能回绕，必须比较连续采样；坏FCS饱和后需重启才能重新计数。有效帧包括ARP等以太网帧，不能直接等同于接受的控制请求。

2026-10-21主机仅允许STOP、状态/能力/传感器/参数读取及同值参数写入在超时后重试一次，每次使用新请求序号，超时和重试次数保留。ARM、校准、速度、角度和雷达控制均不自动重试。重试不能代替网络修复。

主机接收时间另存。LD06 流有效不代表已获得完整一圈。EMS1 超过 150 ms 未更新即不作当前有效遥测。

## EML1 雷达，UDP 6103

64 字节：0 EML1、4 version:u16=1、6 length:u16=64、8 包序号:u32、12 FPGA ms:u32、16～62 已校验的 47 字节 LD06 原包、63 为 0。

原包：54 2C、转速:u16、起始角:u16、12×(距离:u16/置信度:u8)、结束角:u16、设备时间:u16、CRC8。角度单位 0.01°，CRC 多项式 4D。厂家具体模块协议和电平仍待硬件文档确认。

主机二次校验 CRC/序号/角度连续性，回绕开始累计，下一次回绕才发布完整扫描。中断、坏包、序号跳跃、超过 300 ms 无完整新圈均清空；不会把旧圈标为当前数据。

控制 > 遥测/雷达 > 视频，只在包边界选源，发送中锁定源/长度/端口。雷达最多保留一个待发包，覆盖时计数。

## EMV1 视频

保留父工程分块、完整帧提交/废弃协议及 frame_id。HDMI 800×480；网络 400×240 同帧抽样、同一 OSD。没有加入破坏旧接收器的 EMV1 私有字段。
### EMP1 PHY diagnostics

When the A741 build has PHY diagnostics enabled, UDP telemetry also carries a 32-byte `EMP1` packet once per second. The fixed layout is: magic `EMP1`, version `1`, length `32`, sequence, FPGA milliseconds, PHYID32, BMCR, initial BMSR, current BMSR, then ready/error/fault, PHY address, settle-ms and reset-ms bytes. This packet is read-only diagnostics; it never arms the motor or changes PHY registers.

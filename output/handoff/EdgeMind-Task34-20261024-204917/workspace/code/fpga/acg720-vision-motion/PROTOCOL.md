# UART 与运行参数

沿用 `AA 55 | VERSION:u8 | TYPE:u8 | LENGTH:u8 | SEQ:u8 | TTL:u16 | PAYLOAD | CRC:u16`，115200 8N1，多字节小端，payload≤32，CRC16-CCITT-FALSE。VERSION 必须为 1。新 RTL 检查准确长度及已知命令；未知、错误版本、CRC、长度或参数不改变运动、不续期 TTL。CRC 错误不响应。帧内字节间隔超过20ms会放弃不完整帧，后续STOP可重新同步。回复使用请求序号；发送繁忙时可能丢弃查询回复，主机应串行等待，不用回复有无作为唯一停车依据。STOP 的执行不依赖 TX 就绪。

| TYPE | 请求载荷 | 回复 |
|---|---|---|
| 01 HELLO、02 ARM、03 DISARM、04 STOP、20 STATUS、21 CLEAR_FAULT | 空 | 80，原 25 字节运动状态 |
| 05 HEARTBEAT | 空 | 无；只对手动模式续期 |
| 10 SET_TWIST | int32 mm/s，int32 mrad/s | 无；左右目标最终裁剪 ±150 |
| 11 SET_WHEEL_SPEED | int32 左，int32 右，mm/s | 无；最终裁剪 ±150 |
| 12 ROTATE | int32 毫度、uint16 轮速 | 80；角度 ±360000，轮速 20～150 |
| 30 SET_PARAM | uint8 ID、uint32 value | 80；参数范围见下表 |
| 40 GET_CAPABILITIES | 空 | C0，8 字节：ASCII `EVM1`、uint16 flags=000F、uint16 最大轮速=150 |
| 41 SET_MODE | uint8：0 手动、1 循线 | 80；切换立即撤销运动 |
| 42 START_LINE | 空 | 80；再查 C3 确认 armed；不自动清硬故障 |
| 43 GET_SENSING | 空 | C3，32 字节，见下表 |
| 44 SET_LINE_PARAM | uint8 ID、uint32 value | 80；只在停止时接受 |

80 状态保持原格式：state:u8、faults:u16、left_count/right_count/left_speed/right_speed 各 int32、left_pwm/right_pwm/command_age 各 uint16。state=0 停止，1 解锁但零目标/暂停，2 运动，3 故障。faults bit2=无反馈、bit3=持续反馈反向、bit8=感知/TTL/视频故障。非法 AB 累计只在 C3 报告，不触发故障。零目标时 PI 清积分；CLEAR_FAULT 必须已停止，不清累计非法跳变统计。S0 完整复位所有状态。

回复是在命令接受时锁存，可能反映执行前状态；ARM、STOP、模式与启动必须另查状态确认。新固件下 ARM 要求三次安全测距；自主 START 额外要求黑线和视频就绪。模式切换后旧目标失效。STOP 不清故障原因；正常人工停止或遇障/丢线，条件恢复后可再次 START；reason≥4 须先停止并 CLEAR_FAULT。

| C3 字节偏移 | 类型 / 意义 |
|---|---|
| 0 | bit0=模式，bit1=armed |
| 1 | reason：0 正常、1 人工、2 障碍、3 丢线、4 摄像头过期、5 ToF 无效/过期、6 电机反馈、7 手动 TTL、8 视频未就绪 |
| 2 / 4 | uint16 原始距离 / 前沿净空，mm |
| 6 / 7 | 原始 ToF range status / flags：bit1 测距有效、bit2 ToF 通信错误、bit3 DDR 协议错误、bit4 视频就绪、bit5 显示欠载历史、bit6 采集 FIFO 溢出历史 |
| 8 / 10 | uint16 视觉 / 最后有效测距年龄，ms |
| 12 / 14 | uint16 近 / 远黑线中心 x |
| 16 / 17 | bit0 近区有效、bit1 远区有效 / 协议拒绝计数，饱和 255 |
| 18 | uint16 已发布视觉帧序号 |
| 20 / 24 | uint32 左 / 右累计非法 AB 跳变 |
| 28 / 30 | uint16 PI 输出上限 / ToF 基础速度 |

| SET_PARAM ID | 默认值 / 允许范围 |
|---|---|
| 0/1 CPR | 1469/1471；100～100000 |
| 2/3 轮径 mm | 66/66；10～500 |
| 4 轮距 mm | 121；20～1000 |
| 5 速度参数 mm/s | 150；40～400，实际每轮硬限幅仍为150 |
| 6 每毫度计数 Q16 | 491；1～100000 |
| 9 PI 幅值上限 | 512；0～512 |
| 10 斜坡 mm/s/10ms | 50；1～100 |

机械参数只允许停止时修改。ID9/10 在手动解锁时可改，以兼容原上位机动作的零限幅/再使能流程；循线运行时禁止修改。SET_TWIST 仍复用原工程 16 位角速度与 `/2048` 近似，未作为精确几何控制标定。

手动模式在250～500mm内也受ToF速度上限约束，两轮幅值被限到当前40～100mm/s基础速度；超过500mm时每轮硬上限150mm/s。单颗前向ToF不能证明后向净空，手动倒车只在已确认空旷场地进行。

| SET_LINE_PARAM ID | 默认值 / 允许范围 |
|---|---|
| 0 灰度阈值 | 80；1～254 |
| 1/2 近区 y0/y1 | 360/399；0～479，保持 y0≤y1 |
| 3/4 远区 y0/y1 | 260/299；0～479，保持 y0≤y1 |
| 5 图像左右反向 | 0；0/1 |
| 6/7 Kp/Kd Q8 | 64/96；0～1024 |
| 8 ToF 后退于车体前沿的距离 mm | 0；0～500 |

配置更新通过跨域 mailbox，在相机帧开始时采用新区域/阈值；不持久化，复位恢复默认。修改前先停止，至少等待一个新有效帧及三次安全测距再启动。40 能力 flags bit0 表示桥极性已在固件修正，上位机禁止再反转右目标。

# Type-C 串口 CLI 与协议

更新日期：2026-10-13。代码入口是 `serial_control.py` 和 `protocol.py`。这是调试工具初版；工程状态和已知问题见 [工程 README](../README.md)。完整实物 UART 回复、旋转续期和异常退出停车尚未验收。

## 连接和命令

PC 使用 ACG720 板载 CH340E 的 Type-C 数据口，固定 115200、8N1；电源板 USB-C 只供电。以下命令从 `code/fpga/acg720-motion-control/` 执行：

```powershell
python -m pip install pyserial
python host/serial_control.py scan
python host/serial_control.py --port COM7 hello
python host/serial_control.py --port COM7 status
python host/serial_control.py --port COM7 --log status.csv status
python host/serial_control.py --port COM7 stop
python host/serial_control.py --port COM7 disarm
python host/serial_control.py --port COM7 clear-fault
```

`COM7` 是示例，先确认实际端口。每条命令都会打开/关闭串口；当前不提供交互 `connect`。`status` 返回对象和 CSV 列包括 state、faults、左右计数、实测轮速、PWM 幅值和命令年龄。CLI 尚不确认回复序号或命令接受结果；状态发送握手需修复后才能可靠联调。

运动接口语法如下，属于修复和标定后的使用入口，不是本版本的实车通过步骤：

```text
--port COMx arm
--port COMx --duration SECONDS forward SPEED_MM_S
--port COMx --duration SECONDS backward SPEED_MM_S
--port COMx --duration SECONDS turn LINEAR_MM_S ANGULAR_MRAD_S
--port COMx --duration SECONDS rotate ANGLE_DEG SPEED_MM_S
```

全局选项写在子命令前。`--duration` 默认 1 秒；forward/backward/turn/rotate 都每 50 ms 重发原命令，正常退出发送 STOP。运动期间不轮询状态，因此 `--log` 暂不能形成运动曲线；串口错误或 Ctrl+C 没有 finally STOP，应由 FPGA TTL 处理失联，仍需故障注入测试。重复 ROTATE 有再次启动风险，后续须改成一次提交加独立心跳，并等 DONE 停止续期。

## 参数 ID

载荷为 `uint8 id + uint32 value`，小端；命令为 `set-param ID VALUE`。不要把示例机械值当作已标定参数。CPR 理论估算 1456 仅适用于电机轴 13 PPR、齿轮比 28、四倍频的配置。

| ID | 当前含义 | 复位值 / 实现边界 |
| --- | --- | --- |
| 0 / 1 | 左 / 右输出轴 CPR | 0；须分别实测 |
| 2 / 3 | 左 / 右轮径，mm | 0；使用有效滚动轮径 |
| 4 | 驱动轮轮距，mm | 0；运算使用低 16 位 |
| 5 | 最大轮速，mm/s | 0；当前用于 SET_TWIST 限幅，直接轮速命令未限幅 |
| 6 | 每毫度计数 Q16 | 0；下面公式为对称轮组理论值 |
| 7 / 8 | 保留的增益参数 ID | 当前无效，不修改 PI |
| 9 | PI 输出幅值上限 | 1000；只取 value 低 16 位，PWM 1024 满幅 |
| 10 | 每 10 ms 目标变化限值，mm/s | 100；只取低 16 位，不是 mm/s² |

```text
counts_per_mdeg_q16 = round(wheel_base_mm × CPR × 65536 / (360000 × wheel_diameter_mm))
```

ID 0～6 都写入后 ARM 才可能被接受；当前只记录“写过”，不会检查非零、范围或配置时状态。方向反相、最小启动 PWM、运行时 Kp/Ki 及 TTL 默认值参数尚未实现。S0 复位会清除机械参数，须重新配置；电池电压需外部记录。

## 二进制帧

```text
AA 55 | VERSION:u8 | TYPE:u8 | LENGTH:u8 | SEQ:u8 | TTL_MS:u16 | PAYLOAD | CRC:u16
```

VERSION=1；payload 最大 32 字节；多字节小端。CRC16-CCITT-FALSE：poly=0x1021、init=0xFFFF、无反射、xorout=0，覆盖 VERSION 至 PAYLOAD，CRC 自身小端发送，不覆盖 AA 55。TTL 按 FPGA 本地毫秒计时；Python 默认 250 ms。

| TYPE | 命令 | payload |
| --- | --- | --- |
| 0x01 | HELLO | 空；当前回复也是 STATUS，未实现独立版本查询 |
| 0x02 / 0x03 / 0x04 | ARM / DISARM / STOP | 空 |
| 0x10 | SET_TWIST | int32 v_mm_s + int32 omega_mrad_s |
| 0x11 | SET_WHEEL_SPEED | int32 left_mm_s + int32 right_mm_s；需自行调用 protocol.py 编码 |
| 0x12 | ROTATE | int32 angle_mdeg + uint16 max_speed_mm_s |
| 0x20 / 0x21 | GET_STATUS / CLEAR_FAULT | 空 |
| 0x30 | SET_PARAM | uint8 id + uint32 value |
| 0x80 | STATUS 回复 | 25 字节：u8 state、u16 faults、i32×4（左右累计计数/左右实测速度）、u16×3（左右 PWM/命令年龄） |

状态码当前为 0=DISARMED、1=READY、2=RUN、3=FAULT、4=旋转启动；运行中的旋转会写回 2，因此不能依赖 4 判断整个旋转周期。faults bit0=命令超时、bit1=非法编码器跳变、bit2=无反馈超时；S0 为全复位，未另设锁存急停故障位。

当前命令可能更改 TTL，而只有运动命令重置年龄；查询不会续期。版本、精确长度、序号及范围检查尚未完善，最终协议行为以修复后的端到端测试为准。

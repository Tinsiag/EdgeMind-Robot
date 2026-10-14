# Type-C 串口 CLI 与协议

> **2026-10-14**：信号球号已更新，见 [维修后接线](../../../../doc/电机/ACG720与现有电源板接线_2026-10-14.md)。3.3 V 对地短路烧毁根因未确认；闭环新位流已重新构建并通过实际管脚/时序报告审查，见 [构建记录](../BUILD-2026-10-14.md)；未下载，实际 IO Bank 电压仍待核对，不得复用旧位流/时序结果。串口帧格式、参数 ID 和 CLI 未因本次物理换线改变。

更新日期：2026-10-14。代码入口是 `serial_control.py` 和 `protocol.py`。这是调试工具初版；工程状态和已知问题见 [工程 README](../README.md)。完整实物 UART 回复已获用户 3/3 反馈；最新旋转续期和异常退出停车通过模拟测试，尚未实板验收。

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

`COM7` 是示例，先确认实际端口。每条命令都会打开/关闭串口；当前不提供交互 `connect`。`status` 返回对象和 CSV 列包括 state、faults、左右计数、实测轮速、PWM 幅值和命令年龄。CLI 已匹配回复序号，但 STATUS 不回显参数值，也不提供独立命令接受 ACK；无有效回复现在会打印错误并返回退出码 1。2026-10-14 后续修复了 STATUS 发送握手，并新增 serial_diagnose.py 原始字节诊断；基础回包已实板确认，最新控制修复版仍需另行下载验收。

运动接口语法如下，属于修复和标定后的使用入口，不是本版本的实车通过步骤：

```text
--port COMx arm
--port COMx --duration SECONDS forward SPEED_MM_S
--port COMx --duration SECONDS backward SPEED_MM_S
--port COMx --duration SECONDS turn LINEAR_MM_S ANGULAR_MRAD_S
--port COMx --duration SECONDS rotate ANGLE_DEG SPEED_MM_S
```

全局选项写在子命令前。`--duration` 默认 1 秒；forward/backward/turn 周期重发速度命令并轮询状态；rotate 仅发送一次，之后用 0x05 心跳续期并轮询状态。正常结束、Ctrl+C、串口异常、遥测缺失或 FPGA 故障均在端口关闭前 finally 尝试 STOP。断线可能使 STOP 无法送达，依赖 FPGA TTL 后备，仍需实板故障注入验收。旋转 READY 后退出，不重启原命令；`--duration` 是执行时限，超时主动 STOP，不代表角度已完成。运动遥测可通过 `--log` 写 CSV。

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

ID 0～6 都写入后 ARM 才可能被接受；当前只记录“写过”，不会检查非零、范围或配置时状态。方向反相已在顶层固定左 0 / 右 1，无运行时配置；最小启动 PWM、运行时 Kp/Ki 及 TTL 默认值参数尚未实现。S0 复位会清除机械参数，须重新配置；电池电压需外部记录。

## 二进制帧

```text
AA 55 | VERSION:u8 | TYPE:u8 | LENGTH:u8 | SEQ:u8 | TTL_MS:u16 | PAYLOAD | CRC:u16
```

VERSION=1；payload 最大 32 字节；多字节小端。CRC16-CCITT-FALSE：poly=0x1021、init=0xFFFF、无反射、xorout=0，覆盖 VERSION 至 PAYLOAD，CRC 自身小端发送，不覆盖 AA 55。TTL 按 FPGA 本地毫秒计时；Python 默认 250 ms。

| TYPE | 命令 | payload |
| --- | --- | --- |
| 0x01 | HELLO | 空；当前回复也是 STATUS，未实现独立版本查询 |
| 0x02 / 0x03 / 0x04 | ARM / DISARM / STOP | 空 |
| 0x05 | HEARTBEAT | 空；仅 armed 无故障时重置命令年龄，不启动运动 |
| 0x10 | SET_TWIST | int32 v_mm_s + int32 omega_mrad_s |
| 0x11 | SET_WHEEL_SPEED | int32 left_mm_s + int32 right_mm_s；需自行调用 protocol.py 编码 |
| 0x12 | ROTATE | int32 angle_mdeg + uint16 max_speed_mm_s |
| 0x20 / 0x21 | GET_STATUS / CLEAR_FAULT | 空 |
| 0x30 | SET_PARAM | uint8 id + uint32 value |
| 0x80 | STATUS 回复 | 25 字节：u8 state、u16 faults、i32×4（左右累计计数/左右实测速度）、u16×3（左右 PWM/命令年龄） |

状态码当前为 0=DISARMED、1=READY、2=RUN、3=FAULT、4=旋转启动；运行中的旋转会写回 2，因此不能依赖 4 判断整个旋转周期。faults bit0=命令超时、bit1=非法编码器跳变、bit2=无反馈超时；S0 为全复位，未另设锁存急停故障位。

当前命令可能更改 TTL，而运动命令和已使能时的 HEARTBEAT 重置年龄；查询不会续期。版本、精确长度、序号及范围检查尚未完善，最终协议行为以修复后的端到端测试为准。

机械标定：左 CPR 1469、右 CPR 1471、左右轮径 66.3 mm、中心轮距 121.4 mm。当前整数毫米协议使用 66/66/121；详见工程 README，不把小数乘十直接传入。参数复位丢失，未固化。

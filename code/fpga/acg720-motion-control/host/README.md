# Type-C 串口 CLI 与协议

> **2026-10-18 用户验证**：右轮驱动反向补偿后的图形上位机已获用户“已验证可用”反馈。实际距离/转角误差未提供，右轮PI符号限制仍存在。27项Python及10项接线静态回归通过。本轮未烧录或自动执行硬件运动。

## 2026-10-18 图形控制台：按距离和角度执行

### 右轮驱动反向的主机临时补偿

用户确认右轮实际前进方向与原正轮速命令相反。仅修改图形上位机：连接前的“右轮驱动反向补偿”默认勾选，将发送到FPGA的右轮轮速乘-1；编码器计数、物理前进目标和方向异常检查不反相。前进发送(+,-)，后退(-,+)，左转(-,-)，右转(+,+)，括号内为左右UART命令符号。若以后固件/接线已修正，应断开后取消此勾选再连接，避免二次反相。普通 `serial_control.py` 和 `startup_test.py` 没有应用此补偿。

限制：PI位于FPGA内，主机无法只反转桥输出而同时修正固件反馈符号；反向后的右轮命令与正向编码器反馈使内部PI误差相加，可能迅速到达50%输出限幅。因此这是以编码器计数判断行程和停车的临时方向补偿，右轮不能视为正常轮速负反馈，不能保证所填轮速、直线轨迹或转角精度。首次只做架空/短距离验证，保留STOP、计数反向检测、超时和故障收尾。若要修复右轮PI闭环，后续需要固件桥极性修正；本轮遵照用户要求没有保留固件源码改动或烧录。

在运动工程目录执行 `python host/car_control_gui.py`。需要 Python 自带 tkinter 和 `pyserial`（`python -m pip install pyserial`）。选择实际串口（如 COM4）后点击“连接”。连接会 STOP 并将输出限幅设为零，不会自动运行。关闭其他占用串口的程序。

- 前进/后退：输入厘米，或选择10、20、50、100厘米；大于0且最多200厘米。
- 左转/右转：原地旋转，输入角度，或选择15、45、90、180度；大于0且最多360度。左转目标为左轮后退、右轮前进，右转相反，须先核对实物桥方向与前进正计数一致。
- 轮速可输入40～400mm/s，默认200；PI上限固定设置为512/1024（50%），保持现有1kHz A721/A722固件的PWM频率。界面不能读取固件User Code或改变PWM频率。
- 每次点击只执行一个动作；执行中禁止叠加动作。点击红色“停止”或按空格取消；断开或关闭窗口也尝试停车并零限幅后关闭串口。串口由单独工作线程独占，按钮不会同时写串口。

新控制模块 `car_control.py` 使用相对左右编码器计数分别判断距离/转角，计数支持32位回绕；转角按轮距121.4mm、轮径66.3mm、左右CPR1469/1471计算。每轮接近目标减速，达到目标后该轮输出目标归零，最后STOP并零限幅。它没有使用现有固件ROTATE命令中的误差到速度映射。直线同样依据编码器进度，而非“时间×速度”估算距离。

每次运动先STOP/零限幅、检查故障并重配机械参数、确认ARM，再给轮速；目标每约40ms重发续期TTL，超时/无匹配遥测/方向明显相反/FPGA故障均退出并尝试停车。不自动CLEAR_FAULT、不修改固件保护。停止是滑行，轮胎打滑、惯性和遥测间隔会造成距离或角度误差；达到编码器目标不等于已机械停稳。暂未实车验收精度，首次架空检查两轮和正反方向；之前编码器非法跳变问题仍须排查。

兼容现有UART固件，无需为界面重新烧录；如仍使用A721，编码器故障会保持停车。`tests/test_host_motion.py` 是自动化测试，不是操作入口；本次在其中增加距离/角度、四方向、计数回绕、提前到达单轮、取消、故障/断线/超时等回归。

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

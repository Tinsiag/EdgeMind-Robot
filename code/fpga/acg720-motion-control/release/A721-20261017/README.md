# A721：参考 A712 的 1 kHz / 50% 上位机测试版

2026-10-17 在现接线下重新构建，未下载、未发送硬件运动命令。参考 motor-test 中 A712 的 1 kHz、50%、1 秒起动通过记录；A713 的 1 kHz/65% 持续启停也有用户确认。本版采用 A712 的频率和输出范围，保留闭环控制，不复用旧接线位流，也不把历史通过视为换驱动后通过。

## 固件与验证

- `acg720_motion_start50.fs`，User Code `0x0000A721`。
- GW5AT-60B / GW5AT-LV60PG484AC1/I0，50 MHz；PWM 1 kHz。
- SHA256：`aa6c69ad313545c50ce89202208c00a4eef3b706a478703825f27edc0a5698b4`。
- 20 个实际端口、方向、LVCMOS33、User Code 审查通过，setup/hold 违例 0/0，Fmax 51.523 MHz，详见 `build-audit.json`。
- 默认 PI 输出限幅 512/1024（50%），斜坡每 10 ms 为 50 mm/s。参数 ID 9/10 仍可修改；50% 是默认限幅，并非不可修改的硬限制。
- 本轮 16 项 Python 测试及 10 项接线静态测试通过；没有可用的 Icarus/ModelSim，本轮未重跑 RTL 仿真。Gowin 已综合新顶层并生成位流。未实测更换驱动后的起动、方向或闭环稳定性。

## 下载与单轮测试

1. VM 物理断开、车轮架空，下载本目录固件，选择 SRAM Program；独立回读 User Code 应为 A721。不要刷旧 A712/A713。
2. 保持 VM 断开，运行 `python host/serial_diagnose.py --port COM4`，确认 3/3 回复及 DISARMED/faults=0/PWM=0。命令均在 motion-control 工程目录执行。
3. 接通 VM，执行一次 `python host/startup_test.py --port COM4 --wheel left`。该命令会请求实际运动。测试结束断 VM，检查 Final 为 state=0、faults=0、左右 PWM=0，并记录旋转、计数及速度。
4. 左侧方向和输出正常后，保持车轮架空，接通 VM，再单独执行 `python host/startup_test.py --port COM4 --wheel right`，完成后断 VM。

脚本先 STOP、设置零输出限幅、重新配置机械参数（1469/1471、66/66/121）、最大速度400、旋转比例491、斜坡50，再 ARM 并独立确认 READY。运动前将上限设512；仅指定轮目标400 mm/s、另一轮0，主机运行时限1秒。400是用于较快提升PI输出的测试目标，不保证实测速度或一定达到50%；没有强制最低占空比。

本版实际占空比受速度反馈/积分影响，不等于 A712 的固定10%→25%→40%→50%爬升。约200ms无反馈保护、250ms命令TTL保持；缺反馈或其他故障会提前停止，不自动清故障或重试。1秒由主机控制，不是FPGA独立总时限；主机每约50ms续期，通信丢失依赖TTL。脚本结束/异常/中断尝试STOP并将限幅归零，串口断开时不能保证送达，必要时直接断VM。停止为滑行。

脚本不能通过串口核验 User Code，下载后请用 Programmer 回读 A721；勿在旧20kHz A720上误认为已切换频率。复位后机械参数仍丢失；A721默认限幅为512，旧A720仍为1000。

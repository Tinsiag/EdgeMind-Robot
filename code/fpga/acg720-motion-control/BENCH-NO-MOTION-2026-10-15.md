# 2026-10-15 VM 断电状态切换测试

用户明确确认已设置串口权限且电机 VM 已断电。通过 /dev/ttyUSB0、115200 8N1 实际执行。未下载固件、未发送 SET_TWIST/SET_WHEEL_SPEED/ROTATE。

1. serial_diagnose 三次查询均收到完整 35 字节、CRC/序号匹配 STATUS，3/3。
2. STOP 后独立查询 DISARMED，无故障、PWM=0。
3. 按顺序发送参数：9=0，0=1469，1=1471，2=66，3=66，4=121，5=50，6=491，10=5。每条有匹配回复，随后独立查询仍无故障且 DISARMED。协议无参数回读，不能仅凭回复证明每个寄存器值。
4. ARM 后独立查询 state=1；等待 0.3 秒再查询仍 state=1，faults=0，左右 PWM=0。
5. STOP 后独立查询 state=0，faults=0，左右 PWM=0。finally 再次 STOP，最终查询确认 DISARMED。
6. 所有采样中累计计数均为 0，PWM 均为 0。没有测量实际 IN 电平、桥输出、电流或机械动作。

ARM/STOP 自身返回的是处理前状态快照，判定采用随后 GET_STATUS，不把前一拍快照认作命令失败。
最终保持 DISARMED，已发送 PWM 限幅 0，不恢复非零限幅。S0/断电会清除机械参数并使 PI 上限回到复位默认 1000，因此复位后不得假设仍限幅为 0。

原始日志：.local/bench-uart-20261015.log、.local/bench-no-motion-20261015.log；逐帧 JSON：.local/bench-no-motion-20261015.json。
此测试仅证明串口通信和无运动目标状态切换，不验证首次带载启动、PI 整定、旋转取消、运动中的 STOP/TTL 制动距离或实车安全。

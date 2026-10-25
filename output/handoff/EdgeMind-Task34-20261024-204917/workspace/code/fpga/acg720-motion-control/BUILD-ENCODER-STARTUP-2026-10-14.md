# 编码器复位初始化修复，2026-10-14

现象：松开 S0 后 D0/D4/D6 持续亮。旧解码器强制 previous=00，输入稳定为 11 时会形成虚假非法跳变；累计 invalid_count 导致故障锁存，等待不会自愈。此机制已确认，不代表所有实板非法跳变原因均已排除。

修改 quadrature_decoder.v：复位释放后先填满三级同步寄存器，再采用实际 AB 作为初始状态，初始化期间不产生 step/invalid；之后仍检测真实非法跳变。不加入去抖，不屏蔽运行故障。保留右侧 invert=1、左侧 invert=0。

验证：encoder_startup_tb 覆盖全部四种静止 AB 初态，无虚假计数/故障；初始化后 11->00 仍触发一次 invalid，合法一圈仍产生四步。旧代码在静止 01 初态复现虚假一步，测试失败。共九个 RTL 测试通过，五个 Python 测试通过；旧 PI 测试仍有位宽告警。

Gowin 构建结束：2026-10-14 22:08:11 Asia/Shanghai。
20 个实际管脚审查通过，setup/hold 违例均 0，Fmax 51.025 MHz。
位流：impl/pnr/acg720_motion_control.fs
SHA256：fa2a9064764074d18df891597c6c0ad81b8397aac6153742dbb16ec7fb089be2
日志：.local/build-wiring-20261014-220654.log
旧位流备份：.local/pre-encoder-startup-20261014/acg720_motion_control.fs

未下载、未发送运动命令、未提交。实板应保持 VM 断电、编码器正常供电且静止，下载后反复复位并查询。稳定输入时复位后累计计数应为 0，无故障；若仍有 faults=2，应排查真实输入变化/电平/接线，不能屏蔽故障。复位清除 CPR，仍需重写左 1469、右 1471；并未将 CPR 固化。PI/待机超时/旋转取消等已知问题仍未修复。

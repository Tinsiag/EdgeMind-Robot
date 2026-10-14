# 右编码器反馈方向修订，2026-10-14

用户手转确认左轮车身前进原始计数为正、右轮为负；非操作侧少量变化由轻微带动造成。
本次仅将 motion_top.v 中右 quadrature_decoder 的 invert 从 0 改为 1；左侧保持 0，无接线和桥输出修改。
保留此前 STATUS UART 和 Python 分包解析修复。

- 新顶层 encoder_direction_tb：两侧按各自实测前进 AB 序列均 +4，反转均 -4，通过。
- 共 8 个 RTL 测试通过；旧 PI testbench 仍有两项端口位宽告警，不能据此认定 PI 已修复。
- Python 帧解析 5 个测试通过。
- Gowin V1.9.12.04 于 2026-10-14 21:29:04（Asia/Shanghai）完成构建。
- 20 个管脚审查通过，setup/hold 违例均 0，Fmax 51.852 MHz。
- 位流：impl/pnr/acg720_motion_control.fs
- SHA256：acc9db6717811ff99527960ad86c273386621974d13d98488ea34829bb7a26f8
- 日志：.local/build-wiring-20261014-212806.log
- 前一版本备份：.local/pre-right-invert-20261014/acg720_motion_control.fs

未下载，未发送运动命令，未提交 Git。保持 VM 断电下载后，先手转确认左右前进均为正增量，再通过输出轴准确转 5 圈计算 CPR=abs(结束-开始)/5。初始计数可不为零，读数之间不得复位。左右分别测量，推荐同向重复一次检查一致性。不使用电机转子圈数代替减速输出轴圈数。
PI、待机无反馈超时、旋转取消等已知问题仍未修复，不能用于实车运动验收。

# 2026-10-14 STATUS UART 回包修复

用户实测每次 GET_STATUS 收到 18 字节，开头为 AA 01 19，缺少 AA 55 同步头中的 55。
旧发送逻辑在注册的 tx_start 尚未被 UART 接收、busy 尚未更新时再次推进 index，丢失奇数索引字节。
修复 motion_status_tx.v，推进条件增加 !tx_start，等待 UART 接受启动后再发送下一字节。

## 验证

- 新 motion_status_tx_tb 经 UART TX → RX 校验连续三次完整 35 字节回复，验证序号、非零/负数载荷和 CRC，通过。
- 同一测试跑旧代码，在索引 1 复现 got 01 expected 55，失败。
- 其余六个既有仿真通过；PI 旧测试仍有 output_limit/ramp_limit 位宽告警，不证明 PI 缺陷已修复。
- 2026-10-14 21:00:03（Asia/Shanghai）Gowin 构建完成，20 个实际管脚通过审查，setup/hold 违例 0，Fmax 51.852 MHz。
- 新位流：impl/pnr/acg720_motion_control.fs
- SHA256：30e975fa685fd9364397570e7cb5514612b064a7fd9c6923acd42c489d5e4167
- 构建日志：.local/build-wiring-20261014-205906.log
- 前一版位流备份：.local/pre-uart-fix-20261014/acg720_motion_control.fs

上位机无有效回复现在会报错并返回退出码 1；serial_diagnose.py 只发送 GET_STATUS 并打印原始字节。
未提交 Git，未下载，未发送运动命令，未做实板回复验收。保持 VM 断电下载后重新诊断。
PI 有符号计算、待机无反馈超时、旋转取消/重发及异常退出停车等已知问题仍未修复，禁止据此认定可以实车运动。

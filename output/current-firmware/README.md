# 当前固件证据

[STATUS.json](STATUS.json)记录最近已烧录镜像及其验收范围。
[CANDIDATE-74513.json](CANDIDATE-74513.json)只表示候选静态签核，不能代替实板状态。

## 签核与Flash

- [构建文件哈希索引](BUILD-EVIDENCE.json)。
- [时序](TIMING-REVIEW.json)、[物理端点](PHYSICAL-REVIEW.json)、[约束目标](CONSTRAINT-TARGETS.json)。
- [TX](TX-SKEW-REVIEW.json)、[RX](RX-INPUT-REVIEW.json)、[TFT](TFT-PAD-TIMING.json)、[摄像头输入](CAMERA-INPUT-REVIEW.json)。
- [ED10数据隔离范围](DISPLAY-ISOLATION.json)、[后退安装模型](reverse-clearance-74513.json)。
- [原始Flash审计](flash/audit.json)。

同目录 `tests-*.json` 保存当前测试和原语回执。
大型SDF、网表和唯一主位流保留在活动工程当前构建内，不在此重复归档。

## 运行及实物反馈

- [模式1被动接收](MODE1-PASSIVE.json)、[应用记录](APPLICATION-REVIEW.json)。
- [启动ERR0011反馈](STARTUP-ERR0011.json)。
- [旧FW74511已验收基线](BASELINE-74511-ACCEPTANCE.json)，仅作已知对照。

数据记录的采样日期与验证范围保持不变。
本轮文件整理不代表重新进行了硬件测试。

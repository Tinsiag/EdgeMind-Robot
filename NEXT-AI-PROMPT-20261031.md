请继续维护 EdgeMind-Robot，项目目录 C:\Users\sc\Documents\Dev\Hardware\EdgeMind-Robot，活动工程 code/camera-car-control/a745-autonomous。

先读 AGENTS.md、.agent/main/handoff.md、output/refactor-autonomous-20261030/STATUS.json 和 imu-fault-20261031/DIAGNOSTICS.md。

本次已继续开发源码候选FW74507，还须读output/refactor-autonomous-20261030/CHANGE-74507.md。用户明确覆盖旧约定：前方停车线改300mm；编码器连续1秒无脉冲仅TX提示、不再ERR0004停车，非法四相跳变仍停车、PI和PWM上限保留；三方都堵时选择短退后重新择路，后方>350mm才后退，任一轮约100mm或约2秒止，停稳150ms，同一堵塞阶段只尝试一次。新增MODE10/11及EMS flags bit2/bit7提示。实板是否加载候选、实际SHA与签核以STATUS.json和真实审计为准，不能将下文74506签核借给新RTL。ERR0001仍未复现定位。

当前实板FW74506，SHA-256 b5cb8e927ebd07fccbaa1dde327acde91f565e7d8b698bc2862bd7a9c93d3a1a，Flash写入/校验/重载/就绪/版本比对通过，被动健康确认实际74506、CPU/摄像头/DDR正常、IDLE/ERR0000、未ARM。审计为output/refactor-autonomous-20261030/flash/20261031T075334.673715Z/audit.json。74506是故障快照诊断版，尚未修复或复现新的ERR0001，真实冷启动与运动也未验收。旧output/releases/fw74504不是当前镜像。

用户已确认74505能跑能转，问题是落地平地直行偶发ERR0001，架空正常，再按S1可恢复。车太重是猜测，不能直接归因或盲增PWM。先用capture_imu_fault.py只接收记录，用户受控短程复现后关VM、保留FAULT、不按S1，读imu_fault_sources、触发角度和有效标志，再修对应路径。原因bit0..3依次为IMU航向无效、原始gyro采样无效、倾角无效、超倾角；故障后正常角度不能代替触发角度。

保留侧后方CAD扫掠空间、择路转弯、gyro转角/转后航向锁定、编码器PI及未被用户明确改变的联锁。没有卡尔曼。上电不ARM，S1本地启停、S0急停，网口只有TX，不发送运动控制。用户此前确认VM关闭、轮子架空，接手180秒被动记录后答复尚未测试；下一次重载前更新VM关闭确认。持续Flash授权有效，不重复问权限；失败停查，不盲重试、不降级SRAM。架空转向约2秒S1停止，避免4.5秒无航向进度保护ERR0080。

26项回归、实测雷达回放、几何检查、4个导航叶模块5项原语检查及同次PNR/STA/SDF通过。新RTL变更后重建完整证据，再Flash和真实冷启动/负载运动验收。当前HEAD ac56a9e，本次74505/74506修改尚未提交推送；先修复并按真实结果更新交接，不把诊断版写成已解决。不恢复旧备份、不拆公共GND、不关机。

## 最新状态：FW74508（2026-10-31）

FW74508 已完成外部 Flash 写入/校验、重载、就绪和 UserCode 比对。实板 SHA-256 `899034472dc21c4f39669929d592031e9521faabf2b6718ffb9ee83ab8813690`；审计 `output/refactor-autonomous-20261030/flash/20261031T092737.270324Z/audit.json`；最终状态 `0x70022020`。被动健康 `output/refactor-autonomous-20261030/imu-fault-20261031/74508-health-20261031.json` 有 300 状态/300 姿态，均 FW74508、IDLE/ERR0000、未 ARM、目标为零，CPU/IMU/摄像头/DDR 正常。

姿态层新增最近三个完整 roll/pitch 对按最大绝对倾角取中值，抑制单次加速度/振动尖峰；22.5° 阈值、valid 和真实倾斜停车保留。29 项 RTL/协议、回放、几何、CPU、8 项导航/姿态原语模型和同次 PNR/STA/SDF/PAD 已通过。运动、显示和真实冷启动未验收，`application_verified`、`err0001_fixed`、`root_cause_confirmed` 仍为 false。用户已确认 VM 关闭，烧录后未 ARM。

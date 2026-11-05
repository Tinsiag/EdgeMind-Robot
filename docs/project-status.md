# 项目状态

## 版本依据

2026-11-04核对时，本地 `main` 与GitHub远端同为提交 `d433c0115daf1964e5aa9650bb2ea3e3a9139984`，工作区原先无未提交修改。
本轮目录和文档整理是该基线上的本地变更。

当前源码为FW74513，构建输入、唯一主位流和最近一次Flash审计的SHA核对一致。
完整SHA由[STATUS.json](../output/current-firmware/STATUS.json)维护；原始[Flash审计](../output/current-firmware/flash/audit.json)保留执行记录。
整理期间未重新编译或烧录，也没有连接4A核实实时在线状态。

## 已验证范围

| 项目 | 依据 |
| --- | --- |
| 当前构建的RTL、协议、CPU、几何及原语门 | [候选签核](../output/current-firmware/CANDIDATE-74513.json)及同目录测试回执 |
| 同次STA、RX/TX/TFT/DVP和routed端点 | [证据索引](../output/current-firmware/README.md) |
| 外部Flash写入校验、重载、配置就绪、UserCode | [Flash审计](../output/current-firmware/flash/audit.json) |
| 模式1的ED10被动接收 | [模式1记录](../output/current-firmware/MODE1-PASSIVE.json)，最近实测为2026-11-03 |
| 4A视频、NPU和任务控件 | [应用记录](../output/current-firmware/APPLICATION-REVIEW.json)，受其中验证范围限制 |

模式1被动窗口证明了检测数据接收，不能代替屏幕绿色框的肉眼确认或运动验收。
旧FW74511通过的运动与冷启动仅作为[已验收基线](../output/current-firmware/BASELINE-74511-ACCEPTANCE.json)，不套用于当前SHA。

## 待验收与未确认项

- 新SHA模式1/2实屏绿色框、完整断电冷启动和本地S1启动。
- 模式1绕障回线、模式2原地一圈、模式3任务及停车的实物表现。
- 相机/雷达外参、目标可观测性、接近与到达；默认标定未验证，自动接近禁用。
- ERR0011/SRC37和旧ERR0001的电气根因；[实物启动报告](../output/current-firmware/STARTUP-ERR0011.json)保留。

整理任务不会改变这些验收标志。

## 清理状态

[整理结果](../output/project-maintenance-20261104/RESULT.json)区分已执行迁移、文档删除和受阻的目录删除。
历史构建缓存尚未清除，不能将本轮记录描述成全部清理完成。

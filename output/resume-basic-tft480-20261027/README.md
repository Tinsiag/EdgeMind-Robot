# 基础480屏版本：恢复后的离线证据

当前结果为雷达270°安装朝向修正后的统一回归与整板综合。35项RTL、41项Python测试通过；综合LUT19832、寄存器17457、ALU2889、BSRAM36，用时147.049秒。详细说明和后续优化依据见 [根进度文档](../../RESUME-20261027.md)。

| 文件或目录 | 内容与边界 |
| --- | --- |
| `STATUS.json` | 当前完成项和未完成项；PNR、最终时序、烧录、实板、断电均未验收 |
| `regression-result.json`、`full-regression.log`、`tests/` | 同一轮35项RTL与41项Python结果、编译/运行日志、网络输入输出和仿真帧 |
| `FINAL-INPUT-AUDIT.json` | 138个回归输入、102个综合输入一致性；四路电机OBUF接GND、DDR原厂SHA、CST和Tcl选项核对 |
| `synthesis/` | 最终网表、工程、Tcl、原始日志、时间戳、资源/时序估算报告、参数与约束 |
| `resources.json`、`hierarchy.json` | 对比旧完整功能版的资源；实际CLS/最终WNS/TNS/拥塞为空 |
| `net-pin-degree.json` | 模块内命名引脚连接数，含输出；不是精确展平扇出或物理拥塞 |
| `warnings.json` | 综合警告分类计数；未作为时序签核 |
| `CHANGES-FROM-HANDOFF.json` | 相对原120文件交接清单及明确新增文件的变更；原78个已删除文件仍未恢复 |
| `SOURCE-SNAPSHOT.json`、`source-snapshot/` | 本轮回归/综合输入、交接现存源文件和新增源码的本地快照与SHA；不含完整工具链 |
| `camera-tft-simulation.png/.json` | 当前回归产生的480×272测试图案及来源SHA，不是摄像头实拍 |
| `gui-offline.png/.json` | 离线合成状态的GUI视觉检查，未建立硬件socket，不代表联机验收 |
| `telemetry-experiment/` | 未合入的局部载荷复位实验；等价通过但面积收益仅2 LUT/1寄存器，无实测布线收益 |
| `before-lidar-orientation-fix/` | 修正雷达朝向前的冻结结果；不与最终结果混用 |
| `ORIENTATION-FIX-COMPARISON.json` | 修正前后两次综合资源差异；不能将全局映射波动都归因于局部逻辑 |
| `obsolete-tools/` | 从活动工程移除的旧导航/归档脚本原文，仅作历史记录 |
| `finalize_evidence.py` | 检查完成的输入和网表、复制本轮证据；不执行构建/PNR/硬件操作 |

当前DDR跨时钟路径的综合估算余量仍为−0.725ns。综合系统Fmax估算79.349MHz不代表整板时序通过。所有资源数据来自电机物理输出硬接地的screen-test配置；普通运动构建未在本轮做整板实现，不能继承该硬锁保证。

如需只重建资源报告，在活动工程目录运行：

```powershell
& ../.venv/Scripts/python.exe -X utf8 scripts/report_resources.py --build .local/gowin-basic-tft480-screen-test-synth --baseline .local/gowin-fusion-tft480-screen-test --out ../../../output/resume-basic-tft480-20261027
```

工具输入若发生变化，先重新完成对应验证，再生成新的证据目录；不要用历史结果覆盖当前源码的未验收状态。本轮原始HANDOFF/NEXT-AI和旧handoff包未改写，没有提交或上传GitHub。

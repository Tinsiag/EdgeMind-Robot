# 自主避障进度证据

当前结论：57组RTL和61项Python通过；完整构建综合/布局完成，算法一布线失败，7463条网络未布通；未烧录、未ARM、未驱动车辆。最新说明以根 [HANDOFF-20261025.md](../../HANDOFF-20261025.md) 为准。

| 路径 | 用途 |
| --- | --- |
| `regression/result.json`、`*.log` | VM最新全量回归记录；`rtl_passed`是57组名称，`host_tests=61` |
| `gowin/result.json` | 完整构建结果、输入SHA、时间及综合估算；failed而非timed_out |
| `gowin/build.log`、`impl/pnr/a741.log` | 原始工具输出，末尾PR0004/7463未布通 |
| `gowin/impl/pnr/a741.rpt.txt`、`.html` | 失败轮次PNR资源和过程报告，不是最终时序报告 |
| `gowin/impl/gwsynthesis/*` | 综合资源/估算报告 |
| `gowin/build.tcl`、`a741.gprj`、`impl/pnr/cmd.do` | 实际选项、源文件列表、route_option=1/place_option=1与hold检查 |
| `VM-IMPORT-MANIFEST.json` | 从VM取回文件的原始字节SHA、大小与来源；历史文档更新前的SHA保留供追溯 |
| `SOURCE-IDENTITY-AUDIT.json` | 232个唯一VM输入与回归/构建哈希核对；Windows内容或仅换行差异明细 |
| `vm-working-tree.patch`、`vm-status.txt` | 导入时VM的未提交tracked差异与状态；untracked文件另有manifest和仓库副本 |
| `vm-environment.txt` | Linux版本、工具路径、Python版本与构建venv包清单 |
| `history/` | 更新前的交接和提示词原文，只作历史证据 |

基础提交 `6a32a56ee1755c8353116ace9afed6631ba57d9c`。目录沿用会话日期20261025，VM测试和PNR日志时间已跨到北京时间2026-10-26。记录中的绝对路径是旧现场，不是可移植入口。部分生成文件和本地动态库仅在VM；新环境按交接重新准备，不发布IDE、许可证、工具安装包、仿真程序、网表或实现数据库。

导入manifest里的`vm-HANDOFF`原位置后来更新为当前入口，原字节已保存在history；其他编辑过的交接文字以Git补丁为准。回归和构建源文件未在打包阶段改变。验证记录未在打包阶段伪造为新跑一轮，输入身份已单独核验。

更早的导航突发障碍复现日志在 [reproduced-by-next-ai-with-trace](../task34-recheck-20261025/continuous-navigation/reproduced-by-next-ai-with-trace/)，当前正式回归也含`continuous_obstacle_tb`。这些是理想化合成运动模型，不是实车验收。

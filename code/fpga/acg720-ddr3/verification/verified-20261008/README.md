# DDR3 实景 HDMI 固件与验证资料导入

2026-10-10 将用户提供的 `verified-20261008.zip` 合入本目录，30 个原始文件均保留原字节。它来自另一份摄像头工程交付，包含双帧区 HDMI 实景显示固件及证据，与本仓库的静态/单帧 CRC 自检快照分开保存。

## 文件入口

| 内容 | 文件 |
| --- | --- |
| 原始排查与实现报告 | [FINAL_VALIDATION_AND_PROBLEM_SOLVING_REPORT.md](FINAL_VALIDATION_AND_PROBLEM_SOLVING_REPORT.md) |
| 可下载位流 | [firmware/ddr3_live_hdmi.fs](firmware/ddr3_live_hdmi.fs) |
| 构建输入与验证检查 | [firmware/build-inputs.json](firmware/build-inputs.json)、[firmware/build-validation.json](firmware/build-validation.json) |
| 用户实物反馈 | [hardware-evidence/user-verification.md](hardware-evidence/user-verification.md) |
| HDMI 实景照片 | [hardware-evidence/hdmi_scene.png](hardware-evidence/hdmi_scene.png) |
| 正式时序报告 | [pnr-report/ddr3_live_hdmi_tr_content.html](pnr-report/ddr3_live_hdmi_tr_content.html) |
| 测试与历史 | `tests/`、`git-history/` |
| 原始文件校验清单 | [SHA256SUMS](SHA256SUMS) |
| 本次导入的完整校验记录 | [IMPORT-MANIFEST.json](IMPORT-MANIFEST.json) |

位流目标为 GW5AT-LV60PG484AC1/I0 / GW5AT-60B，文件头 User Code=`0x0000BC6C`。SHA256 为 `b6e3967afc4785ff42cb147c1060a8a3d5e2ad39c560904a4f1e8b8b3d8fd6f8`，与包内构建记录及校验清单一致。

## 证据范围

包内用户记录确认 HDMI 实景画面可显示、D6 灭、D7 闪烁。记录同时明确未单独确认镜头移动后的连续刷新、长时间稳定性、配置 Flash 固化及断电冷启动；位流和该次实物反馈的关联来自交付记录，未通过板上配置哈希读回验证。这里归档的是历史证据。

正式 PNR 报告摘要仍有 **101 个 setup、29 个 hold 违反端点**，与 `build-validation.json` 一致，完整时序尚未闭合。构建 JSON 中 `hardware_verified=false` 是编译时状态，后续实物反馈另在 `hardware-evidence/` 记录，原文件均未改写。

包内提供构建源码哈希、脚本哈希及原工程提交摘要，**没有包含完整 RTL、构建脚本或原工程 Git 对象**。本次归档不等于已将那份工程的可编辑源码合并，也无法仅凭该压缩包重新编译同一位流。原报告里的 Linux 路径保留作来源记录，不作为当前 Windows 本机路径。

## 校验处理

ZIP CRC 检查通过。原始 `SHA256SUMS` 的 29 项全部匹配，唯一未列出的是该校验清单本身。原始 `MANIFEST.json` 的其他 28 项匹配，但其中 `SHA256SUMS` 条目仍记录较早的 160 字节版本；包内实际文件为 2893 字节。这属于原始清单的过期记录，保留原件，并在新增 `IMPORT-MANIFEST.json` 中记录全部 30 个实际文件的大小和哈希、压缩包哈希及这一差异。

本目录的 Git 属性关闭文本换行转换，保证推送后的原始资料和位流字节与压缩包一致。

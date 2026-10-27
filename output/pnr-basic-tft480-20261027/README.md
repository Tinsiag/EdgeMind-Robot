# 基础480屏版本布局布线

用户已明确恢复整板布局布线。使用完成35项RTL、41项Python回归的冻结源码，四路电机物理输出硬接GND（screen-test），保持布局1、布线1、时序驱动、hold修复。

**布局布线已完成，最终时序未通过，暂不烧录。** 完整构建646.391秒，布局3分53秒、布线2分37秒；物理CLS17792/29952（60%）、BSRAM60/118（51%）、DSP24/118（21%）。综合阶段的36个BSRAM原语不能替代最终物理块数。

详细结论见 [PNR-20261027.md](../../PNR-20261027.md)。原始离线综合证据保留在 `../resume-basic-tft480-20261027/`，没有用本次结果覆盖旧报告。当前没有硬件操作。

| 证据 | 内容 |
| --- | --- |
| `STATUS.json` | 实现完成、时序不通过、不可进入烧录的当前状态 |
| `PREBUILD-AUDIT.json` | 布局布线开始前对35项RTL/41项Python验证输入及综合输入的核对 |
| `SYNTHESIS-COMPARISON.json` | 本次重综合与上一轮冻结综合资源相同 |
| `TIMING-REVIEW.json` | 六个有效时钟、TNS、端点违例、setup/hold/recovery/removal与脉宽余量 |
| `PHYSICAL-REVIEW.json` | 真实资源、内部阶段计时、四路电机OBUF接GND、原管脚映射、实际cmd.do选项 |
| `*-paths.txt` | 各类最坏时序路径原文，包含负值 |
| `high-fanout-nets-report.txt`、`route-congestions-report.txt` | 实际实现的扇出和局部拥塞报告 |
| `timing-constraints-report.txt` | 所有已报告时序约束的生效状态 |
| `WARNINGS.json` | 综合与PNR警告分开记录；没有PNR错误不等于时序通过 |
| `build-evidence/` | 位流、原始PNR/STA报告、网表、约束、工程、真实cmd.do与日志 |
| `algorithm-options-reference.json`、`clock-timing-reference.json` | 本机匹配版本Gowin手册相关页的文本，用于说明算法/时序含义 |
| `inspect_implementation.py` | 只读检查完成的实现并归档，不执行硬件操作；最终就绪判断仍须人工审核 |

位流SHA256为 `944c7b113cbe2811da7bc94072fb561f7a299bda20d5c1b8a4bbb82445556e41`。它是四路电机硬锁的screen-test候选，尚有DDR控制/复位、RGMII输入hold与TX FIFO最小脉宽违例；不得将此归档当作时序通过的固件交付。

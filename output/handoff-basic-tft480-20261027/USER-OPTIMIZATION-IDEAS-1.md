我现在正在进行FPGA的开发，目前正在做FPGA小车的调试，目前有：网口传调试数据，摄像头经 DDR3 输出到 480×272 TFT，小车用 LD06 做基础避障。保留避障所需的电机闭环与停止保护。DDR3 到 TFT 的取像时序，以及视频显示和避障并行运行，现在我在使用ai的时候，总是会在布线阶段卡相当长的时间，动不动就是40分钟，现在我需要找一些ai布线优化的教程，请你帮我找找该怎么做

你这个 FPGA 小车项目，已经不是单纯的 LED 闪烁或模块仿真了，而是进入了比较典型的 **多模块 FPGA 系统集成与时序收敛** 阶段。

结合你现在的架构，我建议不要只搜索“AI 布线优化”，而是同时学习两件事：

1. **让 AI 更高效地修改 RTL 和约束**：减少无效的代码重写、反复综合，以及每次修改都重新进行完整布局布线的情况。

2. **让 FPGA 工具更高效地完成布局布线（Place & Route）**：缩短实现时间，减少拥塞，并保证视频显示、DDR3 数据通路和避障控制能够稳定并行运行。

这两件事需要分开处理。因为如果一次布局布线需要 40 分钟，问题可能在于 RTL 结构、时钟约束、布局布线策略，也可能只是工具本身的正常运行时间。单纯要求 AI “优化代码”不一定能解决。

## 一、先明确你的项目中哪些部分不能被随意优化

![Design of DDR3 multi-port read-write storage management system based on FPGA-EEWORLD](https://images.openai.com/static-rsc-4/Ru53i_CO0XynHTTL1g2gCgZZJmsjcxPORkUCLPx9oFa_PDjBt27ppLnma7HEGU_J4yvEO6Ev4_mfr1CR2ZVLY6oz8rVSYaXtdab7ltDMTZ1dpxW-EWcCDl-O64q3Czw18gZtEni9biuAb-UVHEbfaJRDnderCKhhgF3uh1Im0ks?purpose=inline)

**DDR3 → TFT 视频显示链路**

重点：数据通路、跨时钟域、像素时序、读写仲裁和存储器接口时序。

应优先保证功能和时序正确，避免 AI 大范围重构已验证的 DDR3 控制与显示模块。

![AP078 - AUTONOMOUS CAR - A SELF DRIVING CAR  INTEGRATED WITH DETECTIONS - InnovateFPGA](https://images.openai.com/static-rsc-4/cBhUb8to0Y-G0Gxxqi9C_JjcrUq4leGci3mRT1gZNn4Ch-xb4rodnyAF6DIkm7nFJRyolpfDFQS5fary5w3fq5Fx32vcoEGJ684dWemnOEd5iFQvq8-mKXEt_POgQlPys0A-iF68otdbTKVpioouTQMY0sqD2ikLDfP0eUCqfVw?purpose=inline)

**LD06 避障与电机闭环**

重点：控制延迟、停止保护、电机反馈闭环、故障时的安全状态。

应将停止保护和闭环控制作为硬性约束，不允许为了减少资源或改善布线而删掉它们。

![AMD Customer Community](https://images.openai.com/static-rsc-4/bUb8oNMIUyiB-OmYYZ5qgXZkYWvyqIM7nu-1pJQyQrPkxZOGky7DoYt4jjD5ScsDI2XTIGr3CA4B04z7q58mhTtJg4ErMZ-10l09LevknG8HZQ-HWKXG7o3mtDYmnABz6Xwq4PJVAzPFOfOD8mjaCQ8EDDhhPS_DL5m76aLFE0U?purpose=inline)

**网口调试数据通路**

重点：接口吞吐、FIFO、时钟域隔离、调试数据与实时控制的资源竞争。

可以优先检查缓存、跨模块总线和高扇出控制信号，而不是直接重写整个通信模块。

你要追求的不是单纯让布线更快，而是：**在保留现有功能和安全保护的前提下，减少实现迭代时间，并让最终设计通过时序检查。**

## 二、我筛选出的高价值教程与官方资料

我建议优先学习 FPGA 厂商的官方实现优化教程，而不是直接套用某个 AI 生成的约束文件。布局布线策略与 FPGA 芯片系列、开发工具版本密切相关。

![Routing Resource Usage report per logic lock region. | Altera Community - 332834](https://images.openai.com/static-rsc-4/xufGL7n-cHiZsKwM30Z9w3SPdCj4AbdFR7eCXGHV4ly2kiMKDimaMnJtp7nOpsTWuR4StJ0a-OnAxjY07gKrSop8bc-kG_KLrl9YZCerrIddtRvLBOyZjPDFoB25RtY1UkdJHXIkqBOyUrSYjuvVyVb35vmazwzj9Y1eDwHXhPo?purpose=inline)

**1. Quartus Prime：增量优化（Incremental Optimization）**

优先学习

适用：Intel / Altera FPGA，尤其是 Quartus Prime Pro。

这项技术允许你分阶段运行 Fitter，分别检查布局、布线和时序，而不是每次修改都盲目等待完整编译。官方还提供了相关教学视频。

[官方教程与视频入口](https://www.intel.com/content/www/us/en/software/programmable/quartus-prime/incremental-optimization.html?utm_source=chatgpt.com) · [增量优化工作流程文档](https://docs.altera.com/r/docs/683236/25.3/quartus-prime-pro-edition-user-guide/incremental-optimization-flow?utm_source=chatgpt.com)

注意：部分增量优化能力仅适用于 Pro 版，具体取决于版本和器件。

![Step 4: Close Timing on your Design](https://images.openai.com/static-rsc-4/SNL1JenNNXKzqNfFHzXjzI26oTIs1AgYPodnKXQvtmgI6fImsB5SGitV4CcLD5VQUXhNq5VPidxZRFpAOnowCZqbXZ6oR0rDUqgGpWNSKmA5fP3oegZtIv7TsAcVL7KIHdj4ibTRF7Lng9dQaNXZRgBpIUIN8I1PdPxw3q5DFmw?purpose=inline)

**2. Quartus：Timing Closure 时序收敛实战**

适用：希望找出为什么布局布线耗时长、为什么时序过不了。

官方课程中有三个特别值得关注的免费内容：

- [Best HDL Design Practices for Timing Closure](https://www.intel.com/content/www/us/en/support/programmable/support-resources/design-guidance/quartus-support.html?utm_source=chatgpt.com) — 50 分钟

- Design Evaluation for Timing Closure — 42 分钟

- Timing Closure Using TimeQuest Custom Reporting — 21 分钟

重点学习关键路径、时序报告、资源利用率和 RTL 结构对时序的影响。

![Timing optimization techniques for RTL based designs on XC7Z007S-1CLG225C MiniZed board - element14 Community](https://images.openai.com/static-rsc-4/QtDmK6EcqtEzbuJj2lrlsUx4CFg4KVjeRi3vukhrLSfrQxHZcfxUb30EjxIQUFeCfV3Dlx_q3f6uqkWuKczFcvLKSsfbiuIKqHybhH3jx07QWeNd_Pxr5oCvvfPrM58Qafdm2wvPyix9v9sCfOGeuFvu8FgoRx3oPhi8EokDyl0?purpose=inline)

**3. Vivado：UltraFast Design Methodology（UG949）**

适用：AMD / Xilinx FPGA。

[官方完整指南](https://docs.amd.com/r/2025.2-English/ug949-vivado-design-methodology?utm_source=chatgpt.com)

优先阅读以下主题：

- Incremental Implementation Flows：增量实现

- Compile Time Considerations：编译时间

- Reducing Net Delay Caused by Congestion：降低拥塞引起的网络延迟

- Addressing Congestion：处理布线拥塞

- High-Fanout Nets：高扇出网络

Vivado 的实现流程还使用机器学习模型辅助预测布线延迟和拥塞，但这不意味着开启某个“AI 开关”就能解决所有布线问题。

![](https://www.google.com/s2/favicons?domain=https://www.amd.com&sz=32)

AMD+1

![AMD Customer Community](https://images.openai.com/static-rsc-4/fGqBjoFt5jJ8spCnJrIaGsex4Vugw2xlAW-8cLBwKqVwTqBHMyRi4e-wX5m8LIXbbERcmtIdhb6GoFPSklRAhpy06jMYT6kQnSxHLhWdyGlJZ1KaxIgVg_Q6iuj6zBBGQjflVgrXSycV2fxgwrNGGlGmDFYsO-lKFTaM5Zj8GmA?purpose=inline)

**4. FPGA 布线优化：资源、拥塞与约束**

适用：无论使用哪一种 FPGA 工具，都值得学习。

[Quartus Prime Pro 设计优化手册](https://www.intel.com/content/www/us/en/support/programmable/support-resources/design-guidance/quartus-support.html?utm_source=chatgpt.com)

[Quartus Prime Pro 时序收敛与优化章节](https://docs.altera.com/r/docs/683641/25.3/quartus-prime-pro-edition-user-guide/timing-closure-and-optimization?utm_source=chatgpt.com)

学习目标是区分逻辑级数过多、全局信号拥塞、资源利用率过高和布局约束不合理，而不是盲目增加布线努力等级。

![](https://www.google.com/s2/favicons?domain=https://www.intel.com&sz=32)

Altera+1

## 三、如何让 AI 帮你优化，而不是反复等待 40 分钟

我建议把 AI 的工作流改成下面这样。

**阶段 1：分析现有工程**

读取 RTL、时钟约束、综合报告和上一次布局布线报告，不先改代码。

**阶段 2：先做低成本检查**

检查未约束时钟、锁存器、资源利用率、高扇出网络、跨时钟域及明显的 RTL 问题。

**阶段 3：分阶段实现**

先综合，再检查布局结果；确认值得继续后再布线。支持时使用增量编译或保存检查点。

**阶段 4：只针对瓶颈修改**

每次优先修改一个明确问题，比较修改前后的资源、拥塞、时序和编译耗时。

这里有一个关键原则：**不要让 AI 在没有报告依据的情况下，一次性重写整个 RTL 工程。** 尤其是 DDR3 控制器、视频时序和电机安全控制，这样做很容易把原本正确的模块改坏。

### 可以直接交给 AI 的优化指令

下面这段可以作为你在 Codex、Claude Code 或其他代码助手中的项目级任务要求。

# FPGA 布局布线优化任务规范

你是一名具有 FPGA 综合、布局布线、时序收敛和硬件验证经验的工程师。

## 项目现状

本项目是 FPGA 小车，包含以下模块：

- 网口传输调试数据。

- 摄像头数据经 DDR3 缓存后输出到 480×272 TFT。

- LD06 激光雷达基础避障。

- 电机闭环控制和停止保护。

## 优化目标

1. 减少综合、布局布线和时序收敛的迭代耗时。

2. 在不牺牲功能正确性和安全性的前提下，改善资源利用率、布线拥塞和关键路径时序。

3. 优先利用已有综合结果、实现检查点和增量编译能力，避免不必要的全量编译。

## 硬性约束

- 不得删除、旁路或弱化电机闭环、停止保护和故障安全逻辑。

- 不得破坏 DDR3 数据通路、TFT 像素时序、摄像头采集及网口调试功能。

- 不得擅自修改引脚分配、时钟结构、DDR3 IP 配置或已有的时序约束。

- 不得仅为了通过时序检查而添加未经分析的 false path、multicycle path 或其他时序例外。

- 所有修改必须有可验证的依据，禁止无目的的大规模重构。

## 工作流程

1. 先识别 FPGA 型号、EDA 工具及版本、顶层模块、时钟约束和当前编译流程。

2. 检查综合报告、时序报告、资源利用率、布局报告、布线拥塞报告及编译日志。

3. 确定实际耗时最长的阶段，并区分逻辑问题、时序问题、布线拥塞和工具配置问题。

4. 优先提出低风险、低成本的诊断和优化方案；未经确认不要直接修改整个工程。

5. 每次修改尽可能只针对一个瓶颈，并保留修改前的工程版本。

6. 优先运行适当的局部检查或中间阶段；只有必要时才进行完整实现。

7. 比较优化前后的编译时间、资源利用率、最差负时序裕量、总负时序裕量、拥塞和功能验证结果。

## 输出要求

先给出问题诊断和证据，再给出修改建议。每项建议必须说明预期收益、风险、验证方式，以及是否需要完整重新布局布线。没有报告证据时，明确标注为待验证假设，不要直接改代码。

## 四、针对你的小车项目，我建议优先检查的 5 个问题

| 优先级 | 检查项                   | 具体做法                                                               |
| ------ | ------------------------ | ---------------------------------------------------------------------- |
| 1      | 到底哪个阶段耗时 40 分钟 | 从编译日志确认时间花在综合、布局、布线还是时序修复阶段                 |
| 2      | 时钟约束是否完整         | 检查系统时钟、DDR3 用户时钟、像素时钟及其他时钟域的约束                |
| 3      | 布线拥塞是否严重         | 查看工具提供的拥塞报告、路由资源利用率和高扇出网络                     |
| 4      | 能否使用增量编译         | 让已经验证的模块复用已有实现结果，避免不必要的重复工作                 |
| 5      | RTL 是否存在结构性问题   | 检查超宽组合逻辑、过深的多路选择器、跨模块长连线和不合理的全局控制信号 |

其中，第 1 项最重要。**如果主要时间花在布线阶段，优化方向与综合阶段耗时过长完全不同。** 而且 40 分钟本身不能说明工具有问题，需要结合芯片规模、资源利用率和编译日志判断。

## 五、我需要你提供两个关键信息

这样我就能从通用教程进一步缩小到适合你当前工程的具体操作步骤。

1. 你现在用的 FPGA 和开发工具是什么？

Intel / Altera FPGA

AMD / Xilinx FPGA

高云 FPGA

其他 FPGA

暂时不确定具体型号

Quartus Prime

Vivado

高云 EDA

其他工具

2. 40 分钟主要卡在哪个阶段？

布局已经完成，Routing / 布线一直运行

Placement / 布局阶段就很慢

布线后反复进行时序优化或修复

每次修改代码后都要重新完整编译

不清楚，需要看日志

你主要使用哪个 AI 编程工具？

Codex / Codex CLI

Claude Code

其他 AI 工具

如果方便，最好再发一张你当前编译日志中显示 **Placement、Routing、Timing Optimization 耗时**的截图。我可以根据实际阶段，帮你判断应该优先调整编译策略、时序约束、RTL，还是 AI 的工作方式。

请针对我的 FPGA 小车项目制定具体的 AI 布局布线优化方案。FPGA 平台：高云；EDA 工具：高云 EDA；主要耗时阶段：布局 Placement；AI 工具：Codex / Codex CLI。请提供对应的官方教程、具体菜单或命令、AI 工作流，以及适合 DDR3→TFT、网口调试和 LD06 避障并行运行的优化方案。

## 六、高云 EDA 应该重点看哪些官方教程

针对你的工具链，我建议按下面顺序阅读。以下都是高云官方资料入口或官方 PDF，优先使用与你安装版本匹配的手册。

**1. SUG100 — Gowin 软件用户指南**

优先级：最高

[官方文档库](https://www.gowinsemi.com.cn/software/3?utm_source=chatgpt.com) · [英文 PDF](https://cdn.gowinsemi.com.cn/SUG100E.pdf?utm_source=chatgpt.com)

阅读工具流程、综合、Place & Route、Process 面板及 FloorPlanner 相关章节。官方手册说明 FloorPlanner 可查看并编辑 I/O、原语、BSRAM、DSP 和组的位置约束。

![](https://www.google.com/s2/favicons?domain=https://cdn.gowinsemi.com.cn&sz=32)

GoWinSemi+1

**2. SUG935 — Gowin 设计物理约束用户指南**

[官方 PDF](https://cdn.gowinsemi.com.cn/SUG935E.pdf?utm_source=chatgpt.com)

重点看 FloorPlanner、物理约束、布局结果回标和时序优化。官方手册也说明，FloorPlanner 可以利用布局信息和关键路径辅助物理优化。

![](https://www.google.com/s2/favicons?domain=https://cdn.gowinsemi.com.cn&sz=32)

GoWinSemi+1

**3. SUG940 — Gowin 设计时序约束用户指南**

[官方文档库](https://www.gowinsemi.com.cn/software/3?utm_source=chatgpt.com)

重点看时钟定义、输入输出延迟、时序例外、跨时钟域和时序报告。先确认时序约束正确，再做物理优化；不要靠放宽约束掩盖真正的问题。

![](https://www.google.com/s2/favicons?domain=https://www.gowinsemi.com.cn&sz=32)

gowinsemi.com.cn+1

**4. SUG949 — Gowin HDL 编码风格用户指南**

[官方文档库](https://www.gowinsemi.com.cn/software/3?utm_source=chatgpt.com)

重点研究 RTL 如何推断寄存器、RAM、DSP 和组合逻辑，以及如何避免不必要的逻辑级数。对 AI 自动生成的 HDL 尤其有用。

**5. SUG1220 — Gowin 软件 Tcl 命令用户指南**

[官方文档库](https://www.gowinsemi.com.cn/software/3?utm_source=chatgpt.com)

如果你希望 Codex 自动读取报告、运行重复检查或整理不同版本的编译结果，这本手册很重要。但必须先确认当前 EDA 版本支持哪些 Tcl 命令，不能照搬 Vivado 或 Quartus 的脚本。

## 七、针对你的系统，具体怎么优化 Placement

这里需要特别注意：你目前最慢的是布局阶段，而不是布线阶段，所以先不要急着加大 Routing Effort。下面是我建议的诊断顺序。

### 1. DDR3 → TFT：优先减少跨区域的数据与控制连接

- 保持 DDR3 控制器、PHY 及其厂商 IP 的原始结构，除非报告明确指向相关瓶颈。

- 将像素输出链路中的 FIFO、行缓存及控制寄存器作为一个逻辑功能簇分析，避免在没有依据时强制把它们锁定到某个区域。

- 检查跨时钟域的 FIFO、帧同步和复位同步逻辑，确认它们的结构合理。

- 如果视频链路存在宽数据总线、复杂多路选择器或大量跨模块控制信号，优先分析这些连接对布局的影响。

### 2. 网口调试：检查高扇出和宽总线

- 避免将同一个未经寄存的复杂组合控制信号分发到大量模块。

- 检查调试数据路径中的 FIFO、总线扇出、数据选择逻辑和跨时钟域处理。

- 不要为了减少逻辑复制而盲目合并所有相似控制逻辑；共享逻辑可能减少 LUT，却增加扇出和连线长度。

### 3. LD06 避障：保持安全控制的独立性

- 保留电机闭环、停止保护和故障处理的完整逻辑。

- 尽可能让关键控制路径保持短小、同步、易于约束。

- 不要把 LD06 数据解析、复杂调试输出和电机控制全部塞入一个巨大的组合逻辑块。

- 如果避障逻辑有独立时钟域，明确处理 CDC，而不是简单地将相关路径排除在时序分析之外。

### 4. 什么时候才应该使用 FloorPlanner 手动布局？

先看布局结果和时序报告，再决定是否对相关模块或原语添加物理约束。

适合尝试的情况：

- 关键模块之间有大量互连，却被布局在相距较远的区域。

- 关键路径报告明确显示长连线延迟占主导。

- 重复布局结果表明某个关键模块的物理位置不理想。

不适合盲目使用的情况：

- 还没有分析布局报告。

- 只是因为 Placement 很慢就把所有模块固定到某个区域。

- 对 DDR3 PHY、专用时钟资源或厂商 IP 施加未经验证的位置约束。

物理约束不一定能缩短 Placement 的时间，过度约束反而可能限制布局器的搜索空间，让结果更差。

## 八、Codex CLI 的实际工作流：把“等 40 分钟”改成有依据的迭代

我建议你将 Codex 的工作分成三个模式：分析模式、局部优化模式、完整验证模式。每个阶段的权限和任务范围不同。

### 第一步：建立可回退的基线

在工程根目录中执行：

```
git status --shortgit switch -c optimize/gowin-placementgit add -Agit commit -m "baseline before placement optimization"
```

如果当前工作区存在未完成的修改，先检查并提交或备份，避免覆盖已有工作。

随后让 Codex 先分析工程：

请只分析当前高云 FPGA 小车工程，暂时不要修改任何文件。

目标是查明 Gowin EDA 的 Placement 阶段为什么耗时很长。

请依次完成：

1. 识别 FPGA 型号、Gowin EDA 版本、顶层模块、RTL 文件、IP 文件和约束文件。

2. 找出 DDR3、摄像头、TFT、网口、LD06、电机闭环和停止保护分别对应哪些模块。

3. 检查现有 SDC/时序约束和物理约束，标记缺失或存在疑问的部分，但不要自行添加时序例外。

4. 检查最新的综合报告，记录 LUT、寄存器、BSRAM、DSP、PLL 等资源利用情况。

5. 从编译日志判断 Placement 的具体耗时，以及是否存在资源拥挤、布局重试、约束冲突或其他异常。

6. 生成一份 placement-baseline.md，记录当前证据、问题假设、待补充的报告和建议的下一步检查。

禁止删除或弱化电机闭环、停止保护、DDR3 控制及视频时序逻辑。没有足够证据时，不要声称已经找到根因。

### 第二步：在高云 EDA 中获取正确的布局信息

![Sipeed Lichee Tang Nano 4K Gowin FPGA - Board review. - element14 Community](https://images.openai.com/static-rsc-4/buICltEIth0i3eKN43MOZlZyDK1sXWgeW_KOLfRFre8d1kfzcNaHjDCv0K7xQJZBj7bynzLI0UiCoHKaUcKQORfD3PnbgLKTjWTqGVG17PEnmW6sM752q5L0Mv7tOLytW83N2g66chMRU0lUBBZuFf4lHR4boJsCuBwnNT6GkG8?purpose=inline)

**操作 A：查看编译报告**

1. 打开现有工程。

2. 在 Process 面板运行 `Synthesize`。

3. 查看综合报告和资源利用率。

4. 再运行 `Place & Route`，检查相关报告及编译日志。

记录 Placement 的开始和结束时间，以及布局失败、重试和资源相关警告。

![Sipeed Lichee Tang Nano 4K Gowin FPGA - Board review. - element14 Community](https://images.openai.com/static-rsc-4/zPlUZWoTYgtxT3h09GDfP0z-Nt09Ml6-b_3WgypKg5QAosxvtN-oO0vAHoXWDGBZ9X4wYNiSYqdAH5RQ5mpStFm1LekPZyQitjGNdnFWtImgYcKeEXI9F0g2qwJBymntkaR4euYgii2siOUaJHslbZlXYdq0W1yqnsLk_ixKIyY?purpose=inline)

**操作 B：检查布局结果**

1. 在 Process 面板中完成综合。

2. 双击 `FloorPlanner`。

3. 检查 Chip Array、Package View 和已有物理约束。

4. 根据关键路径和模块连接情况，判断是否需要物理约束优化。

以上操作路径可在高云官方《设计物理约束用户指南 SUG935》中核对。

![](https://www.google.com/s2/favicons?domain=https://cdn.gowinsemi.com.cn&sz=32)

GoWinSemi+1

注意：不同版本的高云 EDA，Process 节点名称、报告内容和可配置选项可能有所差异。不要预设存在某个叫作 `Fast Placement` 或 `AI Placement` 的开关。

### 第三步：让 Codex 只修改已经证实的瓶颈

将实际报告提供给 Codex，并要求它逐项提出修改方案，而不是一次修改所有模块。

根据当前高云 EDA 工程的综合报告、Placement 日志、布局结果和时序报告，提出最小风险的布局优化方案。

要求：

- 每条建议必须关联到具体的报告证据、模块或信号。

- 优先排查不必要的逻辑复制、过高扇出、过深组合逻辑、资源利用率和模块间长距离连接。

- 区分真正影响 Placement 时间的问题与仅影响最终时序的问题。

- 不要直接添加区域约束、固定原语位置或修改 DDR3 IP；必须先说明必要性和预期收益。

- 一次只实施一个有明确理由的改动。

- 每次修改后先运行低成本检查，再根据结果决定是否进行完整布局布线。

- 对比基线和优化后的编译时间、资源使用率、时序裕量、功能正确性及停止保护。

- 不得将未验证的时序路径设置为 false path，也不得通过放宽约束制造虚假的时序通过结果。

请先给出修改计划及风险，不要立即执行完整重编译。

## 九、怎么判断优化有没有效果？

每次迭代至少记录下面这些指标：

| 指标                   | 作用                               |
| ---------------------- | ---------------------------------- |
| Placement 耗时         | 你的首要优化目标                   |
| 总编译耗时             | 判断是否只是把时间转移到了其他阶段 |
| LUT / FF / BSRAM / DSP | 判断逻辑结构和资源压力             |
| 布局失败、重试和警告   | 判断是否存在约束或布局问题         |
| 最差负时序裕量（WNS）  | 检查最差时序路径                   |
| 总负时序裕量（TNS）    | 检查整体时序违例情况               |
| 功能回归结果           | 确保视频、网口、避障和电机保护正常 |

如果报告没有提供某项指标，就记录为未提供，不要让 AI 猜测数值。

还有一点：如果高云 EDA 当前版本不支持某种增量布局或检查点复用，Codex 也无法通过修改提示词凭空获得这项能力。应先查阅该版本的 SUG100、SUG1220 和发布说明，确认实际支持的功能。

## 十、下一步最值得做的事

我建议你现在先不要继续改 RTL，而是把下面三个信息发给我：

- **FPGA 的具体型号**：例如 GW2A、GW5A 或其他型号。

- **高云 EDA 的版本号**：可以在软件的 About/关于页面查看。

- **一次完整编译的日志或报告**：尤其是 Placement 开始、结束的时间，以及综合资源报告。

有了这些信息，我就可以进一步给你制定针对该型号和工具版本的优化方案，包括具体的菜单位置、哪些报告值得导出、哪些参数可以安全调整，以及 Codex 如何自动整理每轮实验的结果。这样才有机会实质性地减少你每次等待 40 分钟的时间。

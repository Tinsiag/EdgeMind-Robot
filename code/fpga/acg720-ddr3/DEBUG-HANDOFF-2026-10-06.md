# ACG720 OV5640 -> DDR3 调试交接记录

日期：2026-10-06（Asia/Shanghai，22:41 后停止调试）  
项目：EdgeMind-Robot / code/fpga/acg720-ddr3  
硬件：小梅哥 ACG720，GW5AT-60B，GW5AT-LV60PG484AC1/I0，B 版本  
工具：Gowin V1.9.12_x64，Programmer CLI；USB location 546；SRAM 下载，未写外部 Flash

## 当前板卡状态

最后一次下载的是 B21 复位约束的摄像头 DDR FIFO 诊断位流：

- 文件：.local/camera-ddr/impl/pnr/camera_ddr_fifo_bist_b21.fs
- SHA256：27F08F7004201D8818FBA2226A582EDEC4D1BD0B80FBBE849BB9CC57C08866C9
- 下载方式：programmer_cli.exe operation_index=2，100% 完成
- User Code：0x0000BAE9
- Status：0x70026020
- 用户观察：D0 亮，D1/D2/D3 全灭

板卡当前不是已知通过的主工程，而是失败的临时诊断工程。收到用户停止要求后没有再次编译或下载，只整理文档；整理时没有运行中的 gw_sh/GowinSynthesis/programmer_cli。断电会丢失 SRAM 临时配置，重新上电可能加载外部 Flash 中原有程序，不能沿用本记录的 LED 解释。

明天如需恢复工作状态，应重新下载 .local/ch47/impl/pnr/ov5640_ddr3_hdmi.fs；仍然只使用 SRAM。交接期间曾先恢复该主工程位流，下载成功，但没有收到该次恢复的灯态确认就又换成诊断版；“主工程全亮”是此前用户明确反馈的结果。

## 已确认通过的结果

### 1. JTAG / 器件识别

- 下载器：Gowin USB Cable(FT2CH)
- FPGA ID：0x0001481B
- Programmer 可稳定完成 SRAM Program
- 外部 Flash 没有被本次操作改写

### 2. 独立 DDR3 固定模式 BIST

工程：.local/bist/

- 位流：.local/bist/impl/pnr/ddr3_bist.fs
- 本机综合、布局布线、位流生成成功
- 最终通过版本 SHA256：E3A7E06628D7E7600527DE1F8512C7F75EABC1F56067D59ECA29C410E99C5CBD
- SRAM User Code：0x00007CCF
- 板上结果：D0 亮、D1 亮、D2 亮、D3 灭
- 含义：DDR PLL 锁定、DDR3 校准完成、16 个 128-bit 固定模式突发全部读回一致、无失败

这已经证明 ACG720 板上的 DDR3 PHY、引脚约束和固定模式读写通路可工作。它不等价于完整摄像头帧缓存验证，但足以排除“DDR 芯片必然损坏”。

测试范围：地址 0、8、16、…、120，每次 128 bit，共 256 字节。模式为四组 A5A5A5A5/5A5A5A5A/C3C3C3C3/3C3C3C3C 与地址异或；先全部写入，再全部读回比较，并设置读回超时。未测试全容量、长时间压力或整帧数据。

初版 BIST 使用原始 clk50M 作为 DDR IP 的 clk 参考输入，只亮 D0；改成 camera_pll.clkout2 的 loc_clk50m 后 D0/D1/D2 亮、D3 灭。DDR IP 的用户逻辑仍使用其 clk_out，不可把参考 clk 输入当作 UI 时钟。

### 3. 主 OV5640 -> DDR3 -> HDMI 工程

工程：.local/ch47/ov5640_ddr3_hdmi.gprj

- 位流：.local/ch47/impl/pnr/ov5640_ddr3_hdmi.fs
- 当前保留位流 SHA256：D3CD6E1D3967B70441F22201E6A95FC143C7A99BDF63DE3F3B619E04EB23E09D
- 最近一次直接下载 User Code：0x0000D80B
- Status：0x70026020
- 板上曾观察到：D0/D1/D2/D3 全亮
- 主工程 LED：D0=DDR PLL lock，D1=DDR3 校准完成，D2=OV5640 SCCB 初始化完成，D3=摄像头/HDMI PLL lock

主工程曾同时显示 DDR 校准完成和摄像头初始化完成。HDMI 未接显示器，尚未证明画面内容。

## 失败的摄像头 DDR 诊断

### 原生 DDR 接口诊断

工程：.local/camera-ddr/camera_ddr_capture_bist.gprj

功能：等待 OV5640 初始化，抓取 16 个真实 RGB565 像素，写入 2 个 128-bit DDR burst，再读回比较。

- 综合、布局布线、位流生成成功
- 位流曾下载成功，User Code 0x000065D6
- F15 复位约束版本：D0 亮，D1/D2/D3 灭
- 曾测试 F15/B21 复位方向，不能把现象单独归因于复位按键

保留在磁盘的原生接口诊断是后续 F15 重编版本，SHA256 为 98D589900E7A6BDC80D6A23FAE96110DF18F034BD6FDAC69E3DEC1C160EA4E6A；早期 camera-ddr-capture-bist-20261006.log 中的 46226A... / 0x000065D6 对应初版，不能与当前文件视为同一构建。

### 原厂 DDR FIFO 包装器诊断

工程：.local/camera-ddr/camera_ddr_fifo_bist.gprj

功能：抓取 16 个真实像素，经过原厂 ddr3_ctrl_2port 的写 FIFO、DDR3、读 FIFO，再逐像素比较。

- F15 版本位流 SHA256：59260DB7E4746C3AE221E62B0014CEC3332B70A72C2B30869F8D9C46E18E29D5
- 综合、布局布线、位流生成成功
- 下载成功
- 用户观察：只有 D0 亮
- SRAM User Code：0x0000FC3C；Status：0x70026020

为验证主工程的复位约束，又生成了 B21 版本：

- 工程：.local/camera-ddr/camera_ddr_fifo_bist_b21.gprj
- 位流 SHA256：27F08F7004201D8818FBA2226A582EDEC4D1BD0B80FBBE849BB9CC57C08866C9
- User Code：0x0000BAE9
- 下载成功
- 用户观察：仍只有 D0 亮

结论：把 F15 改为 B21 没有解决 D1 不亮；当前失败诊断不能继续作为 DDR 硬件结论。

### 各位流的 LED 含义

| 位流 | D0 | D1 | D2 | D3 |
| --- | --- | --- | --- | --- |
| 主工程 | DDR PLL 锁定 | DDR 校准完成 | 摄像头 SCCB 初始化完成 | camera/HDMI PLL 锁定 |
| 独立固定模式 BIST | DDR PLL 锁定 | DDR 校准完成 | 固定模式读回通过 | 测试失败 |
| 摄像头原生/FIFO 诊断 | DDR PLL 锁定 | DDR 校准完成 | 摄像头初始化且捕获事件已接收 | 像素读回通过 |

后两类诊断的 D3 含义相反。摄像头诊断 D2/D3 灭不能判断 SCCB 本身是否失败，也不能判断测试是否数据不一致，因为 DDR 校准没完成时状态机还没进入这些阶段。JTAG Status/User Code 仅证明配置身份和下载状态，不包含 DDR 运行结果。

## 摄像头映射与初始化

当前工作副本使用 C:/Users/sc/Downloads/cam 实测映射：

- RST C14，SCL B13，SDA D15
- PCLK B18，HREF D14，VSYNC C13
- D0..D7：C15/B15/B16/D17/C17/E16/D16/B17
- 摄像头模块自带 25 MHz 振荡器；FPGA 不再输出 XCLK
- PWDN 未引出，必须在摄像头模块端固定低电平或有可靠下拉
- SCCB 已改为 100 kHz 开漏双向；读取 0x300A=0x56、0x300B=0x40

主工程上板 D2 曾亮，说明 SCCB 初始化链路已经通过；失败诊断中 D2 还包含“抓到 16 个像素”，不能把 D2 灭简单解释为 SCCB 失败。

工作副本移植了 cam/rtl/ov5640_ctrl.v 与 sccb_master.v，并与第 47 章 RGB 初始化表结合；主工程将摄像头复位保持约 1 ms，释放后等待约 20 ms 才启动 SCCB，初始化完成包含 0x5640 ID 检查。DVP_Capture 丢弃前 10 帧，不能以刚下载时瞬间 D2 灭判定无像素。

复位输入：原厂工程/通过的独立 BIST 使用 F15；当前主工程使用 B21，历史 cam 记录标为 S4。不能写成“S0/B21”。B21 诊断 CST 保留了拷贝自 F15 文件的 S0 注释，该注释过时，以实际 IO_LOC 为准。前一条进度消息把 F15/B21 说成旧版与当前版区别，没有板卡版本证据，撤回该说法；已证实的只有不同工程选择了不同输入球号、切换后诊断仍失败。

此前使用过 M20/B2/B1/J2/L18/A1 等旧摄像头映射，主工程 D0/D1/D3 亮、D2 灭；重新接线后仍未初始化。用户随后提供 Downloads/cam，核对并切换到上述 C14/B13/D15/B18 等映射及 SCCB 控制器后，主工程四灯全亮。旧映射只作历史参考。

PWDN：用户曾表示需要断电确认、随后重新接好线；没有单独的电气测量记录，因此不可声称已测量确认其电平。

## 编译与工具证据

所有上述工程均可在许可证恢复后完成 Gowin 综合、布局布线和位流生成。重复出现的警告：

- NL0002：pll_mDRP_intf 被优化器 swept；独立 BIST 和主工程也出现过，暂未证明是根因
- EX3628/EX2830/EX3671：原厂 DDR wrapper/FIFO 重复声明或隐式声明
- EX3791：FIFO 地址表达式 29 bit 截断到 28 bit
- EX3670：burst 实际连接 32 bit 常量到 1 bit 端口
- TA1132：camera_pclk 被识别为时钟但未创建时钟约束；DDR PHY 内部生成时钟也有同类提示

这些警告应在继续工作时清理，但目前不是已证明的板上故障根因。

工具实际路径：

- 综合/P&R：C:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe
- 下载：C:/Gowin/Gowin_V1.9.12_x64/Programmer/bin/programmer_cli.exe
- 用户最初提供的 V1.9.12.04_x64 路径本轮未找到 gw_sh.exe；以成功运行的 V1.9.12_x64 路径为准。
- 本地 build*.tcl 设置 use_sspi_as_gpio=1，以释放板上使用的复用 GPIO。
- 许可证已能支持成功编译；不应再重跑早期 MAC/临时网卡脚本，也不需要教育版。

PNR 报告显示主工程使用 6 个 PRIMARY、2 个 CLKDIV，FIFO 诊断使用 4 个 PRIMARY、1 个 CLKDIV；loc_clk50m 在主工程与诊断中的时钟树覆盖也不同。camera_pclk/B18 实际被布到 PRIMARY，因此 TA1132 应解释为缺少时钟创建/时序覆盖，不能直接说它一定用了普通布线。

无独立 SDC 的工程生成位流不等价于完整时序签核。本轮尚未完成对所有时钟、CDC、输入延时及 DDR 板级时序的签核。

## 目前最可靠的判断

1. 编译成功：主工程、独立 BIST、两个摄像头 DDR 诊断均成功生成位流。
2. 下载成功：JTAG/SRAM 下载稳定，器件 ID 正确，未写 Flash。
3. DDR 校准成功：独立固定模式 BIST D1 亮；主工程曾 D1 亮。
4. DDR 固定模式数据验证成功：独立 BIST D2 亮、D3 灭。
5. 摄像头像素经 DDR 写入/读回验证：尚未成功；原生接口和 FIFO 包装器两个诊断均停在 D0 亮。

DDR 诊断校准失败的根因尚未定位。下一轮应优先核对诊断顶层与主工程的 DDR PHY/PLL/时钟资源和启动复位差异；这只是排查方向，尚无波形证据证明其中哪一项导致失败。主工程保留了完整 HDMI/CLKDIV/摄像头 PLL 输出连接，失败诊断为了去掉 HDMI 改动了顶层时钟资源和 FIFO 时钟结构。下一轮可在已知 D1 通过的主顶层内增量加入诊断标志。

### 尚未上板验证的诊断代码问题

暂停前阅读源码发现以下风险，未修改、未编译修复版，不能把它们当作 D1 灭的已确认原因：

- FIFO 诊断只投喂 16 个 16-bit 像素，即 2 个 128-bit FIFO word，但 wr_bust_len=8，适配器条件为 wfifo_rcount >= wr_bust_len，因此校准即使通过也可能永远凑不够写入门槛。
- 该诊断地址范围 0..24 与一次 8 burst 请求不匹配；读 FIFO 会在写前预取，仍需确认清 FIFO、等待写完成及读取排程。
- 两个摄像头诊断同步一次 cap_toggle 脉冲，只在 ST_WAIT_CAP 消费事件；若摄像头捕获先于 DDR 校准完成，事件可能丢失，需改成保持完成标志或握手。
- FIFO 检查用延迟一拍的 rd_fire_d 同时持续读，不匹配/停止时仍可能有在途读；必须核对生成 FIFO 的输出模式/延迟及索引语义。
- 摄像头诊断没有完整地将读回失败、等待超时与校准失败分开显示；D3 灭不能区分这些情况。

DDR 参数依据现有说明/工作副本：MT41K128M16JT-125:K，x16，256 MiB，memory_clk 400 MHz，1:4，128-bit UI，BL8，SSTL 1.5 V。主工程 1280×720 RGB565，一帧 1,843,200 字节；读写同一地址范围，尚无独立多帧乒乓管理。

## 历史记录与证据范围

已参考用户指定的 Downloads/FPGA OV5640 Camera Interface and Verilog Capture Development (1).md 和 Downloads/cam。历史文件中的“不要移植第 47 章”“60K 必须重生成所有 IP”等是当时工作指令/判断，不替代本次用户授权；本次成功编译和 BIST 上板读回已证明当前所用 IP 至少可在现有环境工作。CST 文件头仍写 138K，但实际项目 XML/编译目标为 GW5AT-60B，不能仅凭注释认定器件不匹配。

旧 README 曾同时写“编译成功”和“许可证失败、没有本机位流”，并把未通过的摄像头像素测试描述成验证结果；本次整理已纠正。早期日志保留原样，有 pending、旧映射、旧位流哈希/旧 User Code 等信息，阅读时必须按对应构建区分。

原厂资料位于 C:/Users/sc/Documents/Dev/Hardware/fpga/小梅哥ACG720国产高云FPGA教学开发板资料/02_例程源码/GW5AT60K/第47章 OV5640摄像头采集HDMI显示屏显示；工作修改仅在 code/fpga/acg720-ddr3 内。原厂源码/IP/位流/日志放在被 .gitignore 忽略的 .local 下，许可证不写入本文。没有提交、推送或改动无关 PCB 文件。

## 明天的建议起点

1. 先下载主工程位流 ov5640_ddr3_hdmi.fs，确认 D0/D1/D2/D3 全亮。
2. 保留主工程的 DDR PLL、camera PLL、CLKDIV、DDR wrapper、复位和约束不动。
3. 只在主顶层加入粘滞状态位：DVP DataValid 见到、写 FIFO 入数增加、读 FIFO 出数增加；先不改变 DDR 物理接口。
4. 再加入有限窗口的写入/读回比较，并分别给出“捕获到像素”“DDR 命令发出”“读回一致”三个独立 LED 状态。
5. 再决定是否修复独立诊断：先处理写入门槛、地址范围、捕获事件保持及超时显示，再核对校准。
6. 清理重复声明、隐式网线、地址位宽截断，并补充 50 MHz、camera_pclk、PLL/DDR UI 时钟约束；分步验证，避免同时改变过多变量。

## 恢复命令（仅供明天续调，本次未执行）

先重新扫描下载器，USB location=546 只是今天记录。确认后，在 code/fpga/acg720-ddr3 目录使用以下 PowerShell 命令恢复已知主工程：

    $acg720Fs = (Resolve-Path .local/ch47/impl/pnr/ov5640_ddr3_hdmi.fs).Path
    & 'C:/Gowin/Gowin_V1.9.12_x64/Programmer/bin/programmer_cli.exe' --device GW5AT-60B --operation_index 2 --fsFile $acg720Fs --cable-index 1 --location 546 --frequency 15MHz

编译主工程：

    & 'C:/Gowin/Gowin_V1.9.12_x64/IDE/bin/gw_sh.exe' ./build.tcl

恢复前不要覆盖当前通过版本的位流及其报告，保留 SHA256 以便准确比较。

## 相关文件

- README.md
- build.tcl
- build_camera_ddr_bist.tcl
- build_camera_ddr_fifo_bist.tcl
- build_camera_ddr_fifo_bist_b21.tcl
- .local/ch47/ov5640_ddr3_hdmi.gprj
- .local/bist/ddr3_bist.gprj
- .local/camera-ddr/camera_ddr_capture_bist.gprj
- .local/camera-ddr/camera_ddr_fifo_bist_b21.gprj
- .local/logs/ddr3-bist-program-20261006.log

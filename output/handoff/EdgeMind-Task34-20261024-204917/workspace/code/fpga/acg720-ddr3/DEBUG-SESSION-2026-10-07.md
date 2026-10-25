# ACG720 DDR3 续调（2026-10-07）

## 基线复核

继续用户 10 月 6 日交接，许可证已解决；不再改 MAC/网卡或安装教育版。仅 SRAM 下载，未写外部 Flash。

- JTAG：FT2CH，location 546，器件 ID 0x0001481B。
- 已核对主工程与固定模式 BIST 的 SHA256，均与交接一致。
- 恢复 `.local/ch47/impl/pnr/ov5640_ddr3_hdmi.fs`，User Code `0x0000D80B`，Status `0x70026020`。
- 用户再次明确反馈：D0/D1/D2/D3 全亮。当前接线下 DDR 校准和 OV5640 初始化可通过。
- 恢复日志：`.local/logs/restore-main-20261007.log`。

## 保留主工程结构的被动观测版

工程 `.local/main-observe/main_observe.gprj`；入口 `build_main_observe.tcl`。从已知主工程复制源码，原主工程及通过的 BIST 位流均未覆盖。

只增加状态寄存器及 LED4..7 输出；原 camera PLL、DDR PLL、CLKDIV、DDR/FIFO 控制、复位、HDMI 和摄像头引脚连接保持原有逻辑。增加探针后布局会变化，不能认为物理布局完全不变。

| 灯 | 含义 |
| --- | --- |
| D0 | DDR PLL 锁定（实时） |
| D1 | DDR 校准完成（实时） |
| D2 | OV5640 初始化完成（实时） |
| D3 | camera/HDMI PLL 锁定（实时） |
| D4 | DVP DataValid 曾有效，摄像头复位清除 |
| D5 | 写 FIFO 在非复位、非满时曾接收写使能，系统复位清除 |
| D6 | DDR 原生写命令及写数据曾同时握手，系统/UI 复位清除 |
| D7 | D6 置位后曾出现 DDR rd_data_valid，系统/UI 复位清除 |

D4..7 是粘滞活动标志，不表示连续无丢数或数据比较通过。D7 不保证返回的地址就是先前写入的地址。

LED4..7 球号 K22/J22/H22/M21 已从资料包原厂管脚表核对。

本机综合、布局布线及位流生成成功，6 个 PRIMARY、2 个 CLKDIV、2 个 PLLA，与主工程资源数量相同。仍存在历史未创建时钟、重复声明等警告，尚未完成完整时序签核。

- 位流：`.local/main-observe/impl/pnr/main_observe.fs`
- SHA256：`5ECFAC90A00CA053CF01F9E78769D46AED892E8C9372848AE5232526E5CBE863`
- SRAM 下载成功，User Code `0x00007E20`，Status `0x70026020`。
- 用户 LED 反馈：D1 不亮；补充确认 D0/D2/D3/D4/D5 都亮。D6/D7 未单独明确反馈。
- 编译日志：`.local/logs/main-observe-build-20261007.log`
- 下载日志：`.local/logs/main-observe-program-20261007.log`
- 源码改动：`.local/main-observe/passive-probes.patch`
- 基线源码/位流指纹：`.local/main-observe/baseline-sha256.json`

## PLL mDRP 控制权缺陷与修正实验

观测版保留了原时钟拓扑仍未校准，但 D0/D3 锁定，D2 摄像头初始化、D4 像素、D5 FIFO 输入均有活动。尚不能由此证明布局布线本身是根因。

查到可以直接由源码证明的缺陷：主顶层把 DDR PLL 的 `pll_init_bypass` 固定为 0；`pll_init.v` 第 388..391 行仅在 bypass=1 时把外部 MDOPC/MDAINC/MDWDI 和 MDRDO 接通。因此 DDR `pll_stop` 的适配器虽然例化，却被隔离并综合删除。此前通过版本也有这个缺陷，曾经通过不代表该控制路径正确；不能据此断言每次失败都由这一项引起。

依据：[高云 UG306 的 PLL mDRP 控制权和切换流程](https://cdn.gowinsemi.com.cn/UG306.pdf)，以及[芯路恒/小梅哥管理员 2025-10-17 针对 25K、60K 的更新方法](https://fpga.cn/forum.php?mod=viewthread&tid=29815)。DDR 的 `pll_stop` 必须能控制 memory_clk；高云 DDR3 IP 指南第 4.4.4 节另有说明。

在独立副本 `.local/main-mdrp/` 中，仅将原两级 lock 延迟改为 16 级，将其末级接 `pll_init_bypass`、适配器 pll_lock 与 wr 的使能条件。延迟寄存器额外提供零初值及外部复位，其他 PLL/IP 实现不变。入口 `build_main_mdrp.tcl`，差异 `.local/main-mdrp/mdrp-handoff.patch`。

- 综合、P&R、位流生成完成；网表保留 `pll_mDRP_intf u_pll_mDRP_intf`，之前的 NL0002 删除警告消失。
- 位流 `.local/main-mdrp/impl/pnr/main_mdrp.fs`
- SHA256 `A95113AE7721BD6BB3076DE045E29DE152222B561802D66D55A824AA45D9E07C`
- SRAM 下载完成，User Code `0x00002D41`，Status `0x70026020`。
- LED 定义与观测版一致；用户结果待确认。
- 日志 `.local/logs/main-mdrp-build-20261007.log`、`.local/logs/main-mdrp-program-20261007.log`。

## 读回比较器准备

`rtl/ddr_readback_monitor.v` 为独立的被动监视模块，暂未接入或下载。依次观察地址 0、8、…、120 的 16 个 128-bit 块；记录目标读命令之前最近一次握手成功的写数据，按全部读命令/响应的序号匹配返回值。只有 16 个地址均比较通过才置 pass；数据不一致或已发出的目标读命令超时置 fail。等待目标写/读命令期间不记超时，pass 后停止。样本可来自不同帧，不是整帧比对。

从 [Icarus Windows 发行页面](https://www.bleyer.org/icarus/) 下载成品安装器，在 `.local/tools/iverilog/` 安装；实际版本 12.0 (devel)，不是最新稳定版本。未自行实现仿真工具。安装器 SHA256 `A614057374DFAED5DA0FE454CDEB410E54981FD85DBD28BD472F4CCB765DEB84` 仅作身份记录。

`tests/ddr_readback_monitor_tb.v` 仿真已通过：无写入的预取、握手未接受、写覆盖、读响应顺序、同时发命令和回数据、16 地址完成、错误注入、无返回超时、UI 复位及序号回绕。日志 `.local/logs/ddr-readback-monitor-sim-20261007.log`。此仿真验证比较器自身，不模拟加密 DDR PHY，不代表实板像素读回已通过。

## 尚待完成

先根据八灯判断活动链路，再进行地址可对应的真实像素读回比较。旧独立诊断的校准失败原因仍未证实；FIFO 诊断只写 2 个 128-bit 块却设 8 块门槛、捕获事件可能丢失等代码缺陷仍保留作历史证据。

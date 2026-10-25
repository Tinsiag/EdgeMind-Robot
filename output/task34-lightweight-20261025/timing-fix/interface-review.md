# 接口时序核对（尚未签核）

2026-10-25。时序修正版使用 place_option=1、route_option=2，02:32:39 开始 PNR，网表 SHA-256 为 `dda4c6bd1d13f96901a76453815f179695b766bfde0581145846e47b69b2e115`。完整 52 组 RTL / 61 项主机回归通过。综合 LUT=35212、寄存器=27193、ALU=5177、BSRAM=81；sys 估算 49.479 MHz，27 级。它们不是最终 PNR 资源或签核数据。

## 新找到的官方资料

入口为 https://www.gowinsemi.com/en/support/ip_detail/14/ （安装目录 `IDE/ipcore/DDR3/doc/ddr3.html` 指向此地址）。此前错误页面不能作为资料证据。

- IPUG281-2.6E，2026-01-16：https://www.gowinsemi.com/upload/database_doc/2009/document/696a8c052f84e.pdf ，SHA-256 `9adb6068b8fefe8db944609fdc5146eed58fda902a267ba22da5f36d78656b39`。
- DDR3 Reference Design 5.8E：https://www.gowinsemi.com/upload/database_doc/2010/document/67cebaccb9842.zip ，SHA-256 `39d0d30584a7c1740d5921c1d7934b334f5fc2db7909d99e4283a25e9a75cc03`。
- 文件、文本和下载清单保存在 `output/task34-resume-20261024/tool-docs/`，实际文件头已核对为 PDF/ZIP。

## DDR 复位：确认存在顶层接口缺口

IPUG281 第 10 页（PDF 第 17 页）4.4.3 明确要求 rst_n 在送入 IP 前由 clk 同步释放。此前 `rtl/a741_top.v` 的 `memory.rst_n` 直接连接 stop_n。`final-path-fix` 已增加 clk 域异步置位、同步释放的 reset_sync，并让 DDR 管理逻辑和 mDRP 使用该同步复位；PLL 的 LOCK 仍直连 IP 的 pll_lock，PLL 自身复位不依赖其 LOCK。此次发现不表示这个改动会消除 IP 内部全部 recovery 违例。

第一轮时序修正版 PNR 已完成，证据在 `pnr-place1/`。上述复位修正随后实施；包含该修正的 52 组 RTL、61 项主机回归已通过，证据在 `../final-path-fix/tests/`。对应整板 PNR 于 02:56:50 启动，03:16:32左右完成，归档在 `../final-path-fix/pnr-place1/`。DDR内部recovery仍负（最差-2.468ns），同步顶层复位并不等于签核内部PHY。

## DDR 内部时钟例外：有官方示例，适配仍待核对

官方 ZIP 中 5A25K 和 5A138K 的 400 MHz、1:4 示例提供 SDC，将参考时钟、400 MHz 和 100 MHz 三域两两声明为异步。已逐字提取到 `ref-DDR3_MC_PHY_1vs4_5a25k.sdc` 和 `ref-DDR3_MC_PHY_1vs4_5a138k.sdc`。本板的厂家第 38 章示例没有 SDC。

当前 60B DDR 配置与官方 25B 示例同为 IP 配置版本 3.0、400 MHz、1:4，但器件、数据位宽和部分 DDR 参数不同。参考示例不是本工程时序签核，不能直接复制整组异步例外。若适配官方 IP 内部例外，需要限定在已核对的 memory 层级，保留用户 UI 同步通路、用户 CDC、外部 I/O 以及最小脉宽检查。

第 11 页还确认：没有 PLL enclk 控制口的 GW5A 器件应使用 mDRP 适配器控制 pll_stop。当前工程已沿用厂家 mDRP 接法；未添加任意延迟链。

## HDMI 时钟

旧轻量版 PNR 报告已显示 serial_clk 使用 PRIMARY 和 BANK10_BANK11_HCLK0，并非普通 fabric 时钟。其 hdmi/serial_reset 三个 FF 的 165 MHz 最小脉宽违例为 -0.555 ns，来自 late/early 时钟传播计算。添加泛化的 BUFG 约束不能直接称为修复；未删除复位同步器、降低检查要求或屏蔽 MPW。

后续隔离实验见`hdmi-clock-audit/REVIEW.md`。使用闲置PLL CLKOUT0产生独立33MHz复位时钟并直接生成高有效三级同步复位，配合route_option=1，隔离工程全部时序检查通过，四路串化器RESET仍完整接受recovery/removal检查。此候选已经纳入`../interface-and-telemetry-fix/`；完整52/61回归通过，整板综合/PNR未完成，不能把隔离结果当整板签核。

## RGMII

输入 max=2 ns、min=-0.5 ns 仍是未完成板级核实的初始预算。原理图的 RXDLY/TXDLY 上拉不等于实测，不据此凭空修改预算或叠加 FPGA 延迟。尚无新的实板波形或冷启动数据。

已取得并核对RTL8211F Rev.1.2公开镜像。图15和表58证明旧预算混用了无延迟模式的最小偏斜，详见`rgmii-budget-review.md`；尚未修改主工程SDC，仍需加入可靠的板级预算。

尚未烧录、Reprogram、ARM 或运动。

# 用户确认兼容的480屏参考

`TFT_CTRL_480_270_16b.v`原样复制自用户指定官方例程：

`C:/Users/sc/Documents/Dev/Hardware/fpga/4.3inchTFT/demos/ac620/AC620_TFT43/rtl/TFT_CTRL_480_270_16b.v`

SHA256：`50ec82be5dc9429658eea27730f271833d527af08014a0c42b1434e74f02ed9e`。保留原始作者/工作室注释，不更改此文件；它仅作为回归参考，不替代ACG720的管脚或视频工程。文件名270不代表有效高度270，实际有效区为480×272。

原顶层NIOS_TFT43把clk9m_clk连接到此模块；生成的mysystem.v将它接到altpll c2；生成PLL配置为50MHz输入、clk2_multiply_by=1、clk2_divide_by=10，所以静态实际5MHz，不能仅凭Clk9M端口名推为9MHz。当前匹配固定5MHz/50%占空比、525×286总扫描，HS低41点、VS低10行，DE起点42/11。

`tft480_reference_tb`把未改动的原控制器与本机驱动逐采样点对照两个完整帧的DE/HS/VS。参数文字、视频并行、复位、背光和实际管脚/板级时序另行验证。此一致性不证明实物显示已经通过。

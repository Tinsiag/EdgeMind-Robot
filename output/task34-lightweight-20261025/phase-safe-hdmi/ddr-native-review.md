# 原厂DDR初始化路径约束审查

约束候选尚未合入主工程，不能据此声称整板通过。

依据：官方DDR3 RefDesign 5.8E的5A25K/5A138K、400MHz、1:4、IP配置版本3.0示例明确将参考clk、PHY高速时钟、UI时钟两两异步。其全域例外未直接复制到本工程。IPUG281-2.6E 4.4.2～4.4.4说明参考clk仅生成同步与控制，UI用户逻辑须与clk_out同步，初始化结束后才允许访问。

此前仅查看加密综合文件，无法追踪内部实现。现从本板第38章原始ZIP提取厂商**已经提供的明文仿真网表**`ddr3_memory_interface.vo`，没有解密或修改IP。保存为`output/task34-resume-20261024/tool-docs/board-60b-ddr3-memory-interface.vo`；它是GW5AT-60B对应文件，不是25K样例的替代品。

- 22880～22902行：ddr_rsti_reg为三级参考clk链，最后一级Q直接驱动ddr_rst。
- 23005行附近：fclkdiv的RESETN是ddr_rst取反。因此UI时钟启动与该复位本身相关，不能把它等同于运行中跨域数据传输。PHY串化器复位释放之后仍需原厂初始化/训练。
- 49195和49379行附近：两个read_rclksel_conf寄存器D固定VCC、CLEAR为ddr_rst，且仅在校准状态使能时置位；复位之间最多改变一次。
- 这两个标志与独立的hold_i经过LUT到DQS HOLD；候选仅例外标志到HOLD，**不例外hold_i**，也不切控制器数据、UI用户逻辑、FIFO、外部I/O、HDMI或最小脉宽。

`ddr-native-constraints-candidate.sdc`仅适配上述两类已有官方例外支持、且本板网表可核对的IP初始化通路。后续必须查看例外报告命中范围和仍受检查的路径；若出现未命中、范围扩大或其他负余量，不能按零计数验收。该审查不代表DDR实板初始化、读写或断电验证通过。

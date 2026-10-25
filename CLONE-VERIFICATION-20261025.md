# GitHub独立克隆验证

2026-10-25约09:56～10:03（北京时间），直接从GitHub的`main`新克隆源码检查点`87c97b7ceb8018fb3edc88cce0c29f15515d4ec9`，使用独立目录及新建Python虚拟环境。没有复制旧工作区的平台、DLL或测试缓存；公共系统工具与WSL仍使用本机安装。

| 检查 | 实际结果 |
| --- | --- |
| GitHub clone / LFS实体下载 | 完成；克隆结束后`git lfs fsck`通过 |
| Python隔离环境 | 3.12.14，新venv；requirements-dev-lock.txt全部安装成功 |
| 原厂例程恢复 | 三份归档全部SHA校验通过，恢复成功 |
| 平台生成 | motion-lidar及fusion+tft480均成功 |
| PicoRV32裸机镜像 | Zig 0.13.0生成920字节，与原工作区二进制及hex哈希相同 |
| Windows建图DLL | 从克隆源码成功构建 |
| 完整回归 | **55组RTL、61项Python通过**；实际测试期间全部输入哈希未变 |
| Flash工具离线回归 | **9项通过**，使用模拟Programmer，不接触硬件 |
| 新综合/PNR/烧录/运动 | 本次克隆检查未执行 |

原始日志、输入清单和机器结果位于[clone-evidence](code/camera-car-control/a741-fpga-fusion/verification/handoff-20261025/clone-evidence/)，总记录为`CLONE-RESULT.json`。该记录的绝对路径属于本机独立克隆目录，换机器后应按交接文档重跑，不复用这些绝对路径。

本次检查还发现Windows的`core.autocrlf=true`会使固件C/汇编/链接脚本变成CRLF，从而在重新生成manifest时改变源码哈希。最终打包提交已将`firmware/**`固定为LF；三个源文件的Git对象、原工作区已通过测试的字节及克隆后规范化字节SHA完全相同。该修正只改变Git检出属性，没有修改RTL、裸机源程序或指令镜像。机器记录中保存了逐文件比较。

**连续突发障碍诊断仍失败，未列入55组通过**。本次验证证明从GitHub能够恢复并运行已有回归，不代表连续绕障、整板时序、实车或断电保留已验收。继续步骤见[交接文档](HANDOFF-20261025.md)，直接使用的[下一位AI提示词](NEXT-AI-PROMPT-20261025.md)也已提供。

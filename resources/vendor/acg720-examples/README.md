# ACG720 构建输入

这是此前用户提供并已在本机使用的第38、47、59章例程源文件，供新克隆恢复构建环境。
第38章和第59章ZIP保持原字节；第47章本机只有解压源码，因此`ch47-local-source.zip`由原`src/`重新打包，不能称为厂家原始ZIP。身份见`manifest.json`。

在仓库根执行`python scripts/handoff/restore_environment.py`，会先校验全部归档，再恢复到原准备脚本使用的`.local/environment/examples/GW5AT60K`。已有文件不同则停止，不覆盖。`--check`只检查，不复制。

原厂IP及例程的权利归原作者；保留原资料内的版权声明。这些归档不是本项目的可交付固件。

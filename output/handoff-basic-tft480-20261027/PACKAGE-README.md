# 本地交接与增量备份

本次不提交、不推送GitHub。直接在原本机接手时，以根HANDOFF-20261027.md和NEXT-AI-PROMPT-20261027.md为入口，保留当前工作区，不需要应用补丁。

`EdgeMind-Robot-basic-tft480-handoff-20261027.zip` 是**本地增量包，不是独立可编译仓库或可刷写固件**。

包内包含：

- `worktree.patch`：以 `6a32a56ee1755c8353116ace9afed6631ba57d9c` 为基准的限定范围Git二进制补丁，包含修改和删除。
- `new-files/`：上述基准未跟踪的当前活动工程源码、测试和本次根交接文档。
- `current-source/`：SOURCE-MANIFEST所列活动源码的**原始字节快照**。Git可能按.gitattributes转换CRLF/LF，仅靠补丁不一定恢复相同字节；该快照用于在备用恢复目录中还原准确的源码/固件manifest输入。
- `SOURCE-MANIFEST.json`、`PATCH-MANIFEST.json`、`PACKAGE-MANIFEST.json`：当前源文件、新文件、补丁和证据的哈希/状态。
- `evidence/`：当前4项局部回归及输入SHA、中间版整链/软件日志、仿真图、先前被用户停止的旧构建网表/布局数据库、已prepare但未综合的新平台文件。
- `diagnosis/`：旧资源层级、停止原因、原输入和被裁剪代码的备份；均是历史参考，不在当前活动编译路径。
- `USER-OPTIMIZATION-IDEAS-1.md`：用户提供的AI整理思路原文；`STATUS.json`明确验证边界。

## 校验

先用旁边的 `.zip.sha256` 对照 `Get-FileHash -Algorithm SHA256`。解压到**新的临时目录**，按 `PACKAGE-MANIFEST.json` 逐项校验。用户1.md期望SHA：

```text
46be88c27448368f8cfaadbf279e7ba2d76a81ccdf25a812920e4fb66ae68a48
```

包不包含ZIP自身的哈希条目，避免循环依赖；ZIP哈希单列。包内未携带编译器/模板zip或完整Git LFS素材；这些仍需保留本机已有依赖。包内源码的存在不表示全套验证/综合已经完成。

## 备用目录恢复（不要对原脏现场执行）

1. 准备一个已检出上述基础提交、干净、所需LFS文件已就绪的**备用仓库目录**。核对 `git rev-parse HEAD` 和 `git status --short`；不匹配则停止。
2. 核对补丁哈希，先 `git apply --check --binary <解压目录>/worktree.patch`；通过后再应用。不猜测基础提交，不强制覆盖冲突。
3. 按清单复制 `new-files/` 的同名相对路径；若目标已有不同内容先停止，不覆盖。
4. 仅在上述基础干净检查和补丁应用均已成功、且备用目录没有新增人工修改时，将 `current-source/` 的同名相对路径还原到该备用目录，消除Git换行转换差异。再以SOURCE-MANIFEST逐项核对原始字节及已删除文件。**不要对原脏现场执行这步。**
5. 证据/诊断资料只存入备用目录的output交接区，**不要把diagnosis中的旧导航/HDMI源码复制回活动工程**。
6. 恢复后仍按暂停状态处理。只有用户明确继续才做离线工作；未明确恢复PNR不启动布线，不写硬件。

此包不包含本仓库其他项目/模型的独立未提交修改。原现场和相邻工作区保持原样。普通构建与screen-test电机锁不同，当前无新.fs及烧录结果。

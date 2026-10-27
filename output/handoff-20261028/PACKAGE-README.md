# 2026-10-28 EdgeMind-Robot 交接包

先读 `root/HANDOFF-20261028.md` 和 `root/NEXT-AI-PROMPT-20261028.md`。

本阅读包记录暂停时的源码/硬件状态、800 屏烧录成功证据、运动版三次 PR0004 失败证据、布线优化思路和屏幕接线注意事项。它只挑选少量文档和日志，**不是完整恢复包**。完整恢复请使用同级外部 `../EdgeMind-Robot-handoff-20261028.zip`，其中包含当前源码、所有 Git 可见资料、真实 d5 位流、精确构建输入快照和可恢复的历史证据；其外层 SHA 在 `../EdgeMind-Robot-handoff-20261028.zip.sha256`。

`CONTENTS-SHA256.json` 是包内文件清单；外层 ZIP 另有 SHA-256。

包排除 `.git`、凭据、Python 虚拟环境、Gowin 安装器/程序、原厂安装资料缓存以及重复的旧交接 ZIP 和 `output/handoff/` 历史展开副本。原始 CAD、源码和各日期证据仍在包/仓库中，排除项记录在完整 ZIP 的 `HANDOFF-METADATA/EXCLUSIONS.json`。完整包不会复制 Git 对象数据库。包内 `HANDOFF-METADATA/PACKAGE-MANIFEST.json` 是全部实际归档文件的相对路径、长度及 SHA-256 清单，包外 `../EdgeMind-Robot-handoff-20261028-VERIFY.json` 是验证结果。不要在恢复前运行综合或把历史 `.fs` 直接烧录。

## 从 GitHub 获取

安装 Git 和 Git LFS，克隆 `https://github.com/Tinsiag/EdgeMind-Robot.git`，在仓库内执行 `git lfs pull`。GitHub 的普通源码下载可能只包含 LFS 指针，不能用几百字节的指针冒充 ZIP。完整包名为 `output/EdgeMind-Robot-handoff-20261028.zip`，外层SHA在同名 `.zip.sha256`；Git LFS本身也会核对对象SHA。

仅验证包、不执行硬件操作（从仓库根目录运行；新机可使用自己的Python3解释器）：

```powershell
Get-FileHash output/EdgeMind-Robot-handoff-20261028.zip -Algorithm SHA256
& code/camera-car-control/.venv/Scripts/python.exe -X utf8 scripts/handoff/package_20261028.py verify output/EdgeMind-Robot-handoff-20261028.zip
```

将完整ZIP解压到新的空目录，包内根目录就是项目根结构。不要覆盖正在工作的仓库；文件长度和SHA通过上面的验证脚本逐项核对。真实d5位流会出现在 `output/tft800-official-20261028/build-evidence-final/a741.fs`，其SHA必须为 `d5e558ad68ac665f889fcec651262714e52e40774853e5368c51f0fc2a1ad62b`。它是锁电机版本，不能驱动车轮。

## 精确构建输入和环境

d5原始输入存为平铺文件，避免Windows长路径；映射表为 `output/tft800-official-20261028/source-snapshot-d5/SOURCE-MAP.json`。可恢复到另一个空目录（这只复制并核对111个输入，不构建/烧录）：

```powershell
& code/camera-car-control/.venv/Scripts/python.exe -X utf8 scripts/handoff/package_20261028.py restore-inputs output/tft800-official-20261028/source-snapshot-d5/SOURCE-MAP.json C:/Dev/EdgeMind-d5-inputs
```

每次motion attempt也有各自 `source-snapshot/SOURCE-MAP.json`，不要混合。输入快照不是完整工具环境；当前源码、原始构建输入及最终位流的适用范围见根交接。旧`.gprj`和审查脚本有绝对路径，新机需重定向或在明确恢复开发后使用prepare生成新目录，不直接执行旧工程文件。

恢复用官方依赖位于 `output/handoff-20261028/rebuild-inputs/examples/GW5AT60K/`，可传给构建器 `--examples`。第28章为留档源码，第38/59章为原ZIP，第47章为已标注的本地源码重打包ZIP；来源清单、哈希在 `rebuild-inputs/`，不含完整厂家资料库或EDA安装器。安装Gowin V1.9.12.04、按 `code/camera-car-control/requirements-dev-lock.txt` 重建Python环境，工具版本和WSL信息见根交接。

现在用户要求暂停；下载、解包、校验可以做，恢复开发需要用户后续明确继续。文档中旧“未授权/正在构建”等是历史，当前只看根 `HANDOFF-20261028.md` 和 `AGENTS.md` 最新节。

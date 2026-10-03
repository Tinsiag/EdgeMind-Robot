# XT60完整模型补充文件

2026-10-03。本机 KiCad 10 自带的 `Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal` 封装引用了一个实际缺失的 STEP。此处补齐完整模型，保持封装焊盘、孔位和库标识不变。

模型来源是项目已有的 `../../3dmodels/XT60PW-M.step`，由 [Northeastern Rover Electrical Team 的公开模型库](https://cadlab.io/project/25916/master/files/3dmodels/rover-lib.3dshapes) 提供。它包含外壳、两组触点、焊接端子和固定片，共七个实体；不是简化方块。来源未提供独立模型许可证，亦未证明是厂家原始 CAD；单独公开分发前应核对许可。

使用 FreeCAD/OpenCascade 对原始完整模型做刚体变换，毫米坐标为：`x'=-x+3.6，y'=z+15.35，z'=y+4.2`。变换为旋转与平移，不是镜像。端子中心对应 stock 封装的 `(0,0)` 与 `(7.2,0)`，固定片对应其 `(-3.15,-6)` 与 `(10.35,-6)`。KiCad 的模型坐标与电路板坐标采用相反的纵轴方向。模型保留七个实体，恢复了黄色外壳与金属部件的显示色。

当前机器已把文件安装到：

`D:/KiCad/10.0/share/kicad/3dmodels/Connector_AMASS.3dshapes/AMASS_XT60PW-M_1x02_P7.20mm_Horizontal.step`

2026-10-03 用户要求同步 PCB 后，最新板上 CN1 改用 `${KIPRJMOD}/3dmodels/AMASS_XT60PW-M_1x02_P7.20mm_Horizontal.step`，内容与本目录对齐后的完整模型一致，模型变换和焊盘几何不变。复制完整项目到其他机器时，该 PCB 模型随项目携带；其他 stock 元件仍需安装对应 KiCad 10 模型库。

若在其他机器上单独从 stock 库重新加载 XT60 封装，而官方安装中仍缺少它，可将本目录同名 STEP 放入该机器 `${KICAD10_3DMODEL_DIR}/Connector_AMASS.3dshapes/`；不要覆盖不同来源的已存在模型，先核对外形。重新加载封装后，应检查板上 CN1 模型是否仍指向项目内文件。

OpenCascade 已成功读取七个有颜色的非空网格。机械公差、板厚适配和插拔空间仍需对照厂家图纸与实物验收。AT8236 当前只建双排排母，未虚构模块本体或插接高度。

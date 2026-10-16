"""Render current motor wiring and mark the old diagrams as historical.

Requires reportlab/pypdf. Run from any directory. Authoritative signal mapping
is read from the 2026-10-14 Markdown table; no physical header pins are inferred.
Original 2026-10-10 PDF/PNG bytes are copied into archive before replacement.
"""
from pathlib import Path
import hashlib
import io
import re
import shutil

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf"
ARCHIVE = OUT / "archive/2026-10-10"
DOCUMENT = ROOT / "doc/电机/ACG720与现有电源板接线_2026-10-14.md"
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
pdfmetrics.registerFont(TTFont("Latin", "/usr/share/fonts/noto/NotoSans-Regular.ttf"))
FONT = "STSong-Light"


def text(c, x, y, value, size=13, color="#18283c"):
    c.setFillColor(color)
    # CID fonts have unreliable Latin advance widths in some PDF viewers.
    # Use Helvetica for ASCII runs and the CJK font only for Chinese runs.
    for run in re.findall(r"[\x00-\x7f]+|[^\x00-\x7f]+", value):
        font = "Latin" if run.isascii() else FONT
        c.setFont(font, size)
        c.drawString(x, y, run)
        x += pdfmetrics.stringWidth(run, font, size)


def rounded(c, x, y, w, h, fill, stroke=None):
    c.setFillColor(fill)
    c.setStrokeColor(stroke or fill)
    c.roundRect(x, y, w, h, 6, fill=1, stroke=bool(stroke))


def rows():
    result = []
    for line in DOCUMENT.read_text().splitlines():
        cells = [s.strip() for s in line.split("|")[1:-1]]
        if len(cells) == 5 and cells[1].startswith(("left_", "right_")):
            result.append(cells)
    assert len(result) == 8
    return result


def render_current():
    OUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT / "ACG720-AT8236-wiring-2026-10-14.pdf"), pagesize=(1190, 842))
    c.setTitle("ACG720 AT8236 - 2026-10-14 current package-ball wiring")
    c.setFillColor("#f4f7fb")
    c.rect(0, 0, 1190, 842, fill=1, stroke=0)
    text(c, 40, 795, "ACG720 / AT8236 维修后信号接线", 25)
    text(c, 40, 770, "2026-10-14  |  用户报告的新球号  |  两台电机 / 两块模块各用 A 通道", 13)
    rounded(c, 40, 711, 1110, 43, "#fff0df")
    text(c, 55, 733, "暂不接回 FPGA 3.3 V 到外部板；短路根因未确认。此图不是重新上电许可。", 16, "#922c17")
    text(c, 55, 718, "球号不等于排针针号；物理连接器位置、各 IO Bank 实际 VCCIO 及供电仍须核对。", 11, "#922c17")
    text(c, 50, 684, "FPGA 信号 / 球号（非连接器针号）", 16)
    text(c, 720, 684, "电源 / 驱动板八针接口", 16)
    mapping = rows()
    for i, (net, port, ball, board, direction) in enumerate(mapping):
        y = 635 - i * 38
        color = "#226aa7" if direction == "输出" else "#137c65"
        rounded(c, 50, y, 400, 30, "#ffffff", "#cdd7e3")
        rounded(c, 710, y, 430, 30, "#ffffff", "#cdd7e3")
        text(c, 65, y+9, f"{port}    |    {ball}", 14)
        text(c, 725, y+9, f"{board}    |    {net}", 14)
        c.setStrokeColor(color)
        c.setLineWidth(2)
        start, end = (460, 700) if direction == "输出" else (700, 460)
        c.line(start, y+15, end, y+15)
        sign = 1 if end > start else -1
        c.line(end, y+15, end-sign*8, y+20)
        c.line(end, y+15, end-sign*8, y+10)
        text(c, 534, y+22, "控制输出" if direction == "输出" else "编码器反馈", 10, color)
    text(c, 50, 337, "板端完整针序：按用户截图从左向右 1-8；方形焊盘为 1 脚。", 13)
    headers = {
        "R / 右电机接口（图 1）": ["RF_ENB", "RF_ENA", "3.3V", "GND", "RAIN1", "RAIN2", "RBIN1", "RBIN2"],
        "L / 左电机接口（图 2）": ["LAIN1", "LAIN2", "LBIN1", "LBIN2", "GND", "3.3V", "LF_ENA", "LF_ENB"],
    }
    for k, (title, nets) in enumerate(headers.items()):
        x = 50 + k*555
        text(c, x, 310, title, 14)
        for i, net in enumerate(nets):
            px = x + i*65
            rounded(c, px, 250, 61, 46, "#ffffff", "#cdd7e3")
            text(c, px+25, 280, str(i+1), 12)
            text(c, px+4, 260, net, 10)
    notes = [
        "1. 公共地：L-5 / R-4 接实板已确认的 FPGA GND；先断电核对是否同网。",
        "2. L-6 / R-3 是外部 3.3 V 网络：供电方案待排查确认，不能悬空后直接运行，也不能盲目并联电源。",
        "3. 仅用 A 通道时：确认模块方向后，L-3 / L-4、R-7 / R-8 接本板 GND；电机只接桥输出。",
        "4. 不把 VM、5 V 或 AOUT 接到 FPGA IO；旧位流不可直接复用，须重建并审核实际引脚 / 电平 / 时序。",
        "5. 左右电机、编码器线束及摄像头需独立核对。LED 只反映逻辑状态，不证明电气安全。",
    ]
    for i, note in enumerate(notes):
        text(c, 50, 221-i*25, note, 12)
    text(c, 50, 62, "来源：用户 2026-10-14 接线描述和两张 PCB 网络截图；当前文档及 CST 已同步。", 11)
    text(c, 50, 42, "闭环新位流已通过 Gowin P&R / 报告审查，详见构建记录；未下载，维修后实板未验证。", 11, "#922c17")
    c.showPage()
    c.save()


def stamp_historical():
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    manifest = []
    for path in sorted(OUT.glob("ACG720-AT8236-*-2026-10-10.*")):
        if path.suffix not in {".pdf", ".png"}:
            continue
        original = ARCHIVE / path.name
        if not original.exists():
            shutil.copyfile(path, original)
        manifest.append(f"{hashlib.sha256(original.read_bytes()).hexdigest()}  {original.name}")
        if path.suffix != ".pdf":
            continue
        writer = PdfWriter()
        for page in PdfReader(original).pages:
            w, h = float(page.mediabox.width), float(page.mediabox.height)
            band = 100
            merged = writer.add_blank_page(width=w, height=h+band)
            merged.merge_page(page)
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=(w, h+band))
            c.setFillColor("#fff0df")
            c.rect(0, h, w, band, fill=1, stroke=0)
            text(c, 25, h+65, "历史旧接线图 / OBSOLETE PINOUT - 不适用于 2026-10-14 新接线", 22, "#922c17")
            text(c, 25, h+37, "改用 ACG720-AT8236-wiring-2026-10-14.pdf；下方旧管脚和供电分支不能继续照接。", 17, "#922c17")
            text(c, 25, h+13, "暂不接回 FPGA 3.3 V 到外部板。原图字节在 archive/2026-10-10/ 保留供追溯。", 15, "#922c17")
            c.save()
            buffer.seek(0)
            merged.merge_page(PdfReader(buffer).pages[0])
        with path.open("wb") as stream:
            writer.write(stream)
    (ARCHIVE / "SHA256SUMS").write_text("\n".join(manifest)+"\n")
    (ARCHIVE / "README.md").write_text("# 2026-10-10 历史原图归档\n\n这些文件保留旧图原始字节（见 SHA256SUMS），只用于追溯，不用于新接线。当前图为 ../../ACG720-AT8236-wiring-2026-10-14.pdf。原路径 PDF/PNG 已增加旧图失效提示。不要按本目录旧球号、P7 针号或供电分支重新连接。\n")


if __name__ == "__main__":
    render_current()
    stamp_historical()

from pathlib import Path
import json

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "Chuong_3_Hoan_thien_phan_tich_sau.docx"
ASSET = ROOT / "chapter3_assets"
ASSET.mkdir(exist_ok=True)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table, color="D9D9D9", size="6"):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = borders.find(qn(f"w:{edge}"))
        if tag is None:
            tag = OxmlElement(f"w:{edge}")
            borders.append(tag)
        tag.set(qn("w:val"), "single")
        tag.set(qn("w:sz"), size)
        tag.set(qn("w:color"), color)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_keep_with_next(paragraph, value=True):
    p_pr = paragraph._p.get_or_add_pPr()
    keep = p_pr.find(qn("w:keepNext"))
    if value and keep is None:
        p_pr.append(OxmlElement("w:keepNext"))
    elif not value and keep is not None:
        p_pr.remove(keep)


def set_cant_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant = OxmlElement("w:cantSplit")
    tr_pr.append(cant)


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, text, end])


def add_para(doc, text="", bold_lead=None, align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=5):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.25
    if bold_lead and text.startswith(bold_lead):
        p.add_run(bold_lead).bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p


def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    p.add_run(text)
    return p


def add_heading(doc, text, level):
    p = doc.add_heading(text, level=level)
    set_keep_with_next(p)
    return p


def add_caption(doc, text):
    p = doc.add_paragraph(style="Caption")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(5)
    p.add_run(text)
    set_keep_with_next(p)
    return p


def add_source(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(f"Nguồn: {text}")
    r.italic = True
    r.font.size = Pt(9)
    return p


def add_table(doc, headers, rows, widths=None, numeric_cols=None, font_size=9.2):
    numeric_cols = set(numeric_cols or [])
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for j, (cell, header) in enumerate(zip(hdr.cells, headers)):
        set_cell_shading(cell, "1F4E78")
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(str(header))
        r.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(font_size)
    for i, row in enumerate(rows):
        tr = table.add_row()
        set_cant_split(tr)
        for j, (cell, val) in enumerate(zip(tr.cells, row)):
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if i % 2 == 1:
                set_cell_shading(cell, "EAF2F8")
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if j in numeric_cols else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            r = p.add_run(str(val))
            r.font.size = Pt(font_size)
    if widths:
        for row in table.rows:
            for cell, width in zip(row.cells, widths):
                cell.width = Cm(width)
    return table


FONT_REG = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REG), size)


def centered_text(draw, xy, text, fnt, fill="#17365D", spacing=6):
    x, y = xy
    box = draw.multiline_textbbox((0, 0), text, font=fnt, align="center", spacing=spacing)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.multiline_text((x - w / 2, y - h / 2), text, font=fnt, fill=fill, align="center", spacing=spacing)


def arrow(draw, start, end, fill="#4F81BD", width=5):
    draw.line([start, end], fill=fill, width=width)
    ex, ey = end
    draw.polygon([(ex, ey), (ex - 15, ey - 9), (ex - 15, ey + 9)], fill=fill)


def draw_bar_chart(labels, values, path, horizontal=False, colors=None, x_label=""):
    W, H = 1600, 850
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    colors = colors or ["#5B9BD5"] * len(values)
    left, top, right, bottom = 180, 70, 1520, 700
    d.line((left, top, left, bottom), fill="#666666", width=3)
    d.line((left, bottom, right, bottom), fill="#666666", width=3)
    maxv = max(values) * 1.18
    if horizontal:
        gap = (bottom - top) / len(values)
        for i, (lab, val, color) in enumerate(zip(labels, values, colors)):
            y0 = top + i * gap + gap * .18
            y1 = top + (i + 1) * gap - gap * .18
            x1 = left + (right - left) * val / maxv
            d.rectangle((left, y0, x1, y1), fill=color)
            d.text((left - 25, (y0 + y1) / 2), str(lab), font=font(26, True), fill="#222222", anchor="rm")
            d.text((x1 + 12, (y0 + y1) / 2), f"{val:.2f}", font=font(24, True), fill="#222222", anchor="lm")
    else:
        gap = (right - left) / len(values)
        for i, (lab, val, color) in enumerate(zip(labels, values, colors)):
            x0 = left + i * gap + gap * .18
            x1 = left + (i + 1) * gap - gap * .18
            y0 = bottom - (bottom - top) * val / maxv
            d.rectangle((x0, y0, x1, bottom), fill=color)
            d.text(((x0 + x1) / 2, bottom + 24), str(lab), font=font(24), fill="#222222", anchor="ma")
            d.text(((x0 + x1) / 2, y0 - 12), f"{val:.2f}", font=font(24, True), fill="#222222", anchor="ms")
    d.text(((left + right) / 2, H - 45), x_label, font=font(25), fill="#333333", anchor="mm")
    img.save(path, dpi=(220, 220))


def draw_line_chart(labels, values, path, x_label="", y_label=""):
    W, H = 1700, 850
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    left, top, right, bottom = 170, 75, 1580, 700
    d.line((left, top, left, bottom), fill="#666666", width=3)
    d.line((left, bottom, right, bottom), fill="#666666", width=3)
    vmin, vmax = min(values), max(values)
    pad = max((vmax - vmin) * .18, .5)
    lo, hi = vmin - pad, vmax + pad
    points = []
    for i, val in enumerate(values):
        x = left + (right - left) * i / max(len(values) - 1, 1)
        y = bottom - (bottom - top) * (val - lo) / (hi - lo)
        points.append((x, y))
    d.line(points, fill="#1F4E78", width=6, joint="curve")
    for i, ((x, y), lab, val) in enumerate(zip(points, labels, values)):
        d.ellipse((x - 7, y - 7, x + 7, y + 7), fill="#5B9BD5", outline="#1F4E78", width=2)
        if i % 2 == 0:
            d.text((x, bottom + 22), str(lab), font=font(22), fill="#222222", anchor="ma")
        if i in {0, 6, 9, 12, 16, 19, 23}:
            d.text((x, y - 15), f"{val:.2f}", font=font(21, True), fill="#222222", anchor="ms")
    d.text(((left + right) / 2, H - 45), x_label, font=font(25), fill="#333333", anchor="mm")
    d.text((45, (top + bottom) / 2), y_label, font=font(25), fill="#333333", anchor="mm")
    img.save(path, dpi=(220, 220))


model = pd.read_csv(ROOT / "data/model_comparison_v3.csv")
bands = pd.read_csv(ROOT / "data/error_by_taxi_band_v3.csv")
airports = pd.read_csv(ROOT / "data/error_by_airport_v3.csv")
summary = pd.read_csv(ROOT / "data/airport_summary_2008.csv")
meta = json.loads((ROOT / "taxiout_deployment_v3/metadata.json").read_text(encoding="utf-8"))

bands["share_pct"] = bands["rows"] / bands["rows"].sum() * 100
weighted_mae = float((bands["rows"] * bands["MAE"]).sum() / bands["rows"].sum())
airport_join = summary.merge(airports, on="Origin")
corr_avg_mae = float(airport_join["avg_taxi_out"].corr(airport_join["MAE"]))
corr_p95_mae = float(airport_join["avg_p95_taxi_out"].corr(airport_join["MAE"]))

# Extended empirical analysis from exported training/test aggregates.
bands["absolute_error_sum"] = bands["rows"] * bands["MAE"]
bands["error_contribution_pct"] = bands["absolute_error_sum"] / bands["absolute_error_sum"].sum() * 100
weighted_bias = float((bands["rows"] * bands["bias"]).sum() / bands["rows"].sum())
mae_without_over60 = float(bands.loc[bands["actual_band"] != ">60", "absolute_error_sum"].sum() /
                           bands.loc[bands["actual_band"] != ">60", "rows"].sum())
normal_mask = bands["actual_band"].isin(["<=10", "11-20", "21-30"])
mae_upto30 = float(bands.loc[normal_mask, "absolute_error_sum"].sum() / bands.loc[normal_mask, "rows"].sum())
tail_share = float(bands.loc[bands["actual_band"].isin(["31-60", ">60"]), "rows"].sum() / bands["rows"].sum() * 100)
tail_error_share = float(bands.loc[bands["actual_band"].isin(["31-60", ">60"]), "absolute_error_sum"].sum() /
                         bands["absolute_error_sum"].sum() * 100)

origin_hour = pd.read_csv(ROOT / "taxiout_deployment_v3/origin_hour_hist.csv")
routes = pd.read_csv(ROOT / "taxiout_deployment_v3/route_hist.csv")
density = pd.read_csv(ROOT / "taxiout_deployment_v3/origin_density_hist.csv")
origin_hour["raw_avg_taxi"] = (
    (origin_hour["origin_hour_hist_n"] + 100) * origin_hour["origin_hour_hist_taxi"]
    - 100 * meta["global_train_mean"]
) / origin_hour["origin_hour_hist_n"]
hour_rows = []
for dep_hour, group in origin_hour.groupby("dep_hour"):
    flights = int(group["origin_hour_hist_n"].sum())
    avg = float((group["origin_hour_hist_n"] * group["raw_avg_taxi"]).sum() / flights)
    hour_rows.append((int(dep_hour), flights, avg))
hourly = pd.DataFrame(hour_rows, columns=["dep_hour", "flights", "avg_taxi_out"]).sort_values("dep_hour")
top_origin_hours = origin_hour.loc[origin_hour["origin_hour_hist_n"] >= 500].nlargest(10, "raw_avg_taxi")
top_routes = routes.loc[routes["route_hist_n"] >= 500].nlargest(10, "route_hist_taxi")
top_density = density.nlargest(10, "origin_avg_density")

# Figure 1: architecture
img = Image.new("RGB", (1900, 850), "white")
d = ImageDraw.Draw(img)
main = [
    (40, "Dữ liệu chuyến bay\nHoa Kỳ 2008"),
    (410, "Spark\nLàm sạch và ETL"),
    (780, "Tạo 18 đặc trưng\nvà chia theo thời gian"),
    (1150, "H2O AutoML\nGLM tốt nhất"),
    (1520, "Mô hình binary\nBảng tra lịch sử"),
]
for x, label in main:
    d.rounded_rectangle((x, 150, x + 290, 360), radius=18, fill="#EAF2F8", outline="#1F4E78", width=4)
    centered_text(d, (x + 145, 255), label, font(30, True))
for i in range(len(main)-1):
    arrow(d, (main[i][0] + 290, 255), (main[i+1][0] - 15, 255))
d.rounded_rectangle((600, 545, 1050, 735), radius=18, fill="#F2F2F2", outline="#666666", width=4)
centered_text(d, (825, 640), "HDFS một nút\nCSV → Spark → Parquet", font(30, True), fill="#333333")
d.rounded_rectangle((1300, 545, 1770, 735), radius=18, fill="#E2F0D9", outline="#548235", width=4)
centered_text(d, (1535, 640), "Streamlit Dashboard\nBiểu đồ và dự đoán", font(30, True), fill="#375623")
d.line((825, 545, 825, 390), fill="#777777", width=5)
d.polygon([(825, 380), (813, 402), (837, 402)], fill="#777777")
d.line((1535, 545, 1665, 390), fill="#548235", width=5)
d.polygon([(1672, 380), (1650, 390), (1670, 405)], fill="#548235")
arch_path = ASSET / "architecture.png"
img.save(arch_path, dpi=(220, 220))

# Figure 2: model comparison
labels = ["Global mean", "Origin-hour", "H2O AutoML GLM"]
colors = ["#A6A6A6", "#5B9BD5", "#1F4E78"]
model_path = ASSET / "model_mae.png"
draw_bar_chart(labels, model["MAE"].tolist(), model_path, colors=colors, x_label="MAE trên tập kiểm tra (phút)")

# Figure 3: band error
band_path = ASSET / "error_bands.png"
draw_bar_chart(bands["actual_band"].tolist(), bands["MAE"].tolist(), band_path,
               colors=["#70AD47", "#70AD47", "#FFC000", "#ED7D31", "#C00000"],
               x_label="Nhóm TaxiOut thực tế (phút)")

# Figure 4: airport error
top10 = airports.head(10).sort_values("MAE")
airport_path = ASSET / "airport_mae.png"
draw_bar_chart(top10["Origin"].tolist(), top10["MAE"].tolist(), airport_path,
               horizontal=True, colors=["#5B9BD5"] * len(top10), x_label="MAE (phút)")

# Figure 5: recovered training hourly profile
hourly_path = ASSET / "hourly_taxi_profile.png"
draw_line_chart(hourly["dep_hour"].tolist(), hourly["avg_taxi_out"].tolist(), hourly_path,
                x_label="Giờ khởi hành theo lịch", y_label="TaxiOut trung bình (phút)")

# Figure 6: contribution of each actual TaxiOut band to total absolute error
contribution_path = ASSET / "error_contribution.png"
draw_bar_chart(bands["actual_band"].tolist(), bands["error_contribution_pct"].tolist(),
               contribution_path,
               colors=["#70AD47", "#5B9BD5", "#FFC000", "#ED7D31", "#C00000"],
               x_label="Tỷ trọng trong tổng sai số tuyệt đối (%)")


doc = Document()
sec = doc.sections[0]
sec.page_width = Cm(21.0)
sec.page_height = Cm(29.7)
sec.top_margin = Cm(2.2)
sec.bottom_margin = Cm(2.0)
sec.left_margin = Cm(2.8)
sec.right_margin = Cm(2.2)
sec.header_distance = Cm(1.0)
sec.footer_distance = Cm(1.0)

styles = doc.styles
normal = styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(11.5)
normal._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
normal.paragraph_format.space_after = Pt(5)
normal.paragraph_format.line_spacing = 1.25
for style_name, size, bold in (("Title", 19, True), ("Heading 1", 15, True), ("Heading 2", 13, True), ("Heading 3", 11.5, True)):
    st = styles[style_name]
    st.font.name = "Times New Roman"
    st.font.size = Pt(size)
    st.font.bold = bold
    st.font.color.rgb = RGBColor(0, 0, 0)
    st._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    st._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    st._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
styles["Heading 1"].paragraph_format.space_before = Pt(12)
styles["Heading 1"].paragraph_format.space_after = Pt(7)
styles["Heading 2"].paragraph_format.space_before = Pt(10)
styles["Heading 2"].paragraph_format.space_after = Pt(5)
styles["Heading 3"].paragraph_format.space_before = Pt(7)
styles["Heading 3"].paragraph_format.space_after = Pt(3)
styles["Caption"].font.name = "Times New Roman"
styles["Caption"].font.size = Pt(10)
styles["Caption"].font.italic = True
styles["Caption"].font.color.rgb = RGBColor(0, 0, 0)
for name in ("List Bullet", "List Bullet 2"):
    styles[name].font.name = "Times New Roman"
    styles[name].font.size = Pt(11.5)

# Remove built-in title borders and force the same header on odd/even pages.
title_ppr = styles["Title"]._element.get_or_add_pPr()
title_border = title_ppr.find(qn("w:pBdr"))
if title_border is not None:
    title_ppr.remove(title_border)
settings = doc.settings._element
odd_even = settings.find(qn("w:evenAndOddHeaders"))
if odd_even is not None:
    settings.remove(odd_even)

add_page_number(sec.footer.paragraphs[0])

title = doc.add_paragraph(style="Title")
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title.paragraph_format.space_before = Pt(36)
title.paragraph_format.space_after = Pt(18)
title.add_run("CHƯƠNG 3")
direct_border = title._p.get_or_add_pPr().find(qn("w:pBdr"))
if direct_border is not None:
    title._p.get_or_add_pPr().remove(direct_border)
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub.paragraph_format.space_after = Pt(24)
r = sub.add_run("XÂY DỰNG ỨNG DỤNG VÀ TRỰC QUAN HÓA DỮ LIỆU TAXIOUT")
r.bold = True
r.font.size = Pt(16)

add_para(doc, "Chương này trình bày toàn bộ quá trình xây dựng và đánh giá hệ thống phân tích thời gian TaxiOut, từ dữ liệu chuyến bay Hoa Kỳ năm 2008 đến pipeline Spark, H2O AutoML, HDFS và dashboard Streamlit. Trọng tâm của chương không chỉ là tạo một giá trị dự báo, mà còn xác định quy luật tắc nghẽn, vị trí mô hình hoạt động tốt hoặc yếu và mức độ tin cậy của kết quả. Các số liệu đánh giá được lấy trực tiếp từ tệp xuất của dự án; các kết quả suy diễn bổ sung đều được tính lại từ bảng tổng hợp để bảo đảm khả năng kiểm chứng.")
add_para(doc, "Kết quả chính cho thấy mô hình H2O AutoML dạng GLM đạt MAE 5,8445 phút, RMSE 10,0755 phút và R² 0,2034 trên 180.000 chuyến kiểm tra thuộc tháng 11-12/2008. Mô hình giảm MAE 18,82% so với baseline trung bình toàn cục, nhưng sai số tăng mạnh đối với TaxiOut trên 30 phút. Vì vậy, hệ thống phù hợp cho phân tích, minh họa pipeline Big Data và hỗ trợ nhận diện tắc nghẽn; chưa đủ cơ sở để dùng độc lập cho quyết định vận hành thời gian thực.")

add_heading(doc, "3.1 Phân tích yêu cầu", 1)
add_heading(doc, "3.1.1 Bài toán và người sử dụng", 2)
add_para(doc, "TaxiOut là số phút từ thời điểm máy bay rời cổng đến thời điểm cất cánh. Giá trị này phản ánh một phần mức độ ùn tắc bề mặt sân bay, khả năng điều phối đường lăn và tình trạng xếp hàng trước đường băng. Bài toán của dự án là dùng thông tin lịch, hãng, sân bay, tuyến bay, khoảng cách và mật độ khởi hành để ước lượng TaxiOut cho từng chuyến.")
add_para(doc, "Nhóm người sử dụng chính gồm sinh viên và giảng viên đánh giá quy trình Big Data, người phân tích vận hành cần so sánh sân bay hoặc khung giờ, và người dùng thử nghiệm muốn nhập thông tin chuyến bay để nhận một giá trị dự báo. Hệ thống không được mô tả như công cụ điều hành bay chính thức vì dữ liệu huấn luyện đã cũ và chưa có thời tiết, cấu hình đường băng, loại tàu bay, hàng đợi lăn hoặc trạng thái ATC.")

add_heading(doc, "3.1.2 Yêu cầu chức năng", 2)
func_rows = [
    ("F1", "Đọc và làm sạch dữ liệu", "Lọc năm 2008, loại chuyến hủy/chuyển hướng, kiểm tra thời gian và TaxiOut."),
    ("F2", "Tạo đặc trưng", "Tạo đặc trưng lịch, giờ, khung 30 phút, mật độ và thống kê lịch sử."),
    ("F3", "Huấn luyện và đánh giá", "So sánh Global Mean, Origin-Hour và H2O AutoML trên tập kiểm tra theo thời gian."),
    ("F4", "Dự đoán cục bộ", "Nạp đúng mô hình H2O binary và tái tạo 18 đặc trưng theo metadata."),
    ("F5", "Trực quan hóa", "Hiển thị so sánh mô hình, ùn tắc sân bay, dự đoán, sai số và luồng ngoài."),
    ("F6", "Kiểm chứng HDFS", "Đọc CSV từ HDFS, xử lý bằng Spark và ghi Parquet trở lại HDFS."),
    ("F7", "Tích hợp nguồn ngoài", "Chuẩn hóa snapshot Aviationstack hoặc CSV hợp lệ thành schema dự đoán."),
]
add_caption(doc, "Bảng 3.1 Yêu cầu chức năng của hệ thống")
add_table(doc, ["Mã", "Chức năng", "Đầu ra cần đạt"], func_rows, widths=[1.5, 4.5, 10], numeric_cols={0}, font_size=9.3)
add_source(doc, "Tổng hợp từ app.py, hdfs_spark_job.py, h2o_predictor.py và live_feed.py.")

add_heading(doc, "3.1.3 Yêu cầu phi chức năng và tiêu chí tin cậy", 2)
add_bullet(doc, "Khả năng tái lập: model_id, phiên bản H2O, thứ tự đặc trưng và các bảng tra phải được lưu trong gói triển khai.")
add_bullet(doc, "An toàn dữ liệu: API key chỉ đọc từ biến môi trường hoặc ô nhập mật khẩu, không ghi cứng trong mã nguồn.")
add_bullet(doc, "Khả năng kiểm chứng: mọi chỉ số trong báo cáo phải đối chiếu được với CSV xuất từ pipeline; không nội suy khi tệp nguồn không tồn tại.")
add_bullet(doc, "Tính minh bạch: dashboard phải nêu rõ nguồn mô hình H2O; dữ liệu trực tiếp và dữ liệu lịch sử phải được phân biệt.")
add_bullet(doc, "Khả năng mở rộng: Spark job chấp nhận URI local, Kaggle hoặc hdfs://; đầu ra Parquet phù hợp cho xử lý phân tán.")
add_bullet(doc, "Kiểm soát phạm vi: đầu vào chưa xuất hiện trong dữ liệu huấn luyện hoặc có mật độ tương đối quá cao phải được cảnh báo thay vì trình bày dự báo như một kết quả chắc chắn.")

add_heading(doc, "3.2 Kiến trúc tổng thể", 1)
add_para(doc, "Kiến trúc được tổ chức thành hai nhánh. Nhánh học máy xử lý dữ liệu lịch sử bằng Spark, tạo đặc trưng, huấn luyện H2O AutoML rồi xuất mô hình và các bảng tra để dashboard dự đoán. Nhánh hạ tầng đưa CSV vào HDFS, dùng Spark ETL và ghi các bảng Parquet trở lại HDFS. Dashboard là lớp trình bày và thử nghiệm, không trực tiếp huấn luyện lại mô hình.")
add_caption(doc, "Hình 3.1 Kiến trúc tổng thể của dự án")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(str(arch_path), width=Cm(16.0))
add_source(doc, "Mô hình hóa từ cấu trúc mã nguồn và các tệp triển khai của dự án.")
arch_rows = [
    ("Lưu trữ", "CSV gốc, HDFS, Parquet", "Lưu dữ liệu đầu vào và các bảng sau ETL."),
    ("Xử lý", "Apache Spark", "Lọc, chuẩn hóa thời gian, tổng hợp mật độ và ùn tắc."),
    ("Học máy", "H2O AutoML", "Huấn luyện, lựa chọn mô hình GLM và xuất binary model."),
    ("Phục vụ", "Python, H2O runtime", "Tái tạo đặc trưng và suy luận cho một hoặc nhiều chuyến."),
    ("Trình bày", "Streamlit, Plotly", "Biểu đồ tương tác, bảng dữ liệu và giao diện dự đoán."),
    ("Nguồn ngoài", "Aviationstack hoặc CSV", "Cung cấp snapshot chuyến bay theo schema kiểm soát."),
]
add_caption(doc, "Bảng 3.2 Vai trò của các lớp trong kiến trúc")
add_table(doc, ["Lớp", "Công nghệ", "Vai trò"], arch_rows, widths=[2.7, 4.1, 9.2], font_size=9.3)
add_source(doc, "Tổng hợp từ mã nguồn dự án.")

add_heading(doc, "3.3 Mô tả dữ liệu", 1)
add_heading(doc, "3.3.1 Nguồn và phạm vi dữ liệu", 2)
add_para(doc, "Pipeline đã xử lý 6.853.707 chuyến bay nội địa Hoa Kỳ năm 2008. Biến mục tiêu là TaxiOut. Dữ liệu mô hình được chia theo trật tự thời gian: tháng 1-9 dùng huấn luyện, tháng 10 dùng validation, tháng 11-12 dùng kiểm tra. Phiên bản cải thiện sử dụng 450.000 dòng train, 140.000 dòng validation và 180.000 dòng test. Cách chia này đáng tin cậy hơn chia ngẫu nhiên đối với bài toán vận hành theo thời gian vì mô phỏng việc dùng dữ liệu quá khứ để dự đoán giai đoạn tương lai.")
split_rows = [
    ("Toàn bộ năm 2008", "6.853.707", "Dữ liệu được Spark xử lý trong notebook"),
    ("Train", "450.000", "Tháng 1-9/2008; huấn luyện mô hình và tạo thống kê lịch sử"),
    ("Validation", "140.000", "Tháng 10/2008; lựa chọn mô hình"),
    ("Test", "180.000", "Tháng 11-12/2008; báo cáo chỉ số cuối cùng"),
]
add_caption(doc, "Bảng 3.3 Quy mô dữ liệu và cách chia tập")
add_table(doc, ["Phạm vi", "Số bản ghi", "Mục đích"], split_rows, widths=[3.5, 3.2, 9.3], numeric_cols={1}, font_size=9.3)
add_source(doc, "README.md, MODEL_EVALUATION.md và error_by_taxi_band_v3.csv.")

add_heading(doc, "3.3.2 Thuộc tính cốt lõi", 2)
data_rows = [
    ("Year, Month, DayofMonth, DayOfWeek", "Thời gian", "Tạo đặc trưng lịch và chia dữ liệu theo thời gian"),
    ("CRSDepTime", "Lịch bay", "Tách giờ, phút và khung 30 phút"),
    ("UniqueCarrier", "Danh mục", "Mã hãng hàng không"),
    ("Origin, Dest", "Danh mục", "Sân bay đi, đến và khóa tuyến bay"),
    ("Distance", "Số", "Khoảng cách tuyến bay theo mile"),
    ("TaxiOut", "Số", "Biến mục tiêu tính bằng phút"),
    ("Cancelled, Diverted", "Cờ", "Loại chuyến hủy hoặc chuyển hướng"),
]
add_caption(doc, "Bảng 3.4 Các thuộc tính đầu vào quan trọng")
add_table(doc, ["Thuộc tính", "Kiểu vai trò", "Cách sử dụng"], data_rows, widths=[5, 3, 8], font_size=9.1)
add_source(doc, "Danh sách REQUIRED_COLUMNS trong hdfs_spark_job.py.")
add_para(doc, "Bảng airport_summary_2008.csv lưu thống kê 20 sân bay được trình bày trên dashboard. Tổng số chuyến của riêng 20 sân bay này là 3.492.791, không phải tổng số chuyến của toàn bộ tập dữ liệu. Việc phân biệt hai phạm vi tránh diễn giải sai rằng bảng top 20 đại diện cho mọi sân bay.")

add_heading(doc, "3.4 Tiền xử lý dữ liệu bằng Spark", 1)
add_heading(doc, "3.4.1 Quy tắc làm sạch", 2)
add_para(doc, "Spark đọc CSV với header và suy luận kiểu dữ liệu, sau đó kiểm tra sự tồn tại của toàn bộ cột bắt buộc trước khi xử lý. Các bản ghi được giữ lại khi Year bằng 2008, Cancelled bằng 0, Diverted bằng 0 và TaxiOut nằm trong khoảng 1-180 phút. CRSDepTime được tách thành dep_hour và dep_minute; ngày bay, giờ, phút, mã hãng, sân bay đi, sân bay đến và khoảng cách đều phải hợp lệ. Quy tắc này loại bỏ chuyến không hoàn thành và các giá trị không phù hợp trước khi tạo đặc trưng.")
clean_rows = [
    ("Năm phân tích", "Year = 2008", "Giữ phạm vi thống nhất của đề tài"),
    ("Trạng thái chuyến", "Cancelled = 0 và Diverted = 0", "Loại chuyến không có quy trình lăn chuẩn"),
    ("TaxiOut", "1 ≤ TaxiOut ≤ 180", "Loại giá trị không hợp lệ hoặc cực đoan ngoài phạm vi thiết kế"),
    ("Phút khởi hành", "0 ≤ dep_minute ≤ 59", "Loại mã thời gian lịch không hợp lệ"),
    ("Trường bắt buộc", "Ngày bay, hãng, Origin, Dest không rỗng; Distance > 0", "Bảo đảm đủ dữ liệu để tạo đặc trưng"),
]
add_caption(doc, "Bảng 3.5 Quy tắc lọc trong Spark ETL")
add_table(doc, ["Nội dung", "Điều kiện", "Ý nghĩa"], clean_rows, widths=[3.2, 5.4, 7.4], font_size=9.2)
add_source(doc, "hdfs_spark_job.py.")

add_heading(doc, "3.4.2 Tạo bảng mật độ và ùn tắc", 2)
add_para(doc, "Mỗi chuyến được gán half_hour_bin theo số phút tính từ đầu ngày, làm tròn xuống bội số 30. Mật độ khởi hành được tính bằng số chuyến có cùng ngày, sân bay đi và khung 30 phút. Sau đó bảng mật độ được nối trở lại từng chuyến để tạo departure_density_30m. Một bảng tổng hợp khác lưu số chuyến, TaxiOut trung bình, trung vị và phân vị 95 theo cùng khóa thời gian - sân bay. Hai đầu ra này phục vụ lần lượt cho học máy và phân tích ùn tắc.")
add_para(doc, "Đầu ra được ghi ở định dạng Parquet. So với CSV, Parquet giữ schema, hỗ trợ đọc theo cột và phù hợp hơn cho truy vấn phân tán. Job mặc định dùng chế độ errorifexists để tránh ghi đè ngoài ý muốn; chỉ dùng overwrite khi người chạy truyền cờ tương ứng.")
add_para(doc, "Sau ETL, job ghi thêm báo cáo chất lượng dữ liệu dạng JSON, gồm số dòng đầu vào, số dòng đúng năm, số chuyến hoàn thành, số dòng có TaxiOut hợp lệ, số dòng sạch và số lượng bị loại ở từng nguyên nhân. Báo cáo còn lưu phiên bản Spark, số shuffle partition, URI đầu vào và thời gian chạy. Cơ chế này giúp giải thích chênh lệch số lượng bản ghi thay vì chỉ công bố số dòng cuối cùng.")

add_heading(doc, "3.5 Xây dựng đặc trưng", 1)
add_heading(doc, "3.5.1 Danh sách đặc trưng triển khai", 2)
feature_rows = [
    ("Lịch", "Month, DayofMonth, DayOfWeek", "Mùa vụ và nhịp theo ngày"),
    ("Thời điểm", "dep_hour, half_hour_bin", "Khung vận hành trong ngày"),
    ("Cờ thời gian", "is_weekend, is_peak_hour", "Cuối tuần và giờ cao điểm 7-9, 16-19"),
    ("Danh mục", "UniqueCarrier, Origin, Dest", "Hãng, sân bay đi và sân bay đến"),
    ("Tuyến", "Distance", "Khoảng cách theo mile"),
    ("Mật độ", "departure_density_30m, relative_density", "Mức tải tuyệt đối và tương đối của sân bay"),
    ("Lịch sử", "origin_hour_hist_taxi, route_hist_taxi, carrier_origin_hist_taxi", "Mức TaxiOut đặc trưng theo ba nhóm"),
    ("Độ hỗ trợ", "origin_hour_hist_n, route_hist_n", "Số quan sát đứng sau thống kê lịch sử"),
]
add_caption(doc, "Bảng 3.6 Mười tám đặc trưng của mô hình triển khai")
add_table(doc, ["Nhóm", "Đặc trưng", "Ý nghĩa"], feature_rows, widths=[2.7, 7.1, 6.2], font_size=8.9)
add_source(doc, "feature_columns trong taxiout_deployment_v3/metadata.json.")

add_heading(doc, "3.5.2 Cách tính đặc trưng lịch sử và giá trị dự phòng", 2)
add_para(doc, "Ba bảng tra lịch sử gồm trung bình TaxiOut theo sân bay-giờ, theo tuyến Origin-Dest và theo cặp hãng-sân bay đi. Khi khóa tra cứu không tồn tại, hệ thống dùng global_train_mean = 16,4766 phút. Mật độ tương đối được tính bằng mật độ khởi hành của chuyến chia cho mật độ trung bình của sân bay; mẫu số được chặn tối thiểu bằng 1 để tránh chia cho 0.")
add_para(doc, "Thống kê sân bay-giờ trong gói triển khai đã được làm trơn với hệ số 100 quan sát hướng về trung bình toàn cục. Làm trơn giảm dao động ở nhóm có ít chuyến, còn origin_hour_hist_n và route_hist_n cho mô hình biết mức độ hỗ trợ của thống kê. Gói triển khai hiện chứa 3.790 tổ hợp sân bay-giờ, 5.137 tuyến, 1.752 cặp hãng-sân bay và 301 sân bay có mật độ tham chiếu.")

add_heading(doc, "3.5.3 Kiểm soát rò rỉ dữ liệu", 2)
add_para(doc, "Rò rỉ dữ liệu xảy ra nếu TaxiOut của giai đoạn validation hoặc test được dùng để tạo trung bình lịch sử đầu vào. Thiết kế của dự án hạn chế rủi ro này bằng cách chia theo thời gian và dùng thống kê huấn luyện để phục vụ suy luận. Báo cáo không khẳng định loại bỏ tuyệt đối mọi dạng rò rỉ nếu không chạy lại toàn bộ notebook, nhưng gói triển khai và tài liệu đánh giá đều nhất quán với nguyên tắc chỉ dùng quá khứ để dự đoán tương lai.")
add_para(doc, "Một điểm cần tiếp tục kiểm soát là target encoding bên trong tập huấn luyện. Nếu TaxiOut của một dòng tham gia trực tiếp vào trung bình lịch sử dùng cho chính dòng đó, kết quả train có thể lạc quan hơn thực tế. Phiên bản chặt chẽ hơn nên tạo encoding theo out-of-fold hoặc expanding window, trong đó mỗi quan sát chỉ nhận thống kê từ các chuyến xảy ra trước nó.")

add_heading(doc, "3.6 Xây dựng và huấn luyện mô hình", 1)
add_heading(doc, "3.6.1 Các mô hình so sánh", 2)
model_desc = [
    ("Global mean", "Dự đoán mọi chuyến bằng trung bình TaxiOut của train", "Mốc tối thiểu để đo lợi ích của mô hình"),
    ("Origin-hour historical mean", "Tra trung bình lịch sử theo sân bay và giờ", "Baseline có thông tin bối cảnh nhưng chưa học tương tác phức tạp"),
    ("H2O AutoML enhanced", "AutoML trên 18 đặc trưng; GLM được chọn", "Mô hình cuối cùng để xuất và phục vụ dự đoán"),
]
add_caption(doc, "Bảng 3.7 Vai trò của các mô hình so sánh")
add_table(doc, ["Mô hình", "Cơ chế", "Vai trò"], model_desc, widths=[4, 6.2, 5.8], font_size=9.2)
add_source(doc, "model_comparison_v3.csv và MODEL_EVALUATION.md.")

add_heading(doc, "3.6.2 Mô hình GLM và gói triển khai", 2)
add_para(doc, "H2O AutoML chọn GLM làm mô hình tốt nhất cho cấu hình đã chạy. GLM tạo dự báo từ tổ hợp tuyến tính của các biến số và các mức biến phân loại sau mã hóa. Với dữ liệu gồm nhiều biến danh mục như hãng và sân bay, ưu điểm của GLM là suy luận nhanh, ổn định và dễ đóng gói hơn các mô hình ensemble lớn. Tuy nhiên, quan hệ giữa tắc nghẽn và TaxiOut có thể phi tuyến, vì vậy GLM không bảo đảm mô tả tốt các đuôi phân phối hiếm.")
deploy_rows = [
    ("Model ID", meta["model_id"]),
    ("Phiên bản H2O", meta["h2o_version"]),
    ("Số đặc trưng", str(len(meta["feature_columns"]))),
    ("Số biến phân loại", str(len(meta["categorical_columns"]))),
    ("Trung bình train", f"{meta['global_train_mean']:.4f} phút"),
    ("Dự báo tham chiếu", f"{meta['reference_prediction']['route']} lúc {meta['reference_prediction']['time']} ≈ {meta['reference_prediction']['expected_minutes']:.1f} phút"),
]
add_caption(doc, "Bảng 3.8 Thông tin gói mô hình triển khai")
add_table(doc, ["Thuộc tính", "Giá trị"], deploy_rows, widths=[5, 11], font_size=9.4)
add_source(doc, "taxiout_deployment_v3/metadata.json.")

add_heading(doc, "3.7 Kết quả đánh giá", 1)
add_heading(doc, "3.7.1 So sánh chỉ số tổng thể", 2)
rows = []
for _, r in model.iterrows():
    rows.append((r["model"], f"{r['MAE']:.4f}", f"{r['RMSE']:.4f}", f"{r['R2']:.4f}", f"{r['MAE_improvement_vs_global_pct']:.2f}%"))
add_caption(doc, "Bảng 3.9 Kết quả trên tập kiểm tra tháng 11-12/2008")
add_table(doc, ["Mô hình", "MAE", "RMSE", "R²", "Giảm MAE"], rows, widths=[5.2, 2.3, 2.3, 2.1, 2.8], numeric_cols={1,2,3,4}, font_size=9.2)
add_source(doc, "data/model_comparison_v3.csv.")
add_caption(doc, "Hình 3.2 So sánh MAE của ba mô hình")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(str(model_path), width=Cm(14.8))
add_source(doc, "Dựng lại từ data/model_comparison_v3.csv.")
add_para(doc, "H2O AutoML đạt MAE 5,8445 phút, thấp hơn 1,3550 phút so với Global Mean và thấp hơn 0,3770 phút so với Origin-Hour. Mức giảm tương đối so với Global Mean là 18,82%. RMSE 10,0755 phút lớn hơn MAE 4,2310 phút, cho thấy một bộ phận nhỏ quan sát có sai số rất lớn và bị RMSE phạt mạnh.")
add_para(doc, "R² = 0,2034 nghĩa là mô hình giải thích khoảng 20,34% biến thiên TaxiOut trên tập kiểm tra theo thời gian. Giá trị này dương và tốt hơn hai baseline, nhưng vẫn thấp đối với một hệ thống dự báo vận hành chính xác. Do đó, kết luận hợp lý là mô hình tạo giá trị phân tích ở mức vừa phải, không phải dự báo đủ tin cậy cho mọi tình huống.")

add_heading(doc, "3.7.2 Sai số theo nhóm TaxiOut", 2)
band_rows = []
for _, r in bands.iterrows():
    band_rows.append((r["actual_band"], f"{int(r['rows']):,}".replace(",", "."), f"{r['share_pct']:.2f}%", f"{r['MAE']:.2f}", f"{r['bias']:.2f}"))
add_caption(doc, "Bảng 3.10 Sai số theo độ dài TaxiOut thực tế")
add_table(doc, ["Nhóm", "Số chuyến", "Tỷ trọng", "MAE", "Bias"], band_rows, widths=[2.7, 3.1, 3, 3, 3], numeric_cols={1,2,3,4}, font_size=9.2)
add_source(doc, "data/error_by_taxi_band_v3.csv; tỷ trọng được tính trên 180.000 chuyến test.")
add_caption(doc, "Hình 3.3 MAE tăng mạnh ở các chuyến TaxiOut dài")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(str(band_path), width=Cm(15.2))
add_source(doc, "Dựng lại từ data/error_by_taxi_band_v3.csv.")
add_para(doc, f"Nhóm 11-20 phút chiếm 49,78% tập kiểm tra và có MAE thấp nhất, 3,78 phút. Hai nhóm không quá 20 phút chiếm tổng cộng 77,49% và được dự báo tương đối ổn định. Ngược lại, nhóm 31-60 phút có MAE 18,06 phút; nhóm trên 60 phút chỉ chiếm 1,06% nhưng MAE lên tới 58,83 phút. MAE trọng số tính lại từ năm nhóm là {weighted_mae:.6f} phút, khớp chỉ số tổng thể đến sáu chữ số thập phân.")
add_para(doc, "Trong bảng dự án, bias được hiểu là thực tế trừ dự đoán. Bias dương lớn ở các nhóm trên 30 phút cho thấy mô hình dự đoán thấp hơn thực tế khi xuất hiện tắc nghẽn nặng. Bias âm ở hai nhóm ngắn cho thấy xu hướng dự đoán cao hơn thực tế. Đây là dấu hiệu hồi quy về trung bình: mô hình hoạt động tốt quanh vùng phổ biến nhưng làm phẳng các trường hợp cực đoan.")

add_heading(doc, "3.7.3 Sai số theo sân bay", 2)
airport_rows = []
for _, r in airports.head(10).iterrows():
    airport_rows.append((r["Origin"], f"{int(r['rows']):,}".replace(",", "."), f"{r['MAE']:.2f}", f"{r['bias']:.2f}"))
add_caption(doc, "Bảng 3.11 Mười sân bay có MAE cao nhất trong bảng xuất")
add_table(doc, ["Sân bay", "Số chuyến test", "MAE", "Bias"], airport_rows, widths=[3.5, 4.5, 3.5, 3.5], numeric_cols={1,2,3}, font_size=9.3)
add_source(doc, "data/error_by_airport_v3.csv.")
add_caption(doc, "Hình 3.4 MAE tại mười sân bay khó dự báo nhất")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(str(airport_path), width=Cm(14.6))
add_source(doc, "Dựng lại từ data/error_by_airport_v3.csv.")
add_para(doc, "JFK, LGA và EWR có MAE lần lượt 13,50; 11,46 và 10,90 phút. Bias âm tại ba sân bay này cho thấy dự báo trung bình cao hơn thực tế trên mẫu test của từng sân bay, mặc dù mô hình vẫn dự báo thiếu ở nhóm TaxiOut rất dài. Hai nhận xét không mâu thuẫn vì một sân bay chứa nhiều dải TaxiOut khác nhau.")
add_para(doc, f"Phân tích mô tả bổ sung trên 20 sân bay xuất hiện đồng thời trong hai bảng cho thấy tương quan Pearson giữa TaxiOut trung bình và MAE là r = {corr_avg_mae:.3f}; giữa p95 TaxiOut và MAE là r = {corr_p95_mae:.3f}. Quan hệ mạnh này gợi ý rằng sân bay có quy trình lăn dài và đuôi phân phối lớn thường khó dự báo hơn. Đây là tương quan trên 20 điểm tổng hợp, không chứng minh quan hệ nhân quả và không thay thế phân tích ở mức từng chuyến.")

add_heading(doc, "3.7.4 Đánh giá độ tin cậy của kết quả", 2)
trust_rows = [
    ("Chia theo thời gian", "Có", "Hạn chế việc dùng tương lai để đánh giá quá khứ"),
    ("Cỡ mẫu test", "180.000 chuyến", "Đủ lớn để chỉ số tổng thể ổn định về mặt mô tả"),
    ("Đối chiếu chéo", "MAE nhóm = MAE tổng thể", "Tính lại đạt 5,844531 phút"),
    ("Kiểm thử mã nguồn", "4/4 đạt", "Bao phủ profile lịch sử, CSV và chuẩn hóa Aviationstack"),
    ("Khoảng tin cậy", "Chưa có", "Không thể bootstrap vì không lưu sai số từng chuyến trong repo"),
    ("Độ mới dữ liệu", "Năm 2008", "Có nguy cơ lệch phân phối khi áp dụng hiện nay"),
]
add_caption(doc, "Bảng 3.12 Căn cứ và giới hạn của độ tin cậy")
add_table(doc, ["Khía cạnh", "Kết quả", "Diễn giải"], trust_rows, widths=[4, 3.8, 8.2], font_size=9.2)
add_source(doc, "Kiểm chứng trực tiếp từ dữ liệu và bộ test trong dự án.")

add_heading(doc, "3.8 Xây dựng HDFS", 1)
add_para(doc, "Dự án triển khai HDFS ở chế độ pseudo-distributed một nút trên Ubuntu WSL. NameNode quản lý namespace và metadata; một DataNode lưu block dữ liệu. Cấu hình này chứng minh khả năng kết nối HDFS-Spark nhưng không đại diện cho khả năng chịu lỗi hoặc mở rộng ngang của cụm nhiều máy.")
hdfs_rows = [
    ("1", "Đưa fixtures/flights_smoke.csv lên HDFS", "Tạo nguồn dữ liệu kiểm thử có 6 dòng"),
    ("2", "Spark đọc hdfs://127.0.0.1:9000/...", "Xác nhận kết nối và schema"),
    ("3", "Lọc chuyến hợp lệ", "Còn 5 chuyến do một chuyến bị hủy"),
    ("4", "Tạo features và congestion", "Kiểm chứng logic ETL"),
    ("5", "Ghi hai bảng Parquet về HDFS", "Xác nhận chiều ghi của pipeline"),
]
add_caption(doc, "Bảng 3.13 Quy trình smoke test Spark-HDFS")
add_table(doc, ["Bước", "Thao tác", "Kết quả mong đợi"], hdfs_rows, widths=[1.5, 7.3, 7.2], numeric_cols={0}, font_size=9.2)
add_source(doc, "README.md, setup_hdfs_wsl.sh và run_hdfs_smoke_wsl.sh.")
add_para(doc, "Với cluster thật, hdfs_spark_job.py nhận URI đầu vào và đầu ra từ tham số dòng lệnh. Điều này tách logic ETL khỏi vị trí lưu trữ. Tuy nhiên, smoke test chỉ dùng mẫu tổng hợp rất nhỏ; không được dùng nó để khẳng định máy local đã xử lý toàn bộ 11,2 GB hay đạt hiệu năng của cụm sản xuất.")

add_heading(doc, "3.9 Xây dựng dashboard Streamlit", 1)
add_para(doc, "Dashboard được tổ chức thành năm tab, mỗi tab trả lời một câu hỏi phân tích riêng. app.py đọc các bảng CSV đã xuất; nếu thiếu bảng lỗi theo giờ, giao diện hiển thị thông báo và không nội suy từ nguồn khác. Khi thiếu hourly_congestion_top20.csv, biểu đồ theo giờ dùng profile huấn luyện tháng 1-9 được khôi phục từ bảng origin_hour_hist và ghi rõ phạm vi này.")
tabs = [
    ("1", "So sánh mô hình", "model_comparison_v3.csv", "MAE, RMSE, R² và mức cải thiện"),
    ("2", "Sân bay và khung giờ", "airport_summary_2008.csv; origin_hour_hist.csv", "Xếp hạng sân bay và profile theo giờ"),
    ("3", "Dự đoán thủ công", "Thông tin người dùng nhập", "TaxiOut dự báo và model ID"),
    ("4", "Phân tích sai số", "error_by_airport_v3.csv; error_by_taxi_band_v3.csv", "Điểm yếu theo sân bay và dải TaxiOut"),
    ("5", "Luồng chuyến bay ngoài", "Aviationstack hoặc live_flights.csv", "Dự báo tối đa 10 chuyến gần nhất"),
]
add_caption(doc, "Bảng 3.14 Thiết kế năm tab của dashboard")
add_table(doc, ["Tab", "Nội dung", "Nguồn dữ liệu", "Đầu ra"], tabs, widths=[1.3, 4.1, 6.2, 4.4], numeric_cols={0}, font_size=8.8)
add_source(doc, "app.py và dashboard_data.py.")
add_para(doc, "Ở tab dự đoán, H2OTaxiOutPredictor nạp mô hình binary, metadata và bốn bảng tra. Dòng nguồn phải hiển thị đúng model ID GLM_1_AutoML_2_20261002_33511. Nếu môi trường không nạp được mô hình H2O, kết quả từ công thức dự phòng không được coi là kết quả của mô hình chính thức.")
add_para(doc, "Trước khi suy luận, lớp dự đoán kiểm tra ngày lịch, giờ, khoảng cách, mật độ và tái sắp xếp đúng 18 đặc trưng theo metadata. Hệ thống cảnh báo khi hãng, sân bay hoặc tuyến chưa xuất hiện trong dữ liệu huấn luyện, khi phải dùng trung bình toàn cục thay cho bảng tra hoặc khi relative_density vượt ngưỡng 4 lần mức tham chiếu. Các cảnh báo không thay thế khoảng dự báo, nhưng ngăn người dùng hiểu sai một giá trị ngoài phạm vi học như kết quả có độ chắc chắn tương đương dữ liệu quen thuộc.")

add_heading(doc, "3.10 Tích hợp Aviationstack", 1)
add_para(doc, "Luồng bên ngoài được lấy theo yêu cầu của người dùng thay vì gọi định kỳ, giúp kiểm soát quota API. Payload được chuyển thành bảy trường: flight_id, scheduled_local, carrier, origin, dest, distance và departure_density_30m. Chuyến bị hủy, thiếu mã chuyến, thiếu hãng, thiếu sân bay, sai thời gian hoặc thiếu tọa độ sẽ bị bỏ qua.")
api_rows = [
    ("Chuẩn hóa mã", "Chuyển carrier, origin, dest và flight_id thành chữ hoa"),
    ("Thời gian", "Phân tích scheduled theo timestamp và làm tròn xuống khung 30 phút"),
    ("Khoảng cách", "Tính great-circle distance từ tọa độ sân bay, đơn vị mile"),
    ("Mật độ", "Đếm chuyến cùng origin và cùng khung 30 phút trong snapshot"),
    ("Kiểm tra", "distance > 0; density ≥ 1; flight_id duy nhất trong CSV"),
    ("Bảo mật", "API key không lưu trong mã nguồn; ưu tiên biến môi trường"),
]
add_caption(doc, "Bảng 3.15 Quy tắc chuẩn hóa dữ liệu chuyến bay ngoài")
add_table(doc, ["Bước", "Quy tắc"], api_rows, widths=[4, 12], font_size=9.2)
add_source(doc, "live_feed.py.")
add_para(doc, "Mật độ tính từ snapshot phản ánh số chuyến quan sát được trong lần gọi API, không nhất thiết bằng toàn bộ lịch khai thác của sân bay. Ngoài ra, mô hình học từ năm 2008 có thể gặp mức phân loại hoặc phân phối mới. Vì vậy, dự báo cho chuyến hiện nay phải được gắn nhãn thử nghiệm và cần kiểm định lại trước khi sử dụng vận hành.")

add_heading(doc, "3.11 Kiểm thử ứng dụng", 1)
test_rows = [
    ("test_historical_hourly_profile", "Khôi phục profile theo giờ từ bảng đã làm trơn", "Đạt"),
    ("test_live_feed_validation_and_calendar", "Kiểm tra schema CSV và chuyển lịch", "Đạt"),
    ("test_live_feed_rejects_missing_density", "Từ chối CSV thiếu mật độ 30 phút", "Đạt"),
    ("test_aviationstack_payload_is_normalized", "Chuẩn hóa payload Aviationstack", "Đạt"),
    ("test_error_columns_use_actual_minus_prediction", "Kiểm tra quy ước residual và nhóm sai số", "Đạt"),
    ("test_summary_computes_mae_rmse_and_bias", "Đối chiếu công thức MAE, RMSE và bias", "Đạt"),
    ("test_group_bootstrap_is_reproducible", "Kiểm tra bootstrap theo nhóm với seed cố định", "Đạt"),
    ("test_feature_order_half_hour_and_categories", "Kiểm tra thứ tự và kiểu của 18 đặc trưng", "Đạt"),
    ("test_unknown_route_uses_global_fallback_and_warns", "Kiểm tra fallback và cảnh báo ngoài phạm vi", "Đạt"),
    ("test_invalid_time và calendar date", "Từ chối giờ hoặc ngày lịch không hợp lệ", "Đạt"),
    ("test_h2o_local.py", "Nạp binary model và dự báo mẫu", "Đã được dự án kiểm chứng trên WSL"),
    ("test_live_feed_local.py", "CSV → đặc trưng → H2O", "Đã được dự án kiểm chứng trên WSL"),
    ("Spark-HDFS smoke", "Đọc CSV, lọc 5 chuyến, ghi hai Parquet", "Đã được dự án kiểm chứng"),
]
add_caption(doc, "Bảng 3.16 Ma trận kiểm thử")
add_table(doc, ["Kiểm thử", "Mục tiêu", "Kết quả"], test_rows, widths=[5.2, 7.2, 3.6], font_size=8.9)
add_source(doc, "tests/test_dashboard_data.py, các chương trình test local và README.md.")
add_para(doc, "Mười hai kiểm thử đơn vị trong repository đã được chạy lại và đều đạt. Nhóm kiểm thử mới bao phủ công thức sai số, tính tái lập bootstrap, thứ tự đặc trưng, fallback, cảnh báo ngoài phân phối và kiểm tra ngày giờ. Hai phép thử H2O và smoke test HDFS phụ thuộc Java, H2O runtime và WSL nên được ghi nhận theo kết quả kiểm chứng của dự án. Khi nghiệm thu, cần chạy lại toàn bộ chuỗi kiểm thử trong đúng môi trường triển khai để phát hiện sai khác phiên bản.")

add_heading(doc, "3.12 Phân tích thực nghiệm mở rộng", 1)
add_para(doc, "Phần này khai thác sâu hơn các bảng xuất của dự án nhằm trả lời ba câu hỏi: tắc nghẽn thay đổi như thế nào theo thời gian và không gian; phần sai số tập trung ở nhóm chuyến nào; và kết quả tổng thể thay đổi ra sao khi loại các trường hợp cực đoan. Mọi phép tính đều sử dụng bảng tổng hợp có trong repository, không tái tạo dữ liệu chuyến bay chưa được lưu.")

add_heading(doc, "3.12.1 Nhịp TaxiOut theo giờ trong dữ liệu huấn luyện", 2)
add_para(doc, f"Bảng origin_hour_hist chứa {int(origin_hour['origin_hour_hist_n'].sum()):,} lượt quan sát lịch sử".replace(",", ".") + " thuộc giai đoạn huấn luyện. Vì giá trị trong bảng đã được làm trơn về trung bình toàn cục, TaxiOut trung bình gốc được khôi phục bằng cách đảo công thức làm trơn với hệ số 100. Trung bình có trọng số sau khôi phục bằng 16,4766 phút, khớp chính xác global_train_mean trong metadata.")
add_caption(doc, "Hình 3.5 TaxiOut trung bình theo giờ khởi hành trong dữ liệu huấn luyện")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(str(hourly_path), width=Cm(15.4))
add_source(doc, "Tính lại từ taxiout_deployment_v3/origin_hour_hist.csv và metadata.json.")
selected_hours = hourly.loc[hourly["dep_hour"].isin([5, 6, 7, 8, 9, 12, 16, 17, 18, 19, 20, 23])]
hour_table = [(str(int(r.dep_hour)), f"{int(r.flights):,}".replace(",", "."), f"{r.avg_taxi_out:.2f}") for r in selected_hours.itertuples()]
add_caption(doc, "Bảng 3.17 Các mốc TaxiOut theo giờ đáng chú ý")
add_table(doc, ["Giờ", "Số quan sát lịch sử", "TaxiOut trung bình"], hour_table,
          widths=[2.5, 6, 6.5], numeric_cols={0,1,2}, font_size=9.2)
add_source(doc, "Tính có trọng số từ origin_hour_hist.csv.")
add_para(doc, "TaxiOut tăng từ 13,70 phút lúc 5 giờ lên 17,16 phút lúc 9 giờ, giảm nhẹ giữa trưa rồi tăng trở lại vào buổi chiều. Đỉnh trong các giờ có lưu lượng đáng kể xuất hiện lúc 19 giờ với 17,56 phút. Từ 6 giờ đến 19 giờ, mức tăng là khoảng 2,57 phút, tương đương 17,1% so với 6 giờ. Mẫu hình này ủng hộ việc đưa dep_hour, half_hour_bin và is_peak_hour vào mô hình.")
add_para(doc, "Các giờ 0-4 có rất ít quan sát so với ban ngày nên không nên diễn giải mức trung bình của chúng như bằng chứng chắc chắn về vận hành ban đêm. Phân tích này mô tả TaxiOut trung bình theo giờ; nó không phải MAE theo giờ và không được dùng thay thế tệp error_by_hour_v3.csv còn thiếu.")

add_heading(doc, "3.12.2 Điểm nóng theo sân bay giờ tuyến bay và mật độ", 2)
oh_rows = []
for r in top_origin_hours.head(8).itertuples():
    oh_rows.append((r.Origin, str(int(r.dep_hour)), f"{int(r.origin_hour_hist_n):,}".replace(",", "."), f"{r.raw_avg_taxi:.2f}"))
add_caption(doc, "Bảng 3.18 Các tổ hợp sân bay giờ có TaxiOut cao với ít nhất 500 chuyến")
add_table(doc, ["Sân bay", "Giờ", "Số chuyến", "TaxiOut trung bình"], oh_rows,
          widths=[3.2, 2.2, 4.2, 5.4], numeric_cols={1,2,3}, font_size=9.2)
add_source(doc, "Khôi phục từ origin_hour_hist.csv; chỉ giữ tổ hợp có tối thiểu 500 chuyến.")
add_para(doc, "JFK chiếm năm trong tám tổ hợp đứng đầu, tập trung từ 16 đến 20 giờ; mức TaxiOut trung bình đạt khoảng 42,82-45,21 phút. EWR xuất hiện ở 18-20 giờ với mức 39,51-42,02 phút. Kết quả này nhất quán với bảng sai số theo sân bay, trong đó JFK và EWR thuộc nhóm khó dự báo, đồng thời cho thấy rủi ro không chỉ gắn với sân bay mà còn phụ thuộc mạnh vào thời điểm.")

route_rows = []
for r in top_routes.head(8).itertuples():
    route_rows.append((f"{r.Origin}-{r.Dest}", f"{int(r.route_hist_n):,}".replace(",", "."), f"{r.route_hist_taxi:.2f}"))
add_caption(doc, "Bảng 3.19 Các tuyến có TaxiOut lịch sử cao với ít nhất 500 chuyến")
add_table(doc, ["Tuyến", "Số chuyến", "TaxiOut lịch sử đã làm trơn"], route_rows,
          widths=[4, 4.5, 6.5], numeric_cols={1,2}, font_size=9.2)
add_source(doc, "taxiout_deployment_v3/route_hist.csv.")
add_para(doc, "Các tuyến đứng đầu chủ yếu khởi hành từ JFK. Tuyến JFK-PDX có TaxiOut lịch sử 45,47 phút trên 528 chuyến; JFK-SEA đạt 42,26 phút trên 1.380 chuyến. Điều này không có nghĩa khoảng cách bay gây ra TaxiOut dài; biến tuyến đang đồng thời mang thông tin về sân bay đi, sân bay đến, lịch khai thác và điều kiện vận hành đặc thù.")

density_rows = [(r.Origin, f"{r.origin_avg_density:.2f}") for r in top_density.head(8).itertuples()]
add_caption(doc, "Bảng 3.20 Các sân bay có mật độ khởi hành tham chiếu cao nhất")
add_table(doc, ["Sân bay", "Mật độ trung bình trong khung 30 phút"], density_rows,
          widths=[4, 11], numeric_cols={1}, font_size=9.3)
add_source(doc, "taxiout_deployment_v3/origin_density_hist.csv.")
add_para(doc, f"Trong 301 sân bay, trung vị origin_avg_density chỉ là {density['origin_avg_density'].median():.2f} chuyến mỗi khung 30 phút, trong khi ATL đạt {density['origin_avg_density'].max():.2f}. Phân vị 90 là {density['origin_avg_density'].quantile(.9):.2f} và phân vị 95 là {density['origin_avg_density'].quantile(.95):.2f}. Phân phối lệch phải này cho thấy mật độ tuyệt đối không thể so sánh trực tiếp giữa sân bay nhỏ và hub lớn; relative_density vì vậy là đặc trưng cần thiết để chuẩn hóa theo quy mô sân bay.")

add_heading(doc, "3.12.3 Mức độ tập trung của sai số", 2)
contrib_rows = []
for r in bands.itertuples():
    contrib_rows.append((r.actual_band, f"{r.share_pct:.2f}%", f"{r.MAE:.2f}", f"{r.error_contribution_pct:.2f}%", f"{r.MAE/weighted_mae:.2f} lần"))
add_caption(doc, "Bảng 3.21 Đóng góp của từng nhóm vào tổng sai số tuyệt đối")
add_table(doc, ["Nhóm", "Tỷ trọng chuyến", "MAE", "Đóng góp sai số", "MAE so với chung"], contrib_rows,
          widths=[2.3, 3.3, 2.5, 3.5, 3.4], numeric_cols={1,2,3,4}, font_size=8.9)
add_source(doc, "Tính từ error_by_taxi_band_v3.csv; tổng đóng góp bằng 100%.")
add_caption(doc, "Hình 3.6 Tỷ trọng từng nhóm trong tổng sai số tuyệt đối")
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(str(contribution_path), width=Cm(15.2))
add_source(doc, "Dựng từ số chuyến nhân MAE của từng nhóm TaxiOut.")
add_para(doc, f"Hai nhóm trên 30 phút chỉ chiếm {tail_share:.2f}% số chuyến nhưng tạo ra {tail_error_share:.2f}% tổng sai số tuyệt đối. Riêng nhóm trên 60 phút có MAE gấp {bands.loc[bands['actual_band']=='>60','MAE'].iloc[0]/weighted_mae:.1f} lần MAE chung và đóng góp 10,65% sai số dù chỉ chiếm 1,06% mẫu. Vì vậy, chỉ báo cáo MAE 5,84 phút sẽ che khuất rủi ro ở đuôi phân phối.")
add_para(doc, f"Bias toàn tập tính từ năm nhóm là {weighted_bias:.2f} phút, khá gần 0. Tuy nhiên, giá trị tổng hợp này hình thành do bias âm ở các chuyến ngắn bù cho bias dương rất lớn ở các chuyến dài. Bias gần 0 không đồng nghĩa mô hình được hiệu chỉnh tốt trong từng phân khúc.")

add_heading(doc, "3.12.4 Phân tích độ nhạy với các trường hợp cực đoan", 2)
sensitivity_rows = [
    ("Toàn bộ tập test", "180.000", f"{weighted_mae:.3f}", "Chỉ số báo cáo chính"),
    ("Loại nhóm trên 60 phút", f"{int(bands.loc[bands['actual_band']!='>60','rows'].sum()):,}".replace(",", "."), f"{mae_without_over60:.3f}", "Giảm do loại 1,06% chuyến cực đoan"),
    ("Chỉ giữ TaxiOut không quá 30 phút", f"{int(bands.loc[normal_mask,'rows'].sum()):,}".replace(",", "."), f"{mae_upto30:.3f}", "Phản ánh vùng vận hành phổ biến"),
]
add_caption(doc, "Bảng 3.22 Độ nhạy của MAE khi thay đổi phạm vi đánh giá")
add_table(doc, ["Phạm vi", "Số chuyến", "MAE tái tính", "Diễn giải"], sensitivity_rows,
          widths=[5, 3, 3, 5], numeric_cols={1,2}, font_size=9.1)
add_source(doc, "Tái tính từ tổng sai số tuyệt đối của các nhóm TaxiOut.")
add_para(doc, f"Khi loại riêng nhóm trên 60 phút, MAE giảm từ 5,845 xuống {mae_without_over60:.3f} phút, tương đương giảm {(weighted_mae-mae_without_over60)/weighted_mae*100:.1f}%. Khi chỉ xét TaxiOut không quá 30 phút, MAE còn {mae_upto30:.3f} phút. Kết quả chứng minh hiệu năng tổng thể nhạy với một số ít chuyến tắc nghẽn nặng và củng cố yêu cầu báo cáo chỉ số theo phân khúc.")

add_heading(doc, "3.12.5 Tình huống dự đoán tham chiếu", 2)
case_rows = [
    ("Tuyến", meta["reference_prediction"]["route"]),
    ("Giờ khởi hành", meta["reference_prediction"]["time"]),
    ("Mô hình", meta["model_id"]),
    ("Kết quả tham chiếu", f"{meta['reference_prediction']['expected_minutes']:.1f} phút"),
    ("Các bước xử lý", "Tạo lịch và khung 30 phút; tra sân bay-giờ, tuyến, hãng-sân bay; tính mật độ tương đối; suy luận H2O"),
]
add_caption(doc, "Bảng 3.23 Tình huống dự đoán được lưu trong metadata")
add_table(doc, ["Nội dung", "Giá trị"], case_rows, widths=[4.2, 10.8], font_size=9.2)
add_source(doc, "taxiout_deployment_v3/metadata.json và h2o_predictor.py.")
add_para(doc, "Kết quả 29,2 phút là phép kiểm tra tham chiếu cho gói triển khai, không phải thời gian thực tế của một chuyến cụ thể và không dùng để tính MAE. Giá trị này giúp phát hiện sai lệch môi trường: nếu cùng payload tham chiếu nhưng kết quả thay đổi đáng kể, cần kiểm tra phiên bản H2O, model binary, thứ tự 18 đặc trưng và các bảng tra.")

add_heading(doc, "3.12.6 Cơ chế hoàn thiện bằng chứng thực nghiệm", 2)
gap_rows = [
    ("Dự đoán cấp chuyến", "Đã bổ sung mã xuất", "test_predictions_v3.csv và Parquet"),
    ("Sai số đa chiều", "Đã bổ sung mã tổng hợp", "Theo sân bay, giờ, dải TaxiOut, hãng, mật độ và tuyến"),
    ("Khoảng tin cậy", "Đã bổ sung bootstrap theo ngày", "MAE và khoảng tin cậy 95% với 2.000 lần lấy mẫu"),
    ("Leaderboard AutoML", "Đã bổ sung lệnh xuất", "h2o_leaderboard_v3.csv"),
    ("Hệ số GLM", "Đã bổ sung xuất hệ số chuẩn hóa", "glm_coefficients_v3.csv khi mô hình thắng là GLM"),
    ("Tái lập lấy mẫu", "Đã lưu seed và phân phối", "sampling_manifest_v3.json và sampling_distribution_v3.csv"),
    ("Hiệu năng Spark", "Đã bổ sung báo cáo ETL", "Số dòng từng bước, partition, phiên bản và runtime"),
]
add_caption(doc, "Bảng 3.24 Bằng chứng thực nghiệm được pipeline hỗ trợ xuất")
add_table(doc, ["Nội dung", "Trạng thái source", "Đầu ra sau khi chạy"], gap_rows,
          widths=[4, 5, 7], font_size=8.8)
add_source(doc, "Đối chiếu repository với kaggle_recovery_cells.py và kaggle_steps_12_13.py.")
add_para(doc, "Source hiện đã có khả năng tạo đầy đủ các bằng chứng trên từ cùng một bảng dự đoán cấp chuyến, nhờ đó tránh tình trạng mỗi biểu đồ dùng một nguồn tính toán khác nhau. Tuy nhiên, các tệp mới chỉ trở thành bằng chứng thực nghiệm sau khi notebook được chạy lại trên Kaggle với dữ liệu gốc. Chương này không tự điền khoảng tin cậy, MAE theo giờ hoặc hệ số GLM khi chưa có đầu ra chạy thật.")

add_heading(doc, "3.13 Thảo luận kết quả và giá trị của hệ thống", 1)
add_para(doc, "Về mặt Big Data, đề tài đã liên kết được lưu trữ HDFS, xử lý Spark, huấn luyện H2O AutoML và phục vụ bằng Streamlit. Điểm có giá trị nhất không chỉ là một con số dự báo, mà là pipeline có thể kiểm chứng từ dữ liệu thô đến chỉ số và giao diện. Việc xuất model ID, feature_columns và các bảng tra làm giảm nguy cơ dùng sai mô hình hoặc sai thứ tự đặc trưng.")
add_para(doc, "Về mặt mô hình, mức giảm MAE 18,82% chứng minh đặc trưng bối cảnh mang lại lợi ích so với trung bình toàn cục. Tuy nhiên, R² 0,2034 và MAE 58,83 phút ở nhóm trên 60 phút chỉ ra giới hạn rõ ràng: mô hình chưa nắm bắt tốt các sự kiện bất thường. Các biến còn thiếu như thời tiết, cấu hình đường băng, loại tàu bay và ATC nhiều khả năng giải thích một phần phương sai còn lại.")
add_para(doc, "Về mặt ứng dụng, dashboard giúp người dùng nhìn thấy đồng thời hiệu năng tổng thể và sai số cục bộ. Đây là thiết kế phù hợp hơn chỉ hiển thị một dự báo đơn lẻ, bởi người dùng có thể nhận biết trường hợp sân bay hoặc dải TaxiOut mà mô hình yếu. Nếu phát triển tiếp, hệ thống nên bổ sung cảnh báo ngoài phân phối, khoảng dự báo, giám sát drift và tái huấn luyện bằng dữ liệu mới.")

add_heading(doc, "3.14 Hạn chế và phạm vi diễn giải", 1)
limitation_rows = [
    ("Tính thời sự", "Dữ liệu năm 2008 không phản ánh đầy đủ hạ tầng và lịch khai thác hiện nay", "Chỉ kết luận trên phạm vi dữ liệu nghiên cứu; tái huấn luyện bằng dữ liệu mới trước triển khai"),
    ("Thông tin đầu vào", "Thiếu thời tiết, đường băng, cổng, loại tàu bay, hàng đợi và ATC", "Không diễn giải mô hình như quan hệ nhân quả hoặc công cụ điều hành độc lập"),
    ("Khả năng giải thích", "R² chỉ đạt 0,2034", "Mô hình phát hiện tín hiệu có ích nhưng phần lớn biến thiên TaxiOut chưa được giải thích"),
    ("Đuôi phân phối", "Sai số tăng rất mạnh khi TaxiOut vượt 30 phút", "Báo cáo riêng theo dải và cảnh báo đối với tình huống tắc nghẽn nặng"),
    ("Lấy mẫu", "AutoML dùng tập mẫu thay vì toàn bộ dữ liệu", "Lưu seed, phân phối mẫu và kiểm tra lại trên toàn bộ dữ liệu khi đủ tài nguyên"),
    ("Tổng quát hóa", "Tập test vẫn thuộc cùng năm 2008", "Cần kiểm định ngoài thời gian và trên nhiều năm"),
    ("Giá trị nghiệp vụ", "Chưa đo trực tiếp nhiên liệu, chi phí hoặc mức cải thiện đúng giờ", "Chỉ khẳng định giá trị phân tích và minh họa kỹ thuật"),
]
add_caption(doc, "Bảng 3.25 Hạn chế chính và nguyên tắc diễn giải")
add_table(doc, ["Khía cạnh", "Hạn chế", "Cách diễn giải hoặc khắc phục"], limitation_rows,
          widths=[3.1, 6.1, 6.8], font_size=8.8)
add_source(doc, "Tổng hợp từ kết quả thực nghiệm và phạm vi dữ liệu của dự án.")
add_para(doc, "Các hạn chế này không phủ nhận giá trị của đề tài phân tích. Với mục tiêu khai phá quy luật TaxiOut và minh họa một pipeline Big Data có thể chạy, kiểm thử và truy vết, hệ thống đã đạt được đầu ra phù hợp. Điểm cần tránh là chuyển một kết quả phân tích có điều kiện thành tuyên bố về độ chính xác vận hành trong mọi bối cảnh.")

add_heading(doc, "3.15 Kết luận chương", 1)
add_para(doc, "Chương 3 đã mô tả đầy đủ kiến trúc, dữ liệu, quy trình Spark, đặc trưng, mô hình H2O AutoML, HDFS, dashboard và tích hợp Aviationstack. Kết quả được kiểm chứng bằng ba chỉ số chính, phân tích sai số theo 180.000 chuyến test và đối chiếu lại từ các bảng nhóm. Phân tích thực nghiệm mở rộng còn chỉ ra nhịp TaxiOut theo giờ, các điểm nóng sân bay-tuyến bay, độ lệch của mật độ và mức tập trung sai số ở đuôi phân phối. Mô hình GLM là phương án tốt nhất trong lần chạy hiện tại, phù hợp cho mục tiêu học tập, phân tích và minh họa pipeline Big Data.")
add_para(doc, "Source hoàn thiện đã bổ sung báo cáo chất lượng ETL, dự đoán cấp chuyến, phân tích sai số đa chiều, bootstrap, bằng chứng lấy mẫu, hệ số GLM, kiểm tra schema đặc trưng và cảnh báo ngoài phân phối. Phạm vi sử dụng vẫn cần được giữ đúng: đây chưa phải hệ thống dự báo vận hành độc lập. Độ tin cậy cao nhất nằm ở các chuyến TaxiOut phổ biến từ 11-20 phút; độ tin cậy giảm mạnh ở sự kiện tắc nghẽn dài và khi áp dụng cho dữ liệu hiện nay. Các kết luận này tạo cơ sở trực tiếp cho chương tiếp theo về hạn chế và hướng phát triển.")

doc.core_properties.title = "Chương 3 Xây dựng ứng dụng và trực quan hóa dữ liệu TaxiOut"
doc.core_properties.subject = "Spark H2O AutoML HDFS Streamlit"
doc.core_properties.author = "Nhóm thực hiện đề tài"
doc.core_properties.keywords = "TaxiOut, Big Data, Spark, H2O AutoML, HDFS, Streamlit"
doc.save(OUT)
print(OUT)

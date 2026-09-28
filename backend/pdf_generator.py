import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


def generate_pdf_buffer(data: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=150,
        bottomMargin=72,
        title=f"{data.get('product_name', 'Unnamed')} specification.pdf"
    )
    elements = []
    styles = getSampleStyleSheet()

    # ---------------------------------------------------------
    # Layout Config Parsing
    # ---------------------------------------------------------
    layout = data.get("layout", {})
    primary_color_hex = layout.get("primary_color", "#D3D3D3")
    primary_color = colors.HexColor(primary_color_hex)

    font_base = layout.get("font_family", "Times-Roman")
    if font_base == "Helvetica":
        font_bold = "Helvetica-Bold"
    elif font_base == "Courier":
        font_bold = "Courier-Bold"
    else:
        font_bold = "Times-Bold"
        font_base = "Times-Roman"

    table_style_pref = layout.get("table_style", "grid")
    logo_pos = layout.get("logo_position", "left").upper()

    # ---------------------------------------------------------
    # Custom Styles
    # ---------------------------------------------------------
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        fontName=font_bold,
        fontSize=14,
        spaceAfter=12,
    )

    normal_style = ParagraphStyle(
        "NormalStyle",
        parent=styles["Normal"],
        fontName=font_base,
        fontSize=10,
        leading=12,
    )

    bold_style = ParagraphStyle(
        "BoldStyle",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=10,
        leading=12,
    )

    header_title_style = ParagraphStyle(
        "HeaderTitleStyle", parent=bold_style, textColor=colors.black
    )

    # Header elements removed from flow; they will be drawn in the canvas callback

    # ---------------------------------------------------------
    # Base Table Style Builder
    # ---------------------------------------------------------
    def get_base_table_style(has_header=True):
        ts = [
            ("FONTNAME", (0, 0), (-1, -1), font_base),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        if table_style_pref == "grid" or table_style_pref == "zebra":
            ts.extend(
                [
                    ("BOX", (0, 0), (-1, -1), 1, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        elif table_style_pref == "minimal":
            ts.extend(
                [
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.black),
                    ("LINEABOVE", (0, 0), (-1, 0), 1, colors.black),
                    ("LINEBELOW", (0, -1), (-1, -1), 1, colors.black),
                ]
            )

        if has_header:
            ts.append(("BACKGROUND", (0, 0), (-1, 0), primary_color))
            ts.append(("TEXTCOLOR", (0, 0), (-1, 0), colors.black))
            ts.append(("FONTNAME", (0, 0), (-1, 0), font_bold))

        return ts

    # ---------------------------------------------------------
    # 2. Header Table
    # ---------------------------------------------------------
    header_data = [
        [
            Paragraph("PRODUCT NAME", header_title_style),
            Paragraph(
                f"<font size=11><b>{data.get('product_name', '')}</b></font>",
                bold_style,
            ),
            data.get("spec_number", ""),
        ],
        ["", "", f"Revision no: {data.get('revision_no', '')}"],
        ["", "", f"Effective Date: {data.get('effective_date', '')}"],
        ["", "", f"Revision Due Date: {data.get('revision_due_date', '')}"],
    ]

    t_header = Table(header_data, colWidths=[1.5 * inch, 3.5 * inch, 2.0 * inch])
    th_style = get_base_table_style(has_header=False)
    th_style.extend(
        [
            ("SPAN", (0, 0), (0, 3)),
            ("SPAN", (1, 0), (1, 3)),
            ("ALIGN", (1, 0), (1, 3), "CENTER"),
            ("BACKGROUND", (0, 0), (0, 3), primary_color),
            ("BACKGROUND", (1, 0), (1, 3), colors.lightgrey),
            ("BACKGROUND", (2, 0), (2, 3), colors.lightgrey),
        ]
    )
    t_header.setStyle(TableStyle(th_style))
    elements.append(t_header)
    elements.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 3. Metadata Table
    # ---------------------------------------------------------
    pairs = []
    if data.get("botanical_name"):
        pairs.append((
            "Botanical/ Scientific name",
            Paragraph(f"<i>{data.get('botanical_name', '')}</i>", normal_style)
        ))
    if data.get("plant_part_used"):
        pairs.append(("Plant part used", data.get("plant_part_used")))
    if data.get("standardization"):
        pairs.append(("Standardization", data.get("standardization")))
    if data.get("production_method"):
        pairs.append(("Production Method", data.get("production_method")))
    if data.get("shelf_life"):
        pairs.append(("Shelf Life", data.get("shelf_life")))
    if data.get("country_of_origin"):
        pairs.append(("Country of origin", data.get("country_of_origin")))

    meta_data = []
    current_row = []
    for label, value in pairs:
        current_row.extend([label, value])
        if len(current_row) == 4:
            meta_data.append(current_row)
            current_row = []
            
    has_odd_pair = False
    if current_row:
        current_row.extend(["", ""])
        meta_data.append(current_row)
        has_odd_pair = True

    if meta_data:
        t_meta = Table(
            meta_data, colWidths=[1.8 * inch, 1.7 * inch, 1.8 * inch, 1.7 * inch]
        )
        t_meta_style = get_base_table_style(has_header=False)
        if has_odd_pair:
            t_meta_style.append(("SPAN", (1, -1), (3, -1)))
        t_meta.setStyle(TableStyle(t_meta_style))
        elements.append(t_meta)
        elements.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 4. Tests Table  (one sub-table per category for correct page breaks)
    # ---------------------------------------------------------
    col_widths = [0.6 * inch, 1.8 * inch, 2.3 * inch, 2.3 * inch]

    def has_content(r):
        return any([
            str(r.get("sl_no", "")).strip(),
            str(r.get("protocol", "")).strip(),
            str(r.get("parameter", "")).strip(),
            str(r.get("limit", "")).strip(),
        ])

    # --- Column header row (rendered once as its own small table) ---
    hdr_style = get_base_table_style(has_header=True)
    hdr_style.extend([
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
    ])
    t_col_hdr = Table([["SL No", "Protocol", "Test Parameter", "Test Limit"]], colWidths=col_widths)
    t_col_hdr.setStyle(TableStyle(hdr_style))
    t_col_hdr.spaceAfter = 0
    elements.append(t_col_hdr)

    # --- One table per category, kept together on the same page ---
    for category in data.get("test_categories", []):
        rows = category.get("rows", [])
        if not rows or not any(has_content(r) for r in rows):
            continue

        cat_data = [
            [Paragraph(f"<b>{category.get('category', '')}</b>", bold_style), "", "", ""]
        ]

        # Build style: left + right + bottom outer borders only (no top) so adjacent
        # tables look like one continuous table with no gap or double-line.
        cat_style = [
            ("FONTNAME", (0, 0), (-1, -1), font_base),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
            ("LINEBEFORE", (0, 0), (0, -1), 1, colors.black),   # left outer
            ("LINEAFTER", (-1, 0), (-1, -1), 1, colors.black),  # right outer
            ("LINEBELOW", (0, -1), (-1, -1), 1, colors.black),  # bottom outer
            # Category header row styling
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
            ("LINEABOVE", (0, 0), (-1, 0), 1, colors.black),  # line above category header
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),  # line below category header
            ("ALIGN", (0, 1), (0, -1), "CENTER"),   # SL No centred
        ]

        row_idx = 1
        start_span_idx = -1
        start_protocol_idx = -1

        for i, row in enumerate(rows):
            sl_no = str(row.get("sl_no", ""))
            protocol = str(row.get("protocol", "")).replace("\n", "<br/>")
            parameter = str(row.get("parameter", "")).replace("\n", "<br/>")
            limit = str(row.get("limit", "")).replace("\n", "<br/>")

            p_protocol = Paragraph(protocol, normal_style) if protocol else ""
            p_parameter = Paragraph(parameter, normal_style) if parameter else ""
            p_limit = Paragraph(limit, normal_style) if limit else ""

            cat_data.append([sl_no, p_protocol, p_parameter, p_limit])

            if table_style_pref == "zebra" and (row_idx % 2 == 0):
                cat_style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#f9fafb")))

            # SL No spanning
            if sl_no != "":
                if start_span_idx != -1 and (row_idx - 1) > start_span_idx:
                    cat_style.append(("SPAN", (0, start_span_idx), (0, row_idx - 1)))
                start_span_idx = row_idx
            elif i == len(rows) - 1:
                if start_span_idx != -1 and row_idx > start_span_idx:
                    cat_style.append(("SPAN", (0, start_span_idx), (0, row_idx)))

            # Protocol spanning
            if protocol != "":
                if start_protocol_idx != -1 and (row_idx - 1) > start_protocol_idx:
                    cat_style.append(("SPAN", (1, start_protocol_idx), (1, row_idx - 1)))
                start_protocol_idx = row_idx
            elif i == len(rows) - 1:
                if start_protocol_idx != -1 and row_idx > start_protocol_idx:
                    cat_style.append(("SPAN", (1, start_protocol_idx), (1, row_idx)))

            row_idx += 1

        t_cat = Table(cat_data, colWidths=col_widths)
        t_cat.setStyle(TableStyle(cat_style))
        t_cat.spaceBefore = 0
        t_cat.spaceAfter = 0
        # KeepTogether ensures the category header never appears without its data
        elements.append(KeepTogether([t_cat]))

    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=15, spaceAfter=15))

    # ---------------------------------------------------------
    # 5. Additional Info Table
    # ---------------------------------------------------------
    add_info_data = [["ADDITIONAL INFORMATION", ""]]
    t_add_style = get_base_table_style(has_header=True)
    t_add_style.extend([("SPAN", (0, 0), (-1, 0))])

    row_idx = 1
    for info in data.get("additional_info", []):
        detail = info.get("detail", "").replace("\n", "<br/>")
        add_info_data.append(
            [info.get("parameter", ""), Paragraph(detail, normal_style)]
        )
        if table_style_pref == "zebra" and (row_idx % 2 == 0):
            t_add_style.append(
                ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#f9fafb"))
            )
        row_idx += 1

    t_add = Table(add_info_data, colWidths=[2 * inch, 5 * inch])
    t_add.setStyle(TableStyle(t_add_style))
    elements.append(t_add)
    elements.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 6. Footers
    # ---------------------------------------------------------
    for note in data.get("footer_notes", []):
        if "computer-generated" in note.lower():
            elements.append(Paragraph(f"<b><i>{note}</i></b>", normal_style))
        else:
            elements.append(Paragraph(note, normal_style))
        elements.append(Spacer(1, 5))

    # Build the PDF into the buffer
    def add_page_header_footer(canvas, doc):
        canvas.saveState()
        
        import sys
        def get_base_path():
            if getattr(sys, 'frozen', False):
                return sys._MEIPASS
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
            
        logo_path = os.path.join(get_base_path(), "bmi_logo.png")
        if os.path.exists(logo_path):
            img = Image(logo_path, width=1.5 * inch, height=1.3 * inch)
            if logo_pos in ["LEFT", "CENTER", "RIGHT"]:
                img.hAlign = logo_pos
            else:
                img.hAlign = "LEFT"
            img.wrapOn(canvas, doc.width, doc.topMargin)
            y = A4[1] - 36 - img.drawHeight
            if img.hAlign == 'CENTER':
                x = doc.leftMargin + (doc.width - img.drawWidth) / 2
            elif img.hAlign == 'RIGHT':
                x = doc.leftMargin + doc.width - img.drawWidth
            else:
                x = doc.leftMargin
            img.drawOn(canvas, x, y)
        else:
            y = A4[1] - 36 - 1.3 * inch
            
        title_text = "FINISHED PRODUCT SPECIFICATION"
        p_title = Paragraph(title_text, title_style)
        p_title.wrapOn(canvas, doc.width, doc.topMargin)
        y_title = y - 24
        p_title.drawOn(canvas, doc.leftMargin, y_title)

        # --- FOOTER ---
        footer_text = (
            "<b>Bio-Med Ingredients Pvt Ltd</b><br/>"
            "<b>Phase -1, Plot No. SC-1/48,Verna Industrial Estate, Verna, Salcete, Goa. 403722.</b><br/>"
            "Tel : +91 832 2782010,11,12,Email: info@biomedingredients.com,<br/>"
            " Website: www.biomedingredients.com"
        )
        footer_style = ParagraphStyle(
            'PageFooter', 
            parent=styles['Normal'], 
            alignment=TA_CENTER, 
            fontName=font_base, 
            fontSize=10, 
            leading=12
        )
        p = Paragraph(footer_text, footer_style)
        w, h = p.wrap(doc.width, doc.bottomMargin)
        p.drawOn(canvas, doc.leftMargin, 20)
        canvas.restoreState()

    # NumberedCanvas enables "Page X of Y" by tracking total pages in two passes
    from reportlab.pdfgen import canvas as pdfgen_canvas

    class NumberedCanvas(pdfgen_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            pdfgen_canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_page_number(num_pages)
                pdfgen_canvas.Canvas.showPage(self)
            pdfgen_canvas.Canvas.save(self)

        def _draw_page_number(self, page_count):
            self.setFont(font_base, 8)
            self.setFillColor(colors.black)
            text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(
                doc.leftMargin + doc.width,
                12,
                text
            )

    doc.build(elements, onFirstPage=add_page_header_footer, onLaterPages=add_page_header_footer, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer

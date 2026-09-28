import json
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
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


def generate_pdf(json_path, output_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=150,
        bottomMargin=72,
    )
    elements = []
    styles = getSampleStyleSheet()

    # Custom Styles
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        fontName="Times-Bold",
        fontSize=14,
        spaceAfter=12,
    )

    normal_style = ParagraphStyle(
        "NormalStyle",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=10,
        leading=12,
    )

    bold_style = ParagraphStyle(
        "BoldStyle",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=10,
        leading=12,
    )

    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.black,
    )

    # 1. Logo
    logo_path = "bmi_logo.png"
    if os.path.exists(logo_path):
        img = Image(logo_path, width=1.5 * inch, height=1.3 * inch)
        img.hAlign = "LEFT"
        elements.append(img)
    else:
        elements.append(Paragraph("[BMI Logo Placeholder]", normal_style))
        elements.append(Spacer(1, 0.5 * inch))

    elements.append(Paragraph("FINISHED PRODUCT SPECIFICATION", title_style))

    # 2. Header Table
    header_data = [
        [
            Paragraph("PRODUCT NAME", heading_style),
            Paragraph(
                f"<font size=11><b>{data['product_name']}</b></font>", heading_style
            ),
            data["spec_number"],
        ],
        ["", "", f"Effective Date: {data['effective_date']}"],
    ]

    t_header = Table(header_data, colWidths=[1.5 * inch, 3.5 * inch, 2.0 * inch])
    t_header.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
                ("SPAN", (0, 0), (0, 1)),
                ("SPAN", (1, 0), (1, 1)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 1), "CENTER"),
                ("BACKGROUND", (0, 0), (0, 1), colors.lightgrey),
                ("BACKGROUND", (1, 0), (1, 1), colors.lightgrey),
                ("BACKGROUND", (2, 0), (2, 1), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
            ]
        )
    )
    elements.append(t_header)
    elements.append(Spacer(1, 10))

    # 3. Metadata Table
    meta_data = [
        [
            "Botanical/ Scientific name",
            Paragraph(f"<i>{data['botanical_name']}</i>", normal_style),
            "Plant part used",
            data["plant_part_used"],
        ],
        [
            "Standardization",
            data["standardization"],
            "Production Method",
            data["production_method"],
        ],
        [
            "Shelf Life",
            data["shelf_life"],
            "Country of origin",
            data["country_of_origin"],
        ],
    ]
    t_meta = Table(
        meta_data, colWidths=[1.8 * inch, 1.7 * inch, 1.8 * inch, 1.7 * inch]
    )
    t_meta.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(t_meta)
    elements.append(Spacer(1, 10))

    # 4. Tests Table
    test_data = [["SL No", "Protocol", "Test Parameter", "Test Limit"]]

    t_test_style = [
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),  # SL No centered
    ]

    row_idx = 1
    for category in data["test_categories"]:
        test_data.append(
            [Paragraph(f"<b>{category['category']}</b>", heading_style), "", "", ""]
        )
        t_test_style.append(("SPAN", (0, row_idx), (-1, row_idx)))
        t_test_style.append(
            ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.lightgrey)
        )
        row_idx += 1

        start_span_idx = -1
        start_protocol_idx = -1
        for i, row in enumerate(category["rows"]):
            sl_no = row["sl_no"]
            protocol = row["protocol"].replace("\n", "<br/>")
            parameter = row["parameter"].replace("\n", "<br/>")
            limit = row["limit"].replace("\n", "<br/>")

            p_protocol = Paragraph(protocol, normal_style) if protocol else ""
            p_parameter = Paragraph(parameter, normal_style) if parameter else ""
            p_limit = Paragraph(limit, normal_style) if limit else ""

            test_data.append([sl_no, p_protocol, p_parameter, p_limit])

            # SL No spanning logic
            if sl_no != "":
                if start_span_idx != -1 and (row_idx - 1) > start_span_idx:
                    t_test_style.append(("SPAN", (0, start_span_idx), (0, row_idx - 1)))
                start_span_idx = row_idx
            elif i == len(category["rows"]) - 1:
                if start_span_idx != -1 and row_idx > start_span_idx:
                    t_test_style.append(("SPAN", (0, start_span_idx), (0, row_idx)))

            # Protocol spanning logic
            if protocol != "":
                if start_protocol_idx != -1 and (row_idx - 1) > start_protocol_idx:
                    t_test_style.append(
                        ("SPAN", (1, start_protocol_idx), (1, row_idx - 1))
                    )
                start_protocol_idx = row_idx
            elif i == len(category["rows"]) - 1:
                if start_protocol_idx != -1 and row_idx > start_protocol_idx:
                    t_test_style.append(("SPAN", (1, start_protocol_idx), (1, row_idx)))

            row_idx += 1

    t_test = Table(
        test_data, colWidths=[0.6 * inch, 1.8 * inch, 2.3 * inch, 2.3 * inch]
    )
    t_test.setStyle(TableStyle(t_test_style))
    elements.append(t_test)
    elements.append(Spacer(1, 10))

    # 5. Additional Info Table
    add_info_data = [["ADDITIONAL INFORMATION", ""]]
    t_add_style = [
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("SPAN", (0, 0), (-1, 0)),
        ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    for info in data["additional_info"]:
        detail = info["detail"].replace("\n", "<br/>")
        add_info_data.append([info["parameter"], Paragraph(detail, normal_style)])

    t_add = Table(add_info_data, colWidths=[2 * inch, 5 * inch])
    t_add.setStyle(TableStyle(t_add_style))
    elements.append(t_add)
    elements.append(Spacer(1, 10))

    # 6. Footers
    for note in data["footer_notes"]:
        if "computer-generated" in note.lower():
            elements.append(Paragraph(f"<b><i>{note}</i></b>", normal_style))
        else:
            elements.append(Paragraph(note, normal_style))
        elements.append(Spacer(1, 5))

    # Build
    footer_text = (
        "<b>Bio-Med Ingredients Pvt Ltd</b><br/>"
        "<b>Phase -1, Plot No. SC-1/48,Verna Industrial Estate, Verna, Salcete, Goa. 403722.</b><br/>"
        "Tel : +91 832 2782010,11,12,Email: info@biomedingredients.com,<br/>"
        " Website: www.biomedingredients.com"
    )
    footer_style = ParagraphStyle(
        "PageFooter",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontName="Times-Roman",
        fontSize=10,
        leading=12,
    )
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(footer_text, footer_style))

    doc.build(elements)
    print(f"Successfully generated {output_path}")


if __name__ == "__main__":
    generate_pdf("data.json", "output.pdf")

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

def test_header():
    doc = SimpleDocTemplate('test_header.pdf', pagesize=A4, rightMargin=36, leftMargin=36, topMargin=160, bottomMargin=72)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading2'], alignment=TA_CENTER, fontName='Times-Bold', fontSize=14)
    normal_style = styles['Normal']
    
    def add_header_footer(canvas, doc):
        canvas.saveState()
        # Header
        logo_path = 'bmi_logo.png'
        if os.path.exists(logo_path):
            img = Image(logo_path, width=1.5 * inch, height=1.3 * inch)
            img.hAlign = 'LEFT'
            img.wrapOn(canvas, doc.width, doc.topMargin)
            x = doc.leftMargin
            y = A4[1] - 36 - img.drawHeight
            img.drawOn(canvas, x, y)
        else:
            y = A4[1] - 36 - 1.3 * inch
        
        p_title = Paragraph('FINISHED PRODUCT SPECIFICATION', title_style)
        p_title.wrapOn(canvas, doc.width, doc.topMargin)
        y_title = y - 24
        p_title.drawOn(canvas, doc.leftMargin, y_title)
        
        canvas.restoreState()
        
    elements = [Paragraph('Hello World '*100, normal_style)] * 40
    doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)

test_header()

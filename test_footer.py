from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

doc = SimpleDocTemplate('test_footer.pdf', pagesize=A4, bottomMargin=72)
styles = getSampleStyleSheet()

def add_page_footer(canvas, doc):
    canvas.saveState()
    footer_text = '<b>Bio-Med Ingredients Pvt Limited</b><br/>Test'
    footer_style = ParagraphStyle(
        'PageFooter', 
        parent=styles['Normal'], 
        alignment=TA_CENTER, 
        fontName='Times-Roman', 
        fontSize=10, 
        leading=12
    )
    p = Paragraph(footer_text, footer_style)
    p.wrapOn(canvas, doc.width, doc.bottomMargin)
    p.drawOn(canvas, doc.leftMargin, 30)
    canvas.restoreState()

elements = [Paragraph('Hello', styles['Normal'])]
doc.build(elements, onFirstPage=add_page_footer, onLaterPages=add_page_footer)

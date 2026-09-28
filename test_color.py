from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

doc = SimpleDocTemplate('test_out.pdf')
styles = getSampleStyleSheet()
bold_white = ParagraphStyle('bw', parent=styles['Normal'], fontName='Times-Bold', textColor=colors.white)

data = [
    [Paragraph('P', bold_white), 'S'],
    ['A', 'B']
]

t = Table(data)
t.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), colors.black),
    ('TEXTCOLOR', (0,0), (-1,-1), colors.black)
]))

doc.build([t])

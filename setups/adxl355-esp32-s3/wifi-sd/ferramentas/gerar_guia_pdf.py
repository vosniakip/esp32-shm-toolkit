"""Regera o PDF e os esquemas vetoriais a partir do guia Markdown (ReportLab)."""
from pathlib import Path
import html
import re
import textwrap

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Preformatted, KeepTogether, Image)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing, Rect, Line, Polygon, String
from reportlab.graphics import renderSVG

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT/'docs'
FIGURES = DOCS/'figuras'
FIGURES.mkdir(exist_ok=True)
BLUE, INK, TEAL = colors.HexColor('#165879'), colors.HexColor('#183247'), colors.HexColor('#087e83')
PALE, BORDER = colors.HexColor('#f1f6f9'), colors.HexColor('#c9d9e3')
FONT, BOLD, MONO = 'Helvetica', 'Helvetica-Bold', 'Courier'
font_root = Path('/usr/share/fonts/truetype/dejavu')
if (font_root/'DejaVuSans.ttf').exists():
    for name, filename in [('Book','DejaVuSans.ttf'),('BookBold','DejaVuSans-Bold.ttf'),('BookMono','DejaVuSansMono.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(font_root/filename)))
    pdfmetrics.registerFontFamily('Book',normal='Book',bold='BookBold',italic='Book',boldItalic='BookBold')
    FONT, BOLD, MONO = 'Book', 'BookBold', 'BookMono'


def text(d,x,y,s,size=10,color=INK,anchor='start',bold=False):
    d.add(String(x,y,s,fontName=BOLD if bold else FONT,fontSize=size,fillColor=color,textAnchor=anchor))


def arrow(d,x1,y1,x2,y2,color=BLUE,width=1.5):
    import math
    d.add(Line(x1,y1,x2,y2,strokeColor=color,strokeWidth=width))
    angle=math.atan2(y2-y1,x2-x1)
    p=[]
    for delta in [0,2.55,-2.55]:
        radius=0 if delta==0 else 6
        p.extend([x2+radius*math.cos(angle+delta),y2+radius*math.sin(angle+delta)])
    d.add(Polygon(p,fillColor=color,strokeColor=color))


def wiring():
    d=Drawing(500,300)
    d.add(Rect(0,5,500,285,rx=8,ry=8,fillColor=PALE,strokeColor=BORDER))
    text(d,250,273,'Dois barramentos SPI | esquema lógico, sem escala',10,anchor='middle',bold=True)
    for x,w,title in [(8,130,'ADXL355'),(180,140,'ESP32-S3'),(378,114,'microSD')]:
        d.add(Rect(x,45,w,207,rx=5,ry=5,fillColor=colors.white,strokeColor=BLUE))
        text(d,x+w/2,232,title,11,anchor='middle',bold=True)
    sensor=[('VCC','3V3'),('GND','GND'),('CS/SCL','GPIO10'),('MOSI/SDA','GPIO11'),('SCLK','GPIO12'),('MISO/AS','GPIO13'),('DRDY','GPIO14')]
    sd=[('3V3','VCC'),('GND','GND'),('GPIO15','CS'),('GPIO16','SCK'),('GPIO17','MOSI'),('GPIO18','MISO')]
    for i,(pin,gpio) in enumerate(sensor):
        y=211-i*23
        color=colors.HexColor('#b53635') if i==0 else colors.HexColor('#5c6971') if i==1 else TEAL if i==3 else BLUE
        text(d,128,y-3,pin,8.5,anchor='end');text(d,190,y-3,gpio,8.5)
        d.add(Line(138,y,180,y,strokeColor=color,strokeWidth=1.8))
    for i,(gpio,pin) in enumerate(sd):
        y=211-i*23
        color=colors.HexColor('#b53635') if i==0 else colors.HexColor('#5c6971') if i==1 else TEAL if i==4 else BLUE
        text(d,310,y-3,gpio,8.5,anchor='end');text(d,387,y-3,pin,8.5)
        d.add(Line(320,y,378,y,strokeColor=color,strokeWidth=1.8))
    text(d,250,25,'3V3 e GND compartilhados na PCB | GPIO19/20 reservados ao USB',8.5,anchor='middle')
    return d


def orientations():
    d=Drawing(500,290)
    cards=[('xpos','Xn',(1,0,0),True),('xneg','Xn',(-1,0,0),False),('ypos','Yn',(0,1,0),True),
           ('yneg','Yn',(0,-1,0),False),('zpos','Zn',(0,0,1),True),('zneg','Zn',(0,0,-1),False)]
    for i,(name,axis,target,positive) in enumerate(cards):
        x=(i%3)*170;y=150-(i//3)*145
        d.add(Rect(x,y,160,133,rx=6,ry=6,fillColor=PALE,strokeColor=BORDER))
        text(d,x+12,y+113,name,11,bold=True)
        d.add(Rect(x+24,y+39,72,15,fillColor=colors.white,strokeColor=BLUE))
        arrow(d,x+60,y+58 if positive else y+91,x+60,y+96 if positive else y+57,color=TEAL,width=2)
        text(d,x+72,y+84,'+'+axis,9)
        arrow(d,x+126,y+94,x+126,y+58,color=colors.HexColor('#9e4545'))
        text(d,x+135,y+76,'g',9)
        text(d,x+80,y+22,'+'+axis+(' para cima' if positive else ' para baixo'),9,anchor='middle')
        text(d,x+80,y+7,'a_ref = '+str(target)+' g',8.2,anchor='middle')
    return d


def architecture():
    d=Drawing(500,245)
    def box(x,y,w,h,title,sub=None):
        d.add(Rect(x,y,w,h,rx=6,ry=6,fillColor=PALE,strokeColor=BORDER))
        text(d,x+w/2,y+h/2+(4 if sub else -3),title,10,anchor='middle',bold=True)
        if sub:text(d,x+w/2,y+h/2-12,sub,8,anchor='middle')
    box(5,177,145,48,'Navegador / Python','Comandos e estado')
    box(205,177,145,48,'Controle do nó','HTTP local')
    arrow(d,150,201,205,201)
    box(5,94,102,48,'ADXL355','FIFO + DRDY')
    box(138,94,100,48,'Aquisição','Prioridade alta')
    box(269,94,100,48,'RAM','Fila de amostras')
    box(400,94,95,48,'microSD','Gravação em blocos')
    arrow(d,107,118,138,118);arrow(d,238,118,269,118);arrow(d,369,118,400,118)
    arrow(d,245,177,195,142,color=TEAL)
    box(274,8,221,48,'Transferência posterior','Arquivo completo + integridade')
    arrow(d,448,94,448,56)
    box(5,8,221,48,'Computador','CSV, calibração e análises')
    arrow(d,274,32,226,32)
    return d


drawings={'ligacoes.svg':wiring(),'orientacoes.svg':orientations(),'arquitetura.svg':architecture()}
for name,drawing in drawings.items():
    renderSVG.drawToFile(drawing,str(FIGURES/name))

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyBook',fontName=FONT,fontSize=9.2,leading=13.6,textColor=INK,spaceAfter=7))
styles.add(ParagraphStyle(name='SectionBook',fontName=BOLD,fontSize=14,leading=18,textColor=BLUE,spaceBefore=14,spaceAfter=8,keepWithNext=True))
styles.add(ParagraphStyle(name='SubBook',fontName=BOLD,fontSize=10.8,leading=14,textColor=TEAL,spaceBefore=10,spaceAfter=6,keepWithNext=True))
styles.add(ParagraphStyle(name='CellBook',fontName=FONT,fontSize=8,leading=11,textColor=INK))
styles.add(ParagraphStyle(name='CellHead',fontName=BOLD,fontSize=8,leading=11,textColor=colors.white))
styles.add(ParagraphStyle(name='CodeBook',fontName=MONO,fontSize=7.5,leading=10,textColor=INK,backColor=PALE,borderPadding=8,spaceBefore=5,spaceAfter=10))
styles.add(ParagraphStyle(name='CaptionBook',fontName=FONT,fontSize=8.1,leading=11,textColor=colors.HexColor('#536c7c'),spaceAfter=12,alignment=TA_LEFT))
styles.add(ParagraphStyle(name='TOCBook',fontName=FONT,fontSize=9,leading=14,textColor=INK,spaceBefore=4,leftIndent=0,firstLineIndent=0))
styles.add(ParagraphStyle(name='BulletBook',parent=styles['BodyBook'],leftIndent=14,firstLineIndent=-10))


def inline(s):
    s=html.escape(s)
    s=re.sub(r'`([^`]+)`',lambda m:'<font name="'+MONO+'" size="8">'+m.group(1)+'</font>',s)
    s=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<link href="\2" color="#165879">\1</link>',s)
    return s


class Book(SimpleDocTemplate):
    def afterFlowable(self,flowable):
        key=getattr(flowable,'bookmark',None)
        if key:
            title=flowable.getPlainText()
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title,key,0,False)
            self.notify('TOCEntry',(0,title,self.page,key))


def footer(canvas,doc):
    canvas.saveState()
    w,h=A4
    canvas.setStrokeColor(BORDER);canvas.line(45,37,w-45,37)
    canvas.setFont(FONT,7.3);canvas.setFillColor(colors.HexColor('#526c7d'))
    canvas.drawString(45,25,'ADXL355 | ESP32-S3 | v3.0.0 - bancada; validação física pendente')
    canvas.drawRightString(w-45,25,str(doc.page))
    canvas.restoreState()


def table(lines):
    rows=[[x.strip() for x in line.strip().strip('|').split('|')] for line in lines]
    rows=[row for row in rows if not all(re.fullmatch('[: -]+',cell or '-') for cell in row)]
    n=len(rows[0]);width=505
    widths=([width*.30,width*.70] if n==2 else [width*.25,width*.32,width*.43] if n==3 else [width/n]*n)
    cells=[[Paragraph(inline(cell),styles['CellHead' if i==0 else 'CellBook']) for cell in row] for i,row in enumerate(rows)]
    result=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
    result.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LINEBELOW',(0,0),(-1,0),.6,BLUE),('LINEBELOW',(0,1),(-1,-1),.35,BORDER),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE])]))
    return [result,Spacer(1,9)]


story=[]
story += [Spacer(1,45),Paragraph('GUIA DE CONFIGURAÇÃO<br/>E ENSAIOS',ParagraphStyle('cover',fontName=BOLD,fontSize=27,leading=33,textColor=BLUE)),
          Spacer(1,16),Paragraph('ADXL355 + ESP32-S3',ParagraphStyle('subtitle',fontName=BOLD,fontSize=19,leading=25,textColor=TEAL)),
          Spacer(1,8),Paragraph('Controle por Wi-Fi · gravação local · transferência posterior',styles['BodyBook']),Spacer(1,25),architecture(),Spacer(1,16),
          Paragraph('<b>Versão 3.0.0 | 21 de outubro de 2026</b>',styles['BodyBook']),
          Paragraph('Inclui calibração matricial do conjunto inclinado, ruído/PSD, temporização, repetibilidade, deriva, vibração livre e Allan.',styles['BodyBook']),
          Paragraph('<b>Validação física pendente.</b> Os testes de software utilizam dados sintéticos. A compilação com o core real e os ensaios no seu hardware são etapas do roteiro.',styles['BodyBook']),
          Paragraph('Para copiar comandos longos, utilize também GUIA_COMPLETO.md, incluído na mesma pasta. Os arquivos da v2 original não foram substituídos.',styles['CaptionBook']),PageBreak()]
story.append(Paragraph('Conteúdo',styles['SectionBook']))
toc=TableOfContents();toc.levelStyles=[styles['TOCBook']];toc.dotsMinLevel=0
story += [toc,PageBreak()]
lines=(DOCS/'GUIA_COMPLETO.md').read_text(encoding='utf-8').splitlines()
paragraph=[];paragraph_style='BodyBook';i=0;section_counter=0


def flush():
    global paragraph,paragraph_style
    if paragraph:
        story.append(Paragraph(inline(' '.join(paragraph)),styles[paragraph_style]))
        paragraph=[];paragraph_style='BodyBook'


while i<len(lines):
    line=lines[i]
    if line.startswith('# '):i+=1;continue
    if line.startswith('## '):
        flush();section_counter+=1
        p=Paragraph(inline(line[3:]),styles['SectionBook']);p.bookmark='sec'+str(section_counter);story.append(p);i+=1;continue
    if line.startswith('### '):flush();story.append(Paragraph(inline(line[4:]),styles['SubBook']));i+=1;continue
    if line.startswith('```'):
        flush();code=[];i+=1
        while i<len(lines) and not lines[i].startswith('```'):
            chunks=textwrap.wrap(lines[i],width=100,break_long_words=False,break_on_hyphens=False,replace_whitespace=False,drop_whitespace=True) or ['']
            for j,chunk in enumerate(chunks):code.append(('  ' if j else '')+chunk+(' `' if j<len(chunks)-1 else ''))
            i+=1
        story.append(Preformatted('\n'.join(code),styles['CodeBook']));i+=1;continue
    if line.startswith('|'):
        flush();rows=[]
        while i<len(lines) and lines[i].startswith('|'):rows.append(lines[i]);i+=1
        story.extend(table(rows));continue
    image=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line.strip())
    if image:
        flush();caption,path=image.groups();p=DOCS/path
        if p.suffix=='.svg':
            drawing=drawings[p.name]
            graphic=Drawing(drawing.width,drawing.height);graphic.add(drawing)
        else:
            graphic=Image(str(p));ratio=505/graphic.imageWidth;graphic.drawWidth=505;graphic.drawHeight=graphic.imageHeight*ratio
        story.append(KeepTogether([Spacer(1,6),graphic,Paragraph(inline(caption),styles['CaptionBook'])]));i+=1;continue
    if not line.strip():flush();i+=1;continue
    if re.match(r'^\d+\. |^- ',line):
        flush();paragraph_style='BulletBook';paragraph=[line];i+=1;continue
    paragraph.append(line.strip());i+=1
flush()
output=DOCS/'GUIA_COMPLETO.pdf'
book=Book(str(output),pagesize=A4,rightMargin=45,leftMargin=45,topMargin=43,bottomMargin=50,
          title='ADXL355 + ESP32-S3 - Guia completo de configuracao e ensaios',author='Pacote de bancada ADXL355',
          subject='Wi-Fi, microSD, calibracao matricial e caracterizacao')
book.multiBuild(story,onFirstPage=footer,onLaterPages=footer)
print(output)

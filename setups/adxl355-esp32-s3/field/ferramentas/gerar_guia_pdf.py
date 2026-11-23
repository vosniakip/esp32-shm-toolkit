"""Gera o guia PDF do Markdown e do apendice metodologico. Requer reportlab e matplotlib."""
from pathlib import Path
import re,html
import matplotlib
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,Preformatted,PageBreak,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
ROOT=Path(__file__).resolve().parents[1];font=Path(matplotlib.get_data_path())/'fonts/ttf'
for name,file in [('Body','DejaVuSans.ttf'),('Body-Bold','DejaVuSans-Bold.ttf'),('Body-Italic','DejaVuSans-Oblique.ttf'),('Mono','DejaVuSansMono.ttf')]:
 pdfmetrics.registerFont(TTFont(name,str(font/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Body-Bold',italic='Body-Italic',boldItalic='Body-Bold')
W=A4[0]-36*mm
styles={
 'body':ParagraphStyle('Body',fontName='Body',fontSize=10,leading=15,spaceAfter=8,textColor=colors.HexColor('#203746'),splitLongWords=True,allowWidows=0,allowOrphans=0),
 'h1':ParagraphStyle('H1',fontName='Body-Bold',fontSize=20,leading=26,spaceAfter=15,textColor=colors.HexColor('#174c6c'),keepWithNext=True),
 'h2':ParagraphStyle('H2',fontName='Body-Bold',fontSize=14,leading=19,spaceBefore=14,spaceAfter=9,textColor=colors.HexColor('#174c6c'),keepWithNext=True),
 'h3':ParagraphStyle('H3',fontName='Body-Bold',fontSize=11.5,leading=16,spaceBefore=11,spaceAfter=8,keepWithNext=True),
 'code':ParagraphStyle('Code',fontName='Mono',fontSize=7.5,leading=10.6,spaceBefore=4,spaceAfter=10,leftIndent=7,rightIndent=4,backColor=colors.HexColor('#f0f4f6'),borderPadding=6),
 'cell':ParagraphStyle('Cell',fontName='Body',fontSize=8.3,leading=11.5,spaceAfter=0,splitLongWords=True,allowWidows=0,allowOrphans=0),
 'head':ParagraphStyle('Head',fontName='Body-Bold',fontSize=8.3,leading=11.5,textColor=colors.white,spaceAfter=0,splitLongWords=True,allowWidows=0,allowOrphans=0),
 'list':ParagraphStyle('List',fontName='Body',fontSize=10,leading=15,spaceAfter=5,leftIndent=14,firstLineIndent=-12,splitLongWords=True,allowWidows=0,allowOrphans=0),
 'caption':ParagraphStyle('Caption',fontName='Body',fontSize=8.5,leading=12,spaceAfter=10,textColor=colors.HexColor('#536671'))}

def fmt(s):
 s=html.escape(s).replace('—','-').replace('–','-')
 s=re.sub(r'`([^`]+)`',lambda m:'<font name="Mono" size="8.5">'+m[1]+'</font>',s)
 s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
 return s

def parse(path,story):
 lines=Path(path).read_text(encoding='utf-8').splitlines();i=0
 while i<len(lines):
  line=lines[i].strip()
  if not line:i+=1;continue
  if line=='<!-- PAGEBREAK -->':story.append(PageBreak());i+=1;continue
  if line.startswith(('~~~','```')):
   fence=line[:3];i+=1;code=[]
   while i<len(lines) and not lines[i].strip().startswith(fence):code.append(lines[i]);i+=1
   story.append(KeepTogether([Preformatted('\n'.join(code),styles['code'],maxLineLength=103,splitChars=' ')]));i+=1;continue
  image=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line)
  if image:
   file=Path(path).parent/image[2]
   from PIL import Image as PILImage
   ww,hh=PILImage.open(file).size
   group=[Image(str(file),width=W,height=W*hh/ww),Paragraph(fmt(image[1])+'. Esquema sem escala.',styles['caption'])]
   if story and isinstance(story[-1],Paragraph) and getattr(story[-1].style,'keepWithNext',False):group.insert(0,story.pop())
   story.append(KeepTogether(group));i+=1;continue
  if line.startswith('|'):
   rows=[]
   while i<len(lines) and lines[i].strip().startswith('|'):
    row=[x.strip() for x in lines[i].strip().split('|')[1:-1]]
    if not all(re.fullmatch(r':?-+:?',x) for x in row):rows.append(row)
    i+=1
   n=len(rows[0]);data=[[Paragraph(fmt(c),styles['head' if j==0 else 'cell']) for c in row] for j,row in enumerate(rows)]
   if n==2:widths=[W*.30,W*.70]
   elif n==3:widths=[W*.25,W*.28,W*.47]
   else:widths=[W/n]*n
   t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
   t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#245c7e')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f6f8')]),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#cbd5dc')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
   if len(rows)>8:story.extend([t,Spacer(1,9)])
   else:story.append(KeepTogether([t,Spacer(1,9)]))
   continue
  if line.startswith('#'):
   level=len(line)-len(line.lstrip('#'))
   title=line[level:].strip()
   if Path(path).name=='GUIA_COMPLETO.md' and level==2 and title.startswith(('10. ','11. ','12. ')):story.append(PageBreak())
   story.append(Paragraph(fmt(title),styles['h'+str(min(3,level))]));i+=1;continue
  if re.match(r'^(\d+\.|-)\s',line):
   story.append(Paragraph(fmt(line),styles['list']));i+=1;continue
  paragraph=[line];i+=1
  while i<len(lines) and lines[i].strip() and not lines[i].strip().startswith(('#','|','~~~','```','![','<!--')) and not re.match(r'^(\d+\.|-)\s',lines[i].strip()):paragraph.append(lines[i].strip());i+=1
  story.append(Paragraph(fmt(' '.join(paragraph)),styles['body']))


def footer(c,doc):
 c.saveState();c.setStrokeColor(colors.HexColor('#cbd5dc'));c.line(18*mm,14*mm,A4[0]-18*mm,14*mm)
 c.setFont('Body',7.5);c.setFillColor(colors.HexColor('#637482'));c.drawString(18*mm,10*mm,'TFC Isaque | ADXL355 + ESP32-S3 | v4.1.0');c.drawRightString(A4[0]-18*mm,10*mm,str(doc.page));c.restoreState()


def main():
 out=ROOT/'docs/GUIA_COMPLETO.pdf';story=[];parse(ROOT/'docs/GUIA_COMPLETO.md',story);story.append(PageBreak());parse(ROOT/'docs/METODOLOGIA_E_REFERENCIAS.md',story)
 doc=SimpleDocTemplate(str(out),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=18*mm,bottomMargin=22*mm,title='ADXL355 + ESP32-S3: comparativos e passarela',author='TFC Isaque')
 doc.build(story,onFirstPage=footer,onLaterPages=footer);print(out)
if __name__=='__main__':main()

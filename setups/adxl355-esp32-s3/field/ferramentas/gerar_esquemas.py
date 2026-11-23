"""Esquemas vetoriais exatos de relacoes; nao representam dimensoes de fabricacao."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,FancyArrowPatch,Circle
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/figuras';OUT.mkdir(exist_ok=True,parents=True)
BLUE='#245c7e';GREEN='#26806a';GRAY='#637482';INK='#193342';LIGHT='#edf3f6'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11})

def setup(w=11,h=5):
 fig,ax=plt.subplots(figsize=(w,h),layout='constrained');ax.set(xlim=(0,11),ylim=(0,5));ax.set_aspect('equal');ax.axis('off');return fig,ax

def box(ax,x,y,w,h,text,color=BLUE):
 ax.add_patch(Rectangle((x,y),w,h,fc=LIGHT,ec=color,lw=1.7));ax.text(x+w/2,y+h/2,text,ha='center',va='center',color=INK,fontsize=10)

def arrow(ax,a,b,label='',color=GRAY,curve=0):
 ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=14,color=color,lw=1.5,connectionstyle=f'arc3,rad={curve}'))
 if label:
  if abs(a[0]-b[0])<.01:ax.text(a[0]+.15,(a[1]+b[1])/2,label,ha='left',va='center',fontsize=9,color=INK)
  else:ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+.15,label,ha='center',va='bottom',fontsize=9,color=INK)

def save(fig,name):
 fig.savefig(OUT/(name+'.png'),dpi=200,bbox_inches='tight');fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');plt.close(fig)

fig,ax=setup()
box(ax,.2,3.3,2.5,1,'Computador / celular\nRede própria do nó')
box(ax,4.1,3.3,2.6,1,'ESP32-S3\nComando e estado')
box(ax,4.1,1.25,2.6,1,'ADXL355 na PCB\nFIFO + DRDY',GREEN)
box(ax,8.2,1.25,2.5,1,'microSD\nArquivo bruto + log',GREEN)
box(ax,.2,.3,2.5,1,'Computador\nAnálise posterior')
arrow(ax,(2.7,3.95),(4.1,3.95),'HTTP local')
arrow(ax,(4.1,3.5),(2.7,3.5))
arrow(ax,(5.4,2.25),(5.4,3.3),'SPI')
arrow(ax,(6.7,3.5),(9.45,2.25),'Fila em RAM')
arrow(ax,(8.2,1.5),(2.7,.85),curve=-.08)
ax.text(6.1,.35,'Download após finalizar\nVerificação SHA-256',ha='center',va='center',fontsize=10,color=INK)
ax.text(8.8,4,'DAQ profissional:\nexportação independente',ha='center',va='center',fontsize=10,color=GRAY)
save(fig,'arquitetura')

fig,ax=setup()
x0,x1=1,10;y0,y1=1.5,2.6
ax.plot([x0,x1],[y0,y0],c=GRAY,lw=3);ax.plot([x0,x1],[y1,y1],c=GRAY,lw=3)
for i in range(6):
 x=x0+i*(x1-x0)/5
 ax.plot([x,x],[y0,y1],c=GRAY,lw=1.7)
 if i<5:
  xx=x0+(i+1)*(x1-x0)/5;ax.plot([x,xx],[y0,y1],c=GRAY,lw=1.5);ax.plot([x,xx],[y1,y0],c=GRAY,lw=1.5)
box(ax,5.1,2.7,1.3,.5,'Nó',BLUE);box(ax,6.5,2.7,1.5,.5,'Referência',GREEN)
ax.text(6.55,3.65,'Mesmo elemento rígido\nEixos comparados paralelos',ha='center',color=INK,fontsize=10)
arrow(ax,(3.5,4),(3.5,2.65),'Impacto')
box(ax,.4,.1,2.5,.6,'Martelo instrumentado\n(opcional)',GRAY)
box(ax,7.7,.1,2.8,.6,'DAQ profissional\nAceleração e força',GREEN)
arrow(ax,(7.3,2.7),(9.1,.75),'',GREEN)
ax.text(9.25,1.0,'Cabo',ha='left',va='center',fontsize=9,color=GREEN)
arrow(ax,(2.9,.4),(7.7,.4),'Força, quando medida',GRAY)
ax.text(1.1,1.1,'Apoio',color=GRAY,fontsize=9);ax.text(9.8,1.1,'Apoio',ha='right',color=GRAY,fontsize=9)
save(fig,'trelica')

fig,ax=setup()
box(ax,2.2,1.2,5.5,.7,'Superfície / adaptador rígido',GRAY)
box(ax,2.7,1.9,2.1,1.2,'Nó completo\nBase + PCB\nADXL355',BLUE)
box(ax,5.5,1.9,1.7,1.2,'Sensor\nprofissional',GREEN)
box(ax,3.6,.2,2.8,.7,'Shaker',GRAY)
arrow(ax,(4.9,.9),(4.9,1.2),'Excitação')
arrow(ax,(3.75,3.1),(3.75,4.15),'Eixo',BLUE)
arrow(ax,(6.35,3.1),(6.35,4.15),'Eixo',GREEN)
box(ax,8.5,2.15,2.2,.8,'DAQ\nprofissional',GREEN)
arrow(ax,(7.2,2.5),(8.5,2.5),'',GREEN)
ax.text(1,3.5,'Wi-Fi\ncomando e\ndownload',ha='center',color=BLUE,fontsize=10)
ax.text(5.4,4.7,'Frequência definida; amplitude medida pela referência',ha='center',color=INK)
save(fig,'shaker')

fig,ax=setup(h=4.7)
ax.set(ylim=(0,4.7))
ax.add_patch(Rectangle((.6,2.45),9.8,.22,fc=LIGHT,ec=GRAY,lw=1.5))
for x,pillar in [(.6,"A"),(5.5,"B"),(10.4,"C")]:
 ax.add_patch(Rectangle((x-.12,1.18),.24,1.25,fc=GRAY,ec=GRAY))
 ax.text(x,1.0,"Pilar "+pillar,ha="center",va="top",color=INK,fontsize=10)
for x,label in [(3.05,"P01"),(7.95,"P02")]:
 box(ax,x-.5,2.72,1,.42,label,BLUE)
 arrow(ax,(x,3.55),(x,3.15),"",BLUE)
 ax.text(x,3.72,"20 minutos",ha="center",color=BLUE,fontsize=12)
for left,right,label in [(.6,5.5,"Vão V1: L1"),(5.5,10.4,"Vão V2: L2")]:
 ax.annotate("",xy=(right,.5),xytext=(left,.5),arrowprops=dict(arrowstyle="|-|",color=GRAY))
 ax.text((left+right)/2,.64,label+" | ponto em L/2",ha="center",fontsize=10,color=INK)
ax.text(.6,4.38,"Botânico",ha="left",color=INK)
ax.text(10.4,4.38,"Politécnico",ha="right",color=INK)
arrow(ax,(2.1,4.38),(8.8,4.38),"Sentido adotado para X",BLUE)
ax.text(5.5,.05,"Um nó reposicionado. Medir L1 e L2 em campo; vãos não presumidos iguais.",ha="center",fontsize=9,color=GRAY)
save(fig,"passarela")

fig,ax=setup(h=5)
box(ax,.4,1.15,4.5,.42,"Elemento rígido do tabuleiro",GRAY)
box(ax,1.1,1.60,3.1,.18,"",GREEN)
box(ax,1.1,1.80,3.1,1.30,"Caixa + apoios + PCB\nADXL355 solidário ao conjunto",BLUE)
arrow(ax,(2.65,3.18),(2.65,4.22),"Z para cima",BLUE)
arrow(ax,(3.0,3.45),(4.6,3.45),"X",BLUE)
ax.text(2.65,.65,"Ligação fina e rígida; sem espuma",ha="center",color=INK,fontsize=10)
ax.plot([4.22,5.4,5.7],[1.7,1.7,2.1],c=GREEN,lw=1.2)
ax.text(5.8,2.15,"Adesivo ou fixação\nrígida autorizada",va="center",fontsize=10,color=GREEN)
box(ax,7.15,2.6,2.6,1.6,"Vista superior\nCaixa orientada\ncomo na calibração",BLUE)
arrow(ax,(6.9,2.12),(10.4,2.12),"",BLUE)
ax.text(8.65,1.85,"X: Botânico → Politécnico",ha="center",fontsize=10,color=BLUE)
arrow(ax,(6.9,2.12),(6.9,4.6),"",BLUE)
ax.text(8.3,4.8,"Y: esquerda de quem olha em +X",ha="center",fontsize=9,color=BLUE)
ax.text(8.45,1.25,"Z: para fora da vista superior\nX × Y = Z",ha="center",fontsize=10,color=INK)
ax.text(5.5,.1,"Eixos do conjunto: verificar a matriz e a orientação real. Não representam o chip inclinado.",ha="center",fontsize=9,color=GRAY)
save(fig,"fixacao_campo")

fig,ax=setup(h=4.5)
ax.set(ylim=(0,4.5))
items=[(.2,3.0,"Preparar e fixar P01"),(4.0,3.0,"Gravar P01\n1200 s"),(7.8,3.0,"Baixar e verificar P01"),
       (7.8,.8,"Reposicionar e fixar P02"),(4.0,.8,"Gravar P02\n1200 s"),(.2,.8,"Baixar e analisar\nP01 e P02 separados")]
for x,y,label in items:box(ax,x,y,3.0,.8,label)
arrow(ax,(3.2,3.4),(4.0,3.4));arrow(ax,(7.0,3.4),(7.8,3.4));arrow(ax,(9.3,3.0),(9.3,1.6));arrow(ax,(7.8,1.2),(7.0,1.2));arrow(ax,(4.0,1.2),(3.2,1.2))
ax.text(5.5,2.22,"40 min de dados + preparação + mudança de ponto + transferências",ha="center",fontsize=10,color=GREEN)
save(fig,"sequencia_passarela")
print(OUT)

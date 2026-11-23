from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT=Path(__file__).resolve().parent; R=ROOT/'resultados'; F=ROOT/'figuras';F.mkdir(exist_ok=True)
S=['MPU6050','MPU9250']; LABEL={'MPU6050':'MPU-6050','MPU9250':'GY-9250 (0x70)'}
C=['#1c5582','#bd5b25','#45805a']; AX=list('XYZ')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.labelsize':12,'axes.titlesize':13,
                     'legend.fontsize':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
def save(fig,name):
    fig.savefig(F/(name+'.png'),dpi=240,bbox_inches='tight',facecolor='white')
    fig.savefig(F/(name+'.svg'),bbox_inches='tight',facecolor='white');plt.close(fig)
def polish(ax):ax.grid(alpha=.2);ax.set_axisbelow(True)

cp=pd.read_csv(R/'calibracao_posicoes.csv');par=pd.read_csv(R/'calibracao_parametros.csv')
fig,axs=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
order=['xpos','xneg','ypos','yneg','zpos','zneg'];names=['X+','X−','Y+','Y−','Z+','Z−']
for s,ax in zip(S,axs):
    g=cp[cp.sensor==s].set_index('posicao').loc[order]
    ax.plot(names,(g.modulo_nominal_g-1)*100,'o-',c=C[0],label='Conversão nominal')
    ax.plot(names,(g.modulo_cal_g-1)*100,'s-',c=C[1],label='Correção diagonal')
    ax.axhline(0,c='0.3',lw=.8);ax.set_title(LABEL[s]);ax.set_ylabel('Desvio do módulo\nem relação a 1 g (%)');polish(ax)
axs[0].legend();save(fig,'01_calibracao_modulo')

fig,axs=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
for s,ax in zip(S,axs):
    g=cp[cp.sensor==s].set_index('posicao').loc[order]
    ax.bar(names,g.transversal_mg,color=C[0] if s==S[0] else C[1],width=.6)
    ax.set_title(LABEL[s]);ax.set_ylabel('Resultante transversal (mg)');ax.set_ylim(0,105);polish(ax)
save(fig,'02_calibracao_transversal')

fig,axs=plt.subplots(1,2,figsize=(10,3.6),layout='constrained',sharey=True)
for s,ax in zip(S,axs):
    p=pd.read_csv(R/('psd_'+s+'.csv'))
    for j,a in enumerate('xyz'):ax.plot(p.f_hz,np.sqrt(p[a+'_g2_Hz'])*1e6,c=C[j],label=a.upper(),lw=1)
    ax.axvspan(10,40,color='0.5',alpha=.08);ax.set_xlim(.5,60);ax.set_ylim(80,380)
    ax.set_xlabel('Frequência (Hz)');ax.set_ylabel('ASD (µg/√Hz)');ax.set_title(LABEL[s]);polish(ax);ax.legend(ncol=3)
save(fig,'03_ruido_asd')

n=pd.read_csv(R/'ruido_por_arquivo.csv')
fig,axs=plt.subplots(1,2,figsize=(10,3.2),layout='constrained',sharey=True)
for s,ax in zip(S,axs):
    for j,a in enumerate(AX):
        g=n[(n.sensor==s)&(n.eixo==a)];ax.plot(range(1,6),g.rms_banda_mg,'o-',color=C[j],label=a)
    ax.set_title(LABEL[s]);ax.set_xlabel('Aquisição em repouso');ax.set_ylabel('RMS na banda de 0,5–50 Hz (mg)');ax.set_xticks(range(1,6));polish(ax);ax.legend(ncol=3)
save(fig,'04_repetibilidade_ruido')

allan=pd.read_csv(R/'allan.csv');old={}
fig,axs=plt.subplots(1,2,figsize=(10,3.8),layout='constrained',sharex=True,sharey=True)
for s,ax in zip(S,axs):
    for j,a in enumerate(AX):
        g=allan[(allan.sensor==s)&(allan.eixo==a)];ax.loglog(g.tau_s,g.allan_ug,c=C[j],label=a,lw=1.6)
        mn=g.loc[g.allan_ug.idxmin()];ax.scatter([mn.tau_s],[mn.allan_ug],s=23,color=C[j],zorder=4)
    ax.set_title(LABEL[s]);ax.set_xlabel('Tempo de integração τ (s)');ax.set_ylabel('Desvio de Allan (µg)');ax.grid(which='both',alpha=.16);ax.legend(ncol=3)
save(fig,'05_desvio_allan')

trend=pd.read_csv(R/'allan_janelas.csv');gap=pd.read_csv(R/'lacunas.csv')
fig,axs=plt.subplots(2,2,figsize=(10,5),layout='constrained',sharex=True)
for k,s in enumerate(S):
    g=trend[trend.sensor==s].copy();g.loc[g.n<14000,['x_mg','y_mg','z_mg','temp_C']]=np.nan
    # Reindexa todos os minutos para interromper a curva nas lacunas.
    g['bin']=np.floor(g.t_min).astype(int);g=g.set_index('bin').reindex(range(240))
    for j,a in enumerate('xyz'):axs[0,k].plot(np.arange(240)+.5,g[a+'_mg']-g[a+'_mg'].iloc[0],c=C[j],label=a.upper(),lw=1)
    axs[1,k].plot(np.arange(240)+.5,g.temp_C,c='0.25',lw=1)
    if s==S[1]:
        for _,v in gap[gap.faltantes>100].iterrows():
            for ax in axs[:,k]:ax.axvspan(v.t_antes_s/60,v.t_depois_s/60,facecolor='#d88888',alpha=.25)
    axs[0,k].set_title(LABEL[s]);axs[0,k].set_ylabel('Variação da média\nem 60 s (mg)');axs[0,k].legend(ncol=3)
    axs[1,k].set_ylabel('Temperatura interna\nnominal (°C)');axs[1,k].set_xlabel('Tempo (min)')
    for ax in axs[:,k]:polish(ax);ax.set_xlim(0,240)
save(fig,'06_allan_tendencia_lacunas')

t=pd.read_csv(R/'aquecimento_janelas.csv');t=t[t.n>14000]
fig,axs=plt.subplots(2,1,figsize=(9,4.7),layout='constrained',sharex=True)
axs[0].plot(t.t_min,t.temp_C,c='0.25');axs[0].set_ylabel('Temperatura interna\nnominal (°C)')
thermal=[]
for j,a in enumerate('xyz'):
    axs[1].plot(t.t_min,t[a+'_mg']-t[a+'_mg'].iloc[0],c=C[j],label=a.upper())
    rr=stats.linregress(t.temp_C,t[a+'_mg']);thermal.append(dict(eixo=a.upper(),variacao_final_mg=t[a+'_mg'].iloc[-1]-t[a+'_mg'].iloc[0],
        amplitude_medias_mg=np.ptp(t[a+'_mg']),inclinacao_mg_C=rr.slope,r2=rr.rvalue**2))
axs[1].set_ylabel('Variação em relação\nao primeiro minuto (mg)');axs[1].set_xlabel('Tempo (min)');axs[1].legend(ncol=3)
for ax in axs:polish(ax);ax.set_xlim(0,60)
save(fig,'07_estabilidade_60min');pd.DataFrame(thermal).to_csv(R/'termica_resumo_recalculado.csv',index=False)

# Recontagem exata por eixo e por instante dos códigos extremos.
di=pd.read_csv(R/'dinamico.csv');clip=[]
for _,v in di.iterrows():
    p=next((ROOT/'entrada'/v.sensor/'dados/brutos').glob('*/dinamico*/'+v.arquivo));dd=pd.read_csv(p)
    raw=dd[['ax_raw','ay_raw','az_raw']].to_numpy();cl=(raw==-32768)|(raw==32767)
    rr=dict(sensor=v.sensor,arquivo=v.arquivo,n=len(raw),instantes_saturados=int(cl.any(axis=1).sum()),
            percentual_instantes=100*cl.any(axis=1).mean(),**{a+'_saturados':int(cl[:,j].sum()) for j,a in enumerate('xyz')})
    clip.append(rr)
cl=pd.DataFrame(clip);cl.to_csv(R/'saturacao.csv',index=False)
di=di.merge(cl,on=['sensor','arquivo']);di.to_csv(R/'dinamico_avaliado.csv',index=False)

fig,axs=plt.subplots(2,2,figsize=(10,5),layout='constrained')
for k,s in enumerate(S):
    v=di[di.sensor==s].iloc[0];z=np.load(R/(Path(v.arquivo).stem+'.npz'))
    j=int(z['eixo']);tt=z['t'];cal=z['cal']
    axs[0,k].plot(tt,cal[:,j],c=C[k],lw=.6);axs[0,k].set_title(LABEL[s]+'   eixo '+AX[j]);axs[0,k].set_xlabel('Tempo (s)');axs[0,k].set_ylabel('Aceleração corrigida (g)')
    # Zoom ao redor do primeiro código extremo, usando conversão nominal para exibir os limites ±2 g.
    p=next((ROOT/'entrada'/s/'dados/brutos').glob('*/dinamico*/'+v.arquivo));dd=pd.read_csv(p)
    raw=dd[['ax_raw','ay_raw','az_raw']].to_numpy();loc=np.flatnonzero((raw[:,j]==32767)|(raw[:,j]==-32768))[0];center=tt[loc]
    mask=(tt>=center-.18)&(tt<=center+.42)
    axs[1,k].plot(tt[mask],raw[mask,j]/16384,c=C[k],marker='.',ms=3,lw=.8)
    for bound in (-2,2):axs[1,k].axhline(bound,c='0.45',ls='--',lw=.8)
    axs[1,k].set_xlabel('Tempo (s)');axs[1,k].set_ylabel('Conversão nominal (g)');axs[1,k].set_title('Detalhe da saturação')
    for ax in axs[:,k]:polish(ax)
save(fig,'08_dinamico_saturacao')

fig,axs=plt.subplots(1,2,figsize=(10,3.2),layout='constrained')
for k,s in enumerate(S):
    for ii,(_,v) in enumerate(di[di.sensor==s].iterrows(),1):
        z=np.load(R/(Path(v.arquivo).stem+'.npz'));j=int(z['eixo']);f=z['f'];p=z['p'][:,j]
        axs[k].plot(f,p/p[(f>=.5)&(f<=50)].max(),lw=1,alpha=.8,label=str(ii))
    axs[k].set_xlim(16,19) if s==S[0] else axs[k].set_xlim(13,15)
    axs[k].set_title(LABEL[s]);axs[k].set_xlabel('Frequência (Hz)');axs[k].set_ylabel('PSD normalizada pelo pico');polish(axs[k]);axs[k].legend(title='Aquisição',ncol=4,fontsize=8)
save(fig,'09_dinamico_frequencias')
print('Figuras concluídas:',len(list(F.glob('*.png'))))
print(di.groupby('sensor').agg(n=('n','sum'),saturados=('instantes_saturados','sum'),min_pct=('percentual_instantes','min'),max_pct=('percentual_instantes','max')).to_string())

"""H1 por media de impactos com forca medida. Sem forca nao existe este resultado."""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import signal
from campo import *


def estimate_frf(reference,events,axis='z',pre=2,post=20,node=None,node_axis='z',sync=None,lo=.5,hi=50):
    if 'force' not in reference.channels or axis not in reference.channels:
        raise ValueError('Referencia precisa conter forca em N e aceleracao simultanea em m/s2.')
    if node is not None and sync is None:raise ValueError('FRF do no exige alinhamento por marcas; nao ajustar por correlacao para melhorar a FRF.')
    if pre<=.1 or post<=0:raise ValueError('Janela de impacto invalida.')
    tn=apply_sync(node,sync) if node is not None else None
    if node is not None and sync.get('csv_ref_sha256')!=sha256(reference.source):raise ValueError('Sincronismo de outra referencia.')
    fs=min(200.,reference.fs,tn.fs if tn else 200.)
    if hi>=.4*fs:raise ValueError('Banda fora do limite da grade comum.')
    length=int(round((pre+post)*fs));dt=1/fs
    F=[];R=[];N=[];quality=[];accepted_times=[]
    for item in events.to_dict('records'):
        ev=float(item['t_ref_s']);accepted=int(item.get('aceito',1))==1;reason=str(item.get('motivo',''))
        row=dict(evento=item.get('evento',len(quality)+1),t_ref_s=ev,aceito_operador=accepted,motivo_operador=reason)
        if accepted:
            if any(abs(ev-prev)<pre+post for prev in accepted_times):raise ValueError('Janelas de impactos se sobrepoem. Use mais intervalo ou menor janela justificada.')
            r=crop(reference,ev-pre-1,ev+post+1)
            pulse=(r.t>=ev-.05)&(r.t<=ev+.10)
            force=r.channels['force'];base=r.t<ev-.10
            baseline=float(np.std(force[base])) if base.any() else float('nan')
            maxf=float(np.max(np.abs(force[pulse])))
            peaks,_=signal.find_peaks(np.abs(force[pulse]),height=.2*maxf,distance=max(1,int(.005*r.fs)))
            double=len(peaks)>1;snr=maxf/max(baseline,1e-12)
            accepted=not double and snr>=10
            row.update(pico_forca_n=maxf,ruido_forca_dp_n=baseline,pico_sobre_ruido=snr,possivel_duplo_impacto=double,
                       amostragem_forca_hz=reference.fs,forca_fs_inferior_1000=reference.fs<1000)
            if accepted:
                grid=ev-pre+np.arange(length)*dt
                fv=lowpass_on_grid(r.t,force,grid)
                yv=lowpass_on_grid(r.t,r.channels[axis],grid)
                fv=fv-np.mean(fv[:max(1,int((pre-.1)*fs))]);yv=yv-np.mean(yv[:max(1,int((pre-.1)*fs))])
                F.append(np.fft.rfft(fv));R.append(np.fft.rfft(yv))
                if tn is not None:
                    check_sync_domain(node,grid[0],grid[-1],sync)
                    n=crop(tn,ev-pre-1,ev+post+1)
                    nv=lowpass_on_grid(n.t,n.channels[node_axis],grid);nv=nv-np.mean(nv[:max(1,int((pre-.1)*fs))])
                    N.append(np.fft.rfft(nv))
                accepted_times.append(ev)
        row['usado_na_media']=accepted;quality.append(row)
    quality=pd.DataFrame(quality)
    if len(F)<3:
        raise ValueError('Menos de tres impactos utilizaveis. Confira forca, duplo impacto e ficha de exclusoes. Nao ha coerencia de conjunto confiavel.')
    F=np.array(F);R=np.array(R);ff=np.fft.rfftfreq(length,1/fs)
    pff=np.mean(abs(F)**2,axis=0);mask=(ff>=lo)&(ff<=hi)
    if not mask.any():raise ValueError('Banda sem linhas espectrais.')
    energy_ok=pff>=np.max(pff[mask])*1e-2
    data=dict(f_hz=ff,energia_forca=pff,excitacao_suficiente=energy_ok)
    for label,Y in [('ref',R)]+([('no',np.array(N))] if N else []):
        cross=np.mean(Y*np.conj(F),axis=0);pyy=np.mean(abs(Y)**2,axis=0)
        h=np.divide(cross,pff,out=np.full(cross.shape,np.nan+0j),where=pff>1e-30)
        coh=np.divide(abs(cross)**2,pff*pyy,out=np.zeros(len(ff)),where=pff*pyy>1e-30)
        data['h1_'+label+'_ms2_n']=np.abs(h);data['coerencia_'+label]=np.clip(coh,0,1)
    if N:data['desvio_abs_h1_pct']=100*(data['h1_no_ms2_n']/data['h1_ref_ms2_n']-1)
    summary=dict(n_impactos_usados=len(F),fs_grade_hz=fs,df_hz=fs/length,janela='retangular; media anterior ao impacto removida; resposta precisa decair dentro da janela',
                 media='H1 = media(Y*conj(F))/media(abs(F)^2)',fase_comparada=False,
                 nota='Coerencia de conjunto entre impactos; nao excluir eventos por apresentarem resultados desfavoraveis. Limite de energia -20 dB e triagem exploratoria.',banda_hz=[lo,hi])
    return pd.DataFrame(data),quality,summary


def save_frf(data,quality,summary,out):
    table(data,out,'frf_h1');table(quality,out,'qualidade_impactos')
    plt=plot_setup();fig,ax=plt.subplots(2,1,figsize=(9,7),layout='constrained')
    f=data.f_hz.to_numpy();ok=data.excitacao_suficiente.to_numpy()
    for key,label in [('ref','Referencia'),('no','No')]:
        if 'h1_'+key+'_ms2_n' in data:
            ax[0].semilogy(f,np.where(ok,data['h1_'+key+'_ms2_n'],np.nan),label=label)
            ax[1].plot(f,data['coerencia_'+key],label=label)
    ax[0].set(ylabel='|H1| ((m/s2)/N)',title='FRF com forca medida e media de impactos')
    ax[1].set(ylabel='Coerencia',ylim=(0,1.02));ax[1].axhline(.8,ls='--',c='gray',label='0,8: triagem')
    for a in ax:a.set(xlim=summary['banda_hz'],xlabel='Frequencia (Hz)');a.legend()
    fig.savefig(Path(out)/'frf.png',dpi=200);fig.savefig(Path(out)/'frf.svg');plt.close(fig)

"""Analises v4: seno estacionario, impacto comparativo, PP/Welch e FDD local."""
from __future__ import annotations
from pathlib import Path
import json,math
import numpy as np
import pandas as pd
from scipy import signal
from scipy.optimize import linear_sum_assignment
from campo import *


def shaker(node,reference,axis_node,axis_ref,target,start_node=10,end_node=None,start_ref=10,end_ref=None):
    if axis_node not in node.channels or axis_ref not in reference.channels:raise ValueError('Eixo ausente.')
    n=crop(node,start_node,node.t[-1]-5 if end_node is None else end_node)
    r=crop(reference,start_ref,reference.t[-1]-5 if end_ref is None else end_ref)
    fn=fit_sine(n.t,n.channels[axis_node],target);fr=fit_sine(r.t,r.channels[axis_ref],target)
    f,p,q=spectrum(n.channels[axis_node],n.fs,min(16,n.t[-1]-n.t[0]))
    ff,pp,qq=spectrum(r.channels[axis_ref],r.fs,min(16,r.t[-1]-r.t[0]))
    result=dict(no=fn,referencia=fr,f_comando_hz=target,
                desvio_f_no_ref_pct=100*(fn['f_hz']/fr['f_hz']-1),
                desvio_amplitude_rms_pct=100*(fn['amplitude_rms_ms2']/fr['amplitude_rms_ms2']-1),
                razao_amplitudes=fn['amplitude_rms_ms2']/fr['amplitude_rms_ms2'],
                fase_comparada=False,
                nota='Ajustes independentes em regime estacionario. Desvio de frequencia inclui as bases de tempo. Comando do shaker nao substitui aceleracao de referencia.',
                janelas=dict(no=[float(n.t[0]),float(n.t[-1])],referencia=[float(r.t[0]),float(r.t[-1])]))
    return result,[(n,axis_node),(r,axis_ref)],[(f,p,q),(ff,pp,qq)]


def save_shaker(result,traces,spectra,out):
    table([dict(f_comando_hz=result['f_comando_hz'],f_no_hz=result['no']['f_hz'],f_ref_hz=result['referencia']['f_hz'],
                rms_no_ms2=result['no']['amplitude_rms_ms2'],rms_ref_ms2=result['referencia']['amplitude_rms_ms2'],
                desvio_f_pct=result['desvio_f_no_ref_pct'],desvio_rms_pct=result['desvio_amplitude_rms_pct'],
                razao_amplitudes=result['razao_amplitudes'],thd_no_pct=result['no']['thd_saida_pct'],thd_ref_pct=result['referencia']['thd_saida_pct'])],out,'metricas_shaker')
    plt=plot_setup();fig,ax=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for (tr,e),(f,p,q),label in zip(traces,spectra,['No','Referencia']):
        t=tr.t-tr.t[0];m=t<=min(3,10/result['f_comando_hz'])
        ax[0].plot(t[m],signal.detrend(tr.channels[e][m]),label=label)
        ax[1].semilogy(f,p,label=label)
        table(dict(f_hz=f,psd_ms4_hz=p),out,'psd_shaker_'+label.lower())
    ax[0].set(xlabel='Tempo local da janela (s)',ylabel='Aceleracao (m/s2)',title='Janelas locais, sem alinhamento de fase')
    ax[1].set(xlim=(max(.1,result['f_comando_hz']*.8),result['f_comando_hz']*1.2),xlabel='Frequencia (Hz)',ylabel='PSD ((m/s2)2/Hz)')
    for a in ax:a.legend()
    fig.savefig(Path(out)/'shaker.png',dpi=200);fig.savefig(Path(out)/'shaker.svg');plt.close(fig)


def compare_impulse(node,reference,en,er,event_n=None,event_r=None,pre=2,post=40,lo=.5,hi=50,segment=16,sync=None):
    if en not in node.channels or er not in reference.channels:raise ValueError('Eixo ausente.')
    if event_r is None:raise ValueError('Informe o instante do impacto na referencia.')
    full_n=node
    if sync:
        if sync.get('csv_ref_sha256')!=sha256(reference.source):raise ValueError('Alinhamento pertence a outra referencia.')
        check_sync_domain(node,event_r-pre,event_r+post,sync)
        full_n=apply_sync(node,sync);event_n=event_r
    elif event_n is None:raise ValueError('Sem alinhamento, informe tambem --impacto-no.')
    # Filtra os registros completos, preservando margem antes de recortar a resposta.
    yn=prepare_band(full_n.t,full_n.channels[en],lo,hi)
    yr=prepare_band(reference.t,reference.channels[er],lo,hi)
    if min(event_n-pre-full_n.t[0],full_n.t[-1]-event_n-post,
           event_r-pre-reference.t[0],reference.t[-1]-event_r-post)<2/lo:
        raise ValueError('Janela muito perto da borda: preserve pelo menos 2/fmin segundos de margem de filtragem.')
    nf=Trace(full_n.t,{en:yn},node.source,node.meta,node.qc)
    rf=Trace(reference.t,{er:yr},reference.source,reference.meta,reference.qc)
    n=crop(nf,event_n-pre,event_n+post);r=crop(rf,event_r-pre,event_r+post)
    f,p,q=spectrum(n.channels[en],n.fs,segment);ff,pp,qq=spectrum(r.channels[er],r.fs,segment)
    cn=find_candidates(f,p,lo,hi)[:10];cr=find_candidates(ff,pp,lo,hi)[:10]
    matches=[]
    if cn and cr:
        cost=np.abs(np.array([x['f_hz'] for x in cn])[:,None]-np.array([x['f_hz'] for x in cr])[None,:])
        ii,jj=linear_sum_assignment(cost)
        for i,j in zip(ii,jj):
            if cost[i,j]<=max(2*q['df_hz'],2*qq['df_hz'],.01*cr[j]['f_hz']):
                matches.append(dict(f_no_hz=cn[i]['f_hz'],f_ref_hz=cr[j]['f_hz'],desvio_f_pct=100*(cn[i]['f_hz']/cr[j]['f_hz']-1)))
    result=dict(rms_no_ms2=band_rms(f,p,lo,hi),rms_ref_ms2=band_rms(ff,pp,lo,hi),
                banda_hz=[lo,hi],picos_pareados=matches,espectro_no=q,espectro_ref=qq,
                comparacao_temporal=bool(sync),fase_validada=False,
                nota='PSD de resposta finita ao impacto. Nao e FRF sem forca medida. Desvios incluem fixacao, posicionamento e processamento.')
    result['desvio_rms_pct']=100*(result['rms_no_ms2']/max(result['rms_ref_ms2'],1e-30)-1)
    pair=None
    if sync:
        fs=min(200.,n.fs,r.fs)
        start=max(n.t[0],r.t[0])+1;end=min(n.t[-1],r.t[-1])-1
        grid=np.arange(start,end,1/fs)
        a=lowpass_on_grid(n.t,n.channels[en],grid);b=lowpass_on_grid(r.t,r.channels[er],grid)
        error=a-b;rmsref=np.sqrt(np.mean(b*b))
        corr=float(np.corrcoef(a,b)[0,1]) if np.std(a)>0 and np.std(b)>0 else None
        result.update(nrmse_pct=100*float(np.sqrt(np.mean(error*error)))/max(rmsref,1e-30),correlacao=corr,
                      grade_comum_hz=fs,diagnostico_alinhamento_s=sync['diagnostico_tempo_s'])
        nseg=min(int(segment*fs),len(grid))
        fc,c=signal.coherence(a,b,fs=fs,window='hann',nperseg=nseg,noverlap=nseg//2,detrend='constant')
        navg=1+(len(grid)-nseg)//(nseg-nseg//2)
        result['segmentos_coerencia']=navg
        if navg<2:c[:]=np.nan;result['nota_coerencia']='Nao calculada com apenas um segmento.'
        pair=(grid,a,b,fc,c)
    return result,[(n,en),(r,er)],[(f,p,q),(ff,pp,qq)],pair


def save_impulse(result,traces,spectra,pair,out):
    table(result['picos_pareados'],out,'picos_pareados')
    table([{k:v for k,v in result.items() if isinstance(v,(str,int,float,bool)) or v is None}],out,'metricas_trelica')
    plt=plot_setup();fig,ax=plt.subplots(2,1,figsize=(9,7),layout='constrained')
    if pair:
        t,a,b,fc,c=pair;ax[0].plot(t,a,label='No');ax[0].plot(t,b,alpha=.7,label='Referencia')
        table(dict(t_ref_s=t,no_ms2=a,referencia_ms2=b,erro_ms2=a-b),out,'sinais_alinhados')
        table(dict(f_hz=fc,coerencia=c),out,'coerencia')
        ax[0].set_title('Alinhamento por marcas externas ao sinal comparado')
    else:
        for (tr,e),label in zip(traces,['No','Referencia']):ax[0].plot(tr.t-tr.t[0],tr.channels[e],label=label)
        ax[0].set_title('Janelas locais: sem metricas amostra a amostra')
    for (f,p,q),label in zip(spectra,['No','Referencia']):
        ax[1].semilogy(f,p,label=label);table(dict(f_hz=f,psd_ms4_hz=p),out,'psd_trelica_'+label.lower())
    ax[0].set(xlabel='Tempo (s)',ylabel='Aceleracao (m/s2)');ax[1].set(xlim=result['banda_hz'],xlabel='Frequencia (Hz)',ylabel='PSD ((m/s2)2/Hz)')
    for a in ax:a.legend()
    fig.savefig(Path(out)/'trelica.png',dpi=200);fig.savefig(Path(out)/'trelica.svg');plt.close(fig)


def fdd(channels,fs,segment_s):
    x=np.asarray(channels);n=min(int(round(fs*segment_s)),len(x));m=x.shape[1]
    if m<2:raise ValueError('FDD requer ao menos dois canais simultaneos.')
    matrix=None
    for i in range(m):
        for j in range(i,m):
            f,p=signal.csd(x[:,i],x[:,j],fs=fs,window='hann',nperseg=n,noverlap=n//2,nfft=n,detrend='constant',scaling='density')
            if matrix is None:matrix=np.zeros((len(f),m,m),complex)
            matrix[:,i,j]=np.conj(p);matrix[:,j,i]=p
    values,vectors=np.linalg.eigh(matrix)
    values=np.maximum(values[:,::-1],0);vectors=vectors[:,:,::-1]
    return f,values,vectors


def identify(tr,lo=.5,hi=50,segment=64,blocks=4,prominence=6,cadences=(),discard=2):
    tr=crop(tr,tr.t[0]+discard,tr.t[-1])
    fs=tr.fs
    if hi>=fs*.4:raise ValueError('Limite superior deve ser menor que 40% da taxa.')
    if segment*lo<10:raise ValueError('Segmento com menos de dez periodos de fmin.')
    if tr.t[-1]-tr.t[0]<2.5*segment*blocks:
        raise ValueError('Registro curto para segmentos e blocos. Use mais duracao ou reduza --segmento-s/--blocos explicitamente.')
    axes=[e for e in 'xyz' if e in tr.channels];series={};spec={};settings=None
    for e in axes:
        f,p,q=spectrum(tr.channels[e],fs,segment);series[e]=p;spec[e]=(f,p);settings=q
    fd=None
    if len(axes)>=2:
        f,sv,u=fdd(np.column_stack([tr.channels[e] for e in axes]),fs,segment)
        series['fdd1']=sv[:,0];fd=(f,sv,u)
    pieces=np.array_split(np.arange(len(tr.t)),blocks)
    block_spectra={k:[] for k in series}
    for ix in pieces:
        for e in axes:
            bf,bp,_=spectrum(tr.channels[e][ix],fs,segment);block_spectra[e].append((bf,bp))
        if fd:
            bf,bv,_=fdd(np.column_stack([tr.channels[e][ix] for e in axes]),fs,segment)
            block_spectra['fdd1'].append((bf,bv[:,0]))
    rows=[];vectors=[]
    for key,p in series.items():
        peaks=find_candidates(f,p,lo,hi,prominence)
        for row in peaks:
            tol=max(2*settings['df_hz'],.005*row['f_hz']);found=[]
            for bf,bp in block_spectra[key]:
                local=find_candidates(bf,bp,lo,hi,prominence)
                choices=[r['f_hz'] for r in local if abs(r['f_hz']-row['f_hz'])<=tol]
                if choices:found.append(min(choices,key=lambda v:abs(v-row['f_hz'])))
            support=len(found)/blocks
            harmonics=[dict(cadencia_hz=float(c),ordem=k) for c in cadences for k in range(1,9) if abs(row['f_hz']-k*c)<=tol]
            label='candidata_consistente' if support>=.75 else 'pico_pouco_persistente'
            if harmonics:label='possivel_harmonico_da_excitacao'
            row.update(metodo='FDD_local' if key=='fdd1' else 'PP_Welch',canal=key,persistencia=support,
                       blocos_com_pico=len(found),n_blocos=blocks,f_media_blocos_hz=float(np.mean(found)) if found else None,
                       f_dp_blocos_hz=float(np.std(found,ddof=1)) if len(found)>1 else None,
                       classificacao=label,coincidencia_cadencia=bool(harmonics),df_hz=settings['df_hz'])
            rows.append(row)
            if key=='fdd1':
                i=int(np.argmin(abs(f-row['f_hz'])));v=u[i,:,0].copy();j=np.argmax(abs(v));v*=np.exp(-1j*np.angle(v[j]));v/=np.max(abs(v))
                vectors.append(dict(f_hz=float(f[i]),**{e+'_real':float(v[k].real) for k,e in enumerate(axes)},
                                    **{e+'_imag':float(v[k].imag) for k,e in enumerate(axes)}))
    result=dict(qc=tr.qc,banda_hz=[lo,hi],espectro=settings,n_blocos=blocks,descartado_inicio_s=discard,
                n_candidatas=len(rows),cadencias_informadas_hz=list(cadences),
                rms_banda_ms2={e:band_rms(*spec[e],lo,hi) for e in axes},
                metodo_principal='PP_Welch_com_persistencia',metodo_complementar='FDD_local' if fd else None,
                inferencia='Candidatas a frequencias naturais; requerem verificacao entre posicoes e condicoes de excitacao. Vetores sao locais, nao formas modais espaciais.',
                amortecimento_estimado=False,formas_modais_espaciais_estimadas=False)
    return result,pd.DataFrame(rows),vectors,(tr,axes,spec,fd)


def save_identification(result,peaks,vectors,extra,out):
    table(peaks,out,'frequencias_candidatas');table(vectors,out,'vetores_locais_de_canais')
    tr,axes,spec,fd=extra;plt=plot_setup()
    fig,ax=plt.subplots(2,1,figsize=(10,7),layout='constrained')
    for e in axes:
        f,p=spec[e];ax[0].semilogy(f,p,label=e.upper());table(dict(f_hz=f,psd_ms4_hz=p),out,'psd_'+e)
    if fd:
        f,sv,u=fd
        for i in range(sv.shape[1]):ax[1].semilogy(f,np.maximum(sv[:,i],1e-30),label='Valor singular '+str(i+1))
        table(dict(f_hz=f,**{'sv'+str(i+1):sv[:,i] for i in range(sv.shape[1])}),out,'fdd_valores_singulares')
    else:ax[1].text(.5,.5,'FDD indisponivel com um canal',transform=ax[1].transAxes,ha='center')
    ax[0].set_title('PP/Welch: frequencias candidatas em um ponto');ax[1].set_title('FDD local dos canais simultaneos')
    for a in ax:
        a.set(xlim=result['banda_hz'],xlabel='Frequencia (Hz)',ylabel='Densidade ((m/s2)2/Hz)');a.legend()
    fig.savefig(Path(out)/'passarela_espectros.png',dpi=200);fig.savefig(Path(out)/'passarela_espectros.svg');plt.close(fig)
    fig,axs=plt.subplots(len(axes),1,figsize=(10,2.7*len(axes)),layout='constrained',squeeze=False)
    for ax,e in zip(axs[:,0],axes):
        n=int(round(result['espectro']['nperseg']))
        f,t,s=signal.spectrogram(tr.channels[e],tr.fs,window='hann',nperseg=n,noverlap=n//2,detrend='constant',scaling='density')
        m=(f>=result['banda_hz'][0])&(f<=result['banda_hz'][1]);z=10*np.log10(np.maximum(s[m],1e-30))
        im=ax.pcolormesh((t+tr.t[0])/60,f[m],z,shading='auto',cmap='viridis')
        ax.set(xlabel='Tempo do registro (min)',ylabel='Frequencia (Hz)',title='Canal '+e.upper());fig.colorbar(im,ax=ax,label='PSD (dB re (m/s2)2/Hz)')
    fig.savefig(Path(out)/'passarela_espectrograma.png',dpi=200);plt.close(fig)

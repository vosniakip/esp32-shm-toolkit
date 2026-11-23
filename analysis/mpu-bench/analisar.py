"""Reanálise independente dos CSV experimentais. Entradas preservadas.
Executar no diretório que contém entrada/MPU6050 e entrada/MPU9250.
Python: numpy, pandas, scipy, matplotlib. Não concatena lacunas no cálculo de Allan.
"""
from pathlib import Path
import json, hashlib, platform
import numpy as np
import pandas as pd
from scipy import signal, stats

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'resultados'
OUT.mkdir(exist_ok=True)
AX = list('xyz')
COLS = ['ax_raw','ay_raw','az_raw']
SENSORS = ['MPU6050','MPU9250']

def write_csv(name, rows):
    df = rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    df.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    return df

def fields(line):
    return dict(v.split('=',1) for v in line.split(',') if '=' in v)

def integrate(f,p,lo,hi):
    inside=(f>lo)&(f<hi)
    xx=np.r_[lo,f[inside],hi]
    yy=np.r_[np.interp(lo,f,p),p[inside],np.interp(hi,f,p)]
    return np.trapezoid(yy,xx)

def contiguous(df):
    idx=df.indice.to_numpy(np.int64); tt=df.t_us.to_numpy(np.int64)
    di=np.diff(idx); dt=np.diff(tt)
    dt0=np.median(dt[(di==1)&(dt>0)])
    # Rupturas explícitas e intervalos anormalmente longos/curtos.
    breaks=np.flatnonzero((di!=1)|(dt<0.5*dt0)|(dt>1.5*dt0))+1
    return list(zip(np.r_[0,breaks],np.r_[breaks,len(df)]))

def temperature(raw,sensor):
    return raw/340+36.53 if sensor=='MPU6050' else raw/333.87+21

inventory=[]; means=[]; gaps=[]; dynamic=[]; noise=[]; allanrows=[]; thermal=[]
calibrations={}; noise_spectra={}; dynamic_spectra={}; allan_trend=[]

for sensor in SENSORS:
    base=ROOT/'entrada'/sensor/'dados'
    cj=json.loads(next((base/'calibracao').glob('*.json')).read_text(encoding='utf-8-sig'))
    offsets=np.array([cj['offset_lsb'][a] for a in AX]); scales=np.array([cj['sensibilidade_lsb_g'][a] for a in AX])
    calibrations[sensor]={'offsets':offsets.tolist(),'scales':scales.tolist()}
    for fpath in sorted((base/'brutos').glob('*/*/*.csv')):
        if fpath.with_suffix('.json').exists():
            meta=json.loads(fpath.with_suffix('.json').read_text(encoding='utf-8-sig'))
        else:
            log=fpath.with_suffix('.log.txt').read_text(encoding='utf-8-sig') if fpath.with_suffix('.log.txt').exists() else ''
            info=[l[l.index('#INFO'):].strip() for l in log.splitlines() if '#INFO' in l]
            meta=dict(ensaio=fpath.parent.name,posicao=fpath.stem.split('_')[-2],repeticao=int(fpath.stem.split('_')[-1][1:]),
                      duracao_s_solicitada=np.nan,mensagens_info=info,observacao='JSON ausente; captura sem dados')
        df=pd.read_csv(fpath)
        inf=fields(meta.get('mensagens_info',[''])[-1]) if meta.get('mensagens_info') else {}
        end=fields(meta.get('mensagem_final',''))
        kind=meta['ensaio']; n=len(df)
        row=dict(sensor=sensor,arquivo=fpath.name,ensaio=kind,posicao=meta['posicao'].lower(),
                 repeticao=meta['repeticao'],n=n,solicitado_s=meta['duracao_s_solicitada'],
                 id=inf.get('who_am_i',''),endereco=inf.get('endereco',''),
                 fim_confirmado=bool(end),invalidas=meta.get('linhas_invalidas',0),
                 fw_amostras=int(end.get('amostras',n)) if end else None,
                 observacao=meta.get('observacao',''),
                 sha256=hashlib.sha256(fpath.read_bytes()).hexdigest())
        if n<2:
            inventory.append(row);continue
        t=df.t_us.to_numpy(np.int64)/1e6; idx=df.indice.to_numpy(np.int64)
        raw=df[COLS].to_numpy(float); cal=(raw-offsets)/scales
        dt=np.diff(t); di=np.diff(idx); valid=(di==1)&(dt>0)
        span=t[-1]-t[0]
        fs=(idx[-1]-idx[0])/span
        periods=contiguous(df)
        device_n=int(end.get('amostras',idx[-1]+1))
        missing_inside=int(np.maximum(di-1,0).sum())
        row.update(span_s=span,fs_indice_hz=fs,fs_arquivo_hz=(n-1)/span,
                   dt_mediano_us=float(np.median(dt[valid])*1e6),
                   dt_dp_us=float(np.std(dt[valid],ddof=1)*1e6),
                   dt_p01_us=float(np.quantile(dt[valid],.01)*1e6),
                   dt_p99_us=float(np.quantile(dt[valid],.99)*1e6),
                   faltantes_internos=missing_inside,faltantes_final=device_n-n if end else None,
                   perdidas_firmware=int(df.perdidas_acum.max()),erros_i2c=int(df.erros_i2c.max()),
                   indice_duplicado=int((di==0).sum()),tempo_nao_crescente=int((dt<=0).sum()),
                   segmentos=len(periods),maior_segmento_s=max((b-a)/fs for a,b in periods),
                   saturados=int((np.abs(raw)>=32760).sum()),
                   temp_media_C=float(temperature(df.temp_raw.mean(),sensor)))
        for a in AX: row['distintos_'+a]=int(df['a'+a+'_raw'].nunique())
        inventory.append(row)
        for k in np.flatnonzero(di!=1):
            gaps.append(dict(sensor=sensor,arquivo=fpath.name,indice_antes=int(idx[k]),indice_depois=int(idx[k+1]),
                             t_antes_s=t[k],t_depois_s=t[k+1],faltantes=int(di[k]-1)))
        keep=(t-t[0])>=2
        mraw=raw[keep].mean(axis=0); mc=cal[keep].mean(axis=0)
        mrow=dict(sensor=sensor,arquivo=fpath.name,ensaio=kind,posicao=row['posicao'],repeticao=row['repeticao'],
                  n_util=int(keep.sum()),modulo_nominal_g=np.linalg.norm(mraw/16384),modulo_calibrado_g=np.linalg.norm(mc))
        for j,a in enumerate(AX):
            mrow.update({f'media_{a}_raw':mraw[j],f'media_{a}_cal_g':mc[j],f'dp_{a}_cal_mg':np.std(cal[keep,j],ddof=1)*1e3})
        means.append(mrow)

        if kind=='repouso':
            assert missing_inside==0 and len(periods)==1, 'Ruído requer tratamento das lacunas'
            f,p=signal.welch(cal[keep],fs=fs,window='hann',nperseg=4096,noverlap=2048,
                             detrend='constant',scaling='density',axis=0)
            noise_spectra.setdefault(sensor,[]).append((f,p))
            for j,a in enumerate(AX):
                band=np.sqrt(integrate(f,p[:,j],.5,50))*1e3
                density=np.sqrt(integrate(f,p[:,j],10,40)/30)*1e6
                noise.append(dict(sensor=sensor,arquivo=fpath.name,eixo=a.upper(),media_g=mc[j],
                                  dp_total_mg=np.std(cal[keep,j],ddof=1)*1e3,rms_banda_mg=band,
                                  densidade_eq_10_40_ug_rtHz=density,fs_hz=fs))

        if kind=='dinamico_exploratorio':
            assert missing_inside==0 and len(periods)==1, 'Dinâmico requer tratamento das lacunas'
            f,p=signal.welch(cal,fs=fs,window='hann',nperseg=min(4096,n),noverlap=min(4096,n)//2,
                             detrend='constant',scaling='density',axis=0)
            band=np.array([integrate(f,p[:,j],.5,50)**.5 for j in range(3)])
            j=int(np.argmax(band)); mask=(f>=.5)&(f<=50)
            k=np.flatnonzero(mask)[np.argmax(p[mask,j])]
            filt=signal.sosfiltfilt(signal.butter(4,[.5,50],fs=fs,btype='bandpass',output='sos'),cal,axis=0)
            # Segundo pico separado por >= 0,5 Hz serve apenas como diagnóstico de multimodalidade.
            peaks,_=signal.find_peaks(p[:,j],distance=max(1,int(.5/(f[1]-f[0]))))
            peaks=peaks[(f[peaks]>=.5)&(f[peaks]<=50)]
            peaks=sorted(peaks,key=lambda q:p[q,j],reverse=True)
            dynamic.append(dict(sensor=sensor,arquivo=fpath.name,eixo=AX[j].upper(),frequencia_hz=f[k],
                                resolucao_hz=f[1]-f[0],rms_banda_mg=band[j]*1e3,
                                pico_filtrado_mg=np.abs(filt[:,j]).max()*1e3,
                                segundo_pico_hz=f[peaks[1]] if len(peaks)>1 else np.nan,
                                razao_pico2_pico1=p[peaks[1],j]/p[k,j] if len(peaks)>1 else np.nan))
            dynamic_spectra[fpath.stem]=dict(sensor=sensor,t=t,cal=cal,filt=filt,f=f,p=p,eixo=j)

        if kind in ('allan','aquecimento'):
            # Janela de 60 s em tempo real, sem comprimir ausências.
            bucket=(t//60).astype(int)
            temp=temperature(df.temp_raw.to_numpy(float),sensor)
            dd=pd.DataFrame({'janela':bucket,'t':t,'temp_C':temp,**{a:cal[:,j] for j,a in enumerate(AX)}})
            grp=dd.groupby('janela'); avg=grp.mean(); count=grp.size()
            for w,v in avg.iterrows():
                z=dict(sensor=sensor,arquivo=fpath.name,ensaio=kind,t_min=float(v.t/60),n=int(count[w]),temp_C=float(v.temp_C))
                z.update({f'{a}_mg':float(v[a]*1000) for a in AX})
                (thermal if kind=='aquecimento' else allan_trend).append(z)

        if kind=='allan':
            # Nenhuma média ou diferença atravessa uma lacuna ou salto temporal.
            maxlen=max(b-a for a,b in periods)
            ms=np.unique(np.r_[np.round(np.geomspace(1,maxlen//10,80)).astype(int),
                               np.round(np.array([.1,1,10,100])*fs).astype(int)])
            segments=[np.vstack((np.zeros(3),np.cumsum(cal[a:b],axis=0,dtype=np.float64))) for a,b in periods if b-a>=2]
            for m in ms:
                sums=np.zeros(3); terms=0; blocks=0
                for c in segments:
                    if len(c)<=2*m:continue
                    d=(c[2*m:]-2*c[m:-m]+c[:-2*m])/m
                    sums+=np.einsum('ij,ij->j',d,d);terms+=len(d);blocks+=(len(c)-1)//m
                val=np.sqrt(sums/(2*terms))*1e6
                for j,a in enumerate(AX):allanrows.append(dict(sensor=sensor,eixo=a.upper(),m=int(m),tau_s=m/fs,
                                                              allan_ug=val[j],termos_sobrepostos=terms,blocos_aprox=blocks))
            print('Allan concluído',sensor,'segmentos',len(periods),flush=True)

inv=write_csv('inventario',inventory);mm=write_csv('medias',means);write_csv('lacunas',gaps)
nn=write_csv('ruido_por_arquivo',noise);write_csv('dinamico',dynamic);aa=write_csv('allan',allanrows)
write_csv('aquecimento_janelas',thermal);write_csv('allan_janelas',allan_trend)

parameters=[];poses=[];cv=[]
for s in SENSORS:
    dd=mm[(mm.sensor==s)&(mm.ensaio=='calibracao')]
    pos=dd.groupby('posicao')[[f'media_{a}_raw' for a in AX]].mean()
    b=np.array([(pos.loc[a+'pos',f'media_{a}_raw']+pos.loc[a+'neg',f'media_{a}_raw'])/2 for a in AX])
    sc=np.array([(pos.loc[a+'pos',f'media_{a}_raw']-pos.loc[a+'neg',f'media_{a}_raw'])/2 for a in AX])
    assert np.allclose(b,calibrations[s]['offsets'],atol=1e-6)
    assert np.allclose(sc,calibrations[s]['scales'],atol=1e-6)
    for j,a in enumerate(AX):parameters.append(dict(sensor=s,eixo=a.upper(),offset_LSB=b[j],offset_mg=b[j]/sc[j]*1000,
                                                    sensibilidade_LSB_g=sc[j],desvio_escala_pct=(sc[j]/16384-1)*100))
    for p,r in pos.iterrows():
        j=AX.index(p[0]);c=(r.to_numpy()-b)/sc
        target=np.zeros(3);target[j]=1 if p.endswith('pos') else -1
        reps=dd[dd.posicao==p];vars=reps[[f'media_{a}_cal_g' for a in AX]].to_numpy()
        poses.append(dict(sensor=s,posicao=p,modulo_nominal_g=np.linalg.norm(r.to_numpy()/16384),
                          modulo_cal_g=np.linalg.norm(c),erro_vetorial_mg=np.linalg.norm(c-target)*1000,
                          transversal_mg=np.linalg.norm(np.delete(c,j))*1000,
                          angulo_aparente_graus=np.degrees(np.arctan2(np.linalg.norm(np.delete(c,j)),abs(c[j]))),
                          dp_entre_medias_eixo_mg=np.std(vars[:,j],ddof=1)*1000,
                          amplitude_entre_medias_eixo_mg=np.ptp(vars[:,j])*1000,
                          **{a+'_cal_g':c[k] for k,a in enumerate(AX)}))
    # Validação interna: deixar uma repetição por posição de fora do ajuste.
    for rep in (1,2,3):
        tr=dd[dd.repeticao!=rep].groupby('posicao')[[f'media_{a}_raw' for a in AX]].mean()
        bb=np.array([(tr.loc[a+'pos',f'media_{a}_raw']+tr.loc[a+'neg',f'media_{a}_raw'])/2 for a in AX])
        ss=np.array([(tr.loc[a+'pos',f'media_{a}_raw']-tr.loc[a+'neg',f'media_{a}_raw'])/2 for a in AX])
        for _,r in dd[dd.repeticao==rep].iterrows():
            val=(r[[f'media_{a}_raw' for a in AX]].to_numpy(float)-bb)/ss
            j=AX.index(r.posicao[0]);target=1 if r.posicao.endswith('pos') else -1
            cv.append(dict(sensor=s,posicao=r.posicao,repeticao=rep,erro_eixo_mg=(val[j]-target)*1000,
                           erro_modulo_mg=(np.linalg.norm(val)-1)*1000))
write_csv('calibracao_parametros',parameters);write_csv('calibracao_posicoes',poses);write_csv('calibracao_validacao_interna',cv)
agg=nn.groupby(['sensor','eixo']).agg(n=('arquivo','count'),media_g=('media_g','mean'),
    dp_entre_medias_mg=('media_g',lambda x:np.std(x,ddof=1)*1000),
    amplitude_entre_medias_mg=('media_g',lambda x:np.ptp(x)*1000),
    rms_total_mg=('dp_total_mg','mean'),rms_total_dp_mg=('dp_total_mg','std'),
    rms_banda_mg=('rms_banda_mg','mean'),rms_banda_dp_mg=('rms_banda_mg','std'),
    asd_eq_10_40_ug_rtHz=('densidade_eq_10_40_ug_rtHz','mean'),
    asd_eq_dp=('densidade_eq_10_40_ug_rtHz','std')).reset_index()
agg['cv_rms_banda_pct']=agg.rms_banda_dp_mg/agg.rms_banda_mg*100
write_csv('ruido_agregado',agg)
mins=aa.loc[aa.groupby(['sensor','eixo']).allan_ug.idxmin()].copy()
write_csv('allan_minimos',mins)

# Armazena apenas séries necessárias às figuras; não duplica os arquivos longos.
for s,seq in noise_spectra.items():
    grid=seq[0][0];avg=np.mean([np.column_stack([np.interp(grid,f,p[:,j]) for j in range(3)]) for f,p in seq],axis=0)
    write_csv('psd_'+s,pd.DataFrame({'f_hz':grid,**{a+'_g2_Hz':avg[:,j] for j,a in enumerate(AX)}}))
for name,v in dynamic_spectra.items():
    np.savez_compressed(OUT/(name+'.npz'),**v)

summary={'calibration':calibrations,'version':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},
         'metodo':{'descarte_estaticos_s':2,'ruido_banda_Hz':[.5,50],'densidade_equivalente_banda_Hz':[10,40],
                   'welch_nperseg':4096,'welch_overlap':.5,'allan':'sobreposto, segmentos contíguos; sem passa-altas; tau<=maior_segmento/10',
                   'fs':'diferença dos índices / diferença dos timestamps, não número de linhas / duração quando há lacunas'}}
(OUT/'metodologia.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(inv.groupby(['sensor','ensaio']).agg(arquivos=('n','size'),amostras=('n','sum')).to_string())
print('\nRUIDO\n',agg.to_string(index=False))
print('\nALLAN\n',mins.to_string(index=False))

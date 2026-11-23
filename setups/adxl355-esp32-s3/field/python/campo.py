"""Dados em unidades SI, integridade e processamento comum dos ensaios v4."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from fractions import Fraction
import json
import math
import numpy as np
import pandas as pd
from scipy import signal, optimize
from comum import ler, converter, diagnostico, exigir_continuidade, nova_pasta, salvar_json, sha256, plot_setup

VERSION = '4.1.0'

@dataclass
class Trace:
    t: np.ndarray
    channels: dict[str, np.ndarray]
    source: str = ''
    meta: dict = field(default_factory=dict)
    qc: dict = field(default_factory=dict)

    @property
    def fs(self):
        return (len(self.t)-1)/(self.t[-1]-self.t[0])


def validate_trace(t, channels):
    t = np.asarray(t, dtype=float)
    if len(t) < 16 or not np.all(np.isfinite(t)):
        raise ValueError('Tempo invalido ou menos de 16 amostras.')
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError('Tempo repetido/decrescente. Nao ordenar ou remover linhas automaticamente.')
    median = np.median(dt)
    if np.max(dt) > 1.5*median or np.min(dt) < 0.5*median:
        raise ValueError('Lacuna ou irregularidade temporal excessiva. Nao interpolar perdas.')
    jitter = np.std(dt)/np.mean(dt)*100
    if jitter > 2:
        raise ValueError('Jitter RMS >2%: confira o tempo antes de usar metodos uniformes.')
    for key, v in channels.items():
        if len(v) != len(t) or not np.all(np.isfinite(v)):
            raise ValueError(f'Canal {key}: valor ausente/nao finito ou comprimento diferente.')
    return dict(n=len(t), fs_hz=(len(t)-1)/(t[-1]-t[0]), duracao_s=t[-1]-t[0],
                dt_dp_pct=jitter, dt_min_s=float(dt.min()), dt_max_s=float(dt.max()))


def load_node(path, calibration=None, g=9.80665, nominal_ok=False):
    import comum
    if abs(g-9.80665)>1e-9:
        raise ValueError('A unidade g usa 9.80665 m/s2. A gravidade local pertence ao ajuste da calibracao, nao a uma segunda conversao.')
    if not calibration and not nominal_ok:
        raise ValueError('Informe --calibracao; ou --permitir-nominal para diagnostico sem correcao.')
    comum.G0 = g
    d = converter(ler(path), calibration)
    exigir_continuidade(d)
    q = diagnostico(d)
    if q['perto_limite_digital']:
        raise ValueError('No perto do limite digital: repita com menor excitacao ou maior faixa e calibracao correspondente.')
    t = d.t_us.to_numpy(dtype=float)/1e6
    channels = {e: d['a'+e+'_ms2'].to_numpy(dtype=float) for e in 'xyz'}
    q.update(validate_trace(t, channels))
    return Trace(t, channels, str(Path(path).resolve()),
                 dict(d.attrs['metadados'], calibracao_aplicada=d.attrs['calibracao_aplicada'], g_ms2=g), q)


def load_reference(path):
    p = Path(path)
    meta = json.loads(p.with_suffix('.json').read_text(encoding='utf-8'))
    if meta.get('schema') != 'REFERENCIA_SI_V1':
        raise ValueError('Importe a referencia com 18_importar_referencia.py antes da analise.')
    if meta.get('csv_sha256') != sha256(p):
        raise ValueError('CSV da referencia alterado. Use o arquivo importado original.')
    d = pd.read_csv(p)
    channels = {e:d['a'+e+'_ms2'].to_numpy(dtype=float) for e in 'xyz' if 'a'+e+'_ms2' in d}
    if 'forca_n' in d:
        channels['force'] = d.forca_n.to_numpy(dtype=float)
    q = validate_trace(d.tempo_s.to_numpy(dtype=float), channels)
    for e, limit in meta.get('limites_abs_si', {}).items():
        if e in channels and limit is not None and np.any(np.abs(channels[e]) >= .98*float(limit)):
            raise ValueError(f'Referencia perto do limite declarado no canal {e}.')
    return Trace(d.tempo_s.to_numpy(dtype=float), channels, str(p.resolve()), meta, q)


def crop(tr, start=None, end=None):
    start = tr.t[0] if start is None else start
    end = tr.t[-1] if end is None else end
    if not np.isfinite([start,end]).all() or start >= end:
        raise ValueError('Janela temporal invalida.')
    if start < tr.t[0]-1/tr.fs or end > tr.t[-1]+1/tr.fs:
        raise ValueError(f'Janela {start:.3f} a {end:.3f} s nao cabe em {tr.source}.')
    m = (tr.t >= start)&(tr.t <= end)
    ch = {e:v[m] for e,v in tr.channels.items()}
    return Trace(tr.t[m], ch, tr.source, tr.meta, validate_trace(tr.t[m], ch))


def output(root, label, inputs, params):
    out = nova_pasta(root, label)
    manifest = dict(schema='ANALISE_CAMPO_V4', versao=VERSION, parametros=params,
                    entradas=[dict(arquivo=str(Path(p).resolve()),sha256=sha256(p)) for p in inputs if p],
                    status='em_execucao')
    salvar_json(manifest, out/'analise.json')
    return out


def finish(out, result):
    p=Path(out)/'analise.json'
    data=json.loads(p.read_text(encoding='utf-8'))
    data.update(status='concluido', resultados=result)
    salvar_json(data,p)


def table(data,out,name):
    df = data if isinstance(data,pd.DataFrame) else pd.DataFrame(data)
    df.to_csv(Path(out)/(name+'.csv'),index=False,float_format='%.12g')
    return df


def spectrum(x, fs, segment_s=64):
    n = min(int(round(segment_s*fs)), len(x))
    if n < 16:
        raise ValueError('Segmento espectral muito curto.')
    f,p=signal.welch(x,fs=fs,window='hann',nperseg=n,noverlap=n//2,
                     nfft=n,detrend='constant',scaling='density')
    navg=1+(len(x)-n)//(n-n//2)
    return f,p,dict(nperseg=n, df_hz=fs/n, enbw_hann_hz=1.5*fs/n, segmentos=navg)


def band_rms(f,p,lo=.5,hi=50):
    if not 0 < lo < hi <= f[-1]:
        raise ValueError('Banda fora do espectro.')
    m=(f>lo)&(f<hi)
    ff=np.r_[lo,f[m],hi]
    pp=np.r_[np.interp(lo,f,p),p[m],np.interp(hi,f,p)]
    return math.sqrt(max(float(np.trapezoid(pp,ff)),0))


def find_candidates(f,p,lo=.5,hi=50,prominence=6):
    db=10*np.log10(np.maximum(p,np.finfo(float).tiny))
    ids, props=signal.find_peaks(db,prominence=prominence,distance=2)
    rows=[]
    for k,i in enumerate(ids):
        if not lo<=f[i]<=hi:
            continue
        near=(np.abs(f-f[i])<=max(.5,8*(f[1]-f[0])))&(np.abs(f-f[i])>=3*(f[1]-f[0]))
        floor=np.median(p[near]) if near.any() else np.median(p)
        rows.append(dict(f_hz=float(f[i]), psd_si2_hz=float(p[i]),
                         proeminencia_db=float(props['prominences'][k]),
                         contraste_local_db=float(10*np.log10(p[i]/max(floor,1e-30)))))
    return sorted(rows,key=lambda x:x['psd_si2_hz'],reverse=True)


def fit_sine(t,y,target):
    if target<=0 or target>=.4/np.median(np.diff(t)):
        raise ValueError('Frequencia solicitada invalida para esta taxa.')
    t=np.asarray(t)-np.mean(t)
    y=np.asarray(y)
    duration=t[-1]-t[0]
    if duration*target < 20:
        raise ValueError('Janela com menos de 20 ciclos. Aumente a duracao/ajuste a janela.')
    fs=(len(t)-1)/duration
    f,p=signal.periodogram(signal.detrend(y),fs=fs,window='hann',scaling='spectrum')
    width=max(.10*target,3/duration)
    good=(f>=max(0,target-width))&(f<=target+width)
    if not good.any():raise ValueError('Banda de busca vazia.')
    center=f[np.flatnonzero(good)[np.argmax(p[good])]]
    def linear(freq):
        a=np.column_stack([np.ones(len(t)),t,np.sin(2*np.pi*freq*t),np.cos(2*np.pi*freq*t)])
        beta=np.linalg.lstsq(a,y,rcond=None)[0]
        return beta,y-a@beta
    lo=max(target-width,center-1.2/duration,1/duration)
    hi=min(target+width,center+1.2/duration)
    opt=optimize.minimize_scalar(lambda fr:np.mean(linear(fr)[1]**2),bounds=(lo,hi),method='bounded',options={'xatol':1e-10})
    freq=float(opt.x);beta,res=linear(freq)
    amp=float(np.hypot(beta[2],beta[3]))
    if amp<=0:raise ValueError('Amplitude fundamental nula.')
    harmonics=[k for k in range(1,6) if k*freq < .45*fs]
    a=np.column_stack([np.ones(len(t)),t]+[v for k in harmonics for v in (np.sin(2*np.pi*k*freq*t),np.cos(2*np.pi*k*freq*t))])
    coef=np.linalg.lstsq(a,y,rcond=None)[0]
    amps=[float(np.hypot(coef[2+2*i],coef[3+2*i])) for i in range(len(harmonics))]
    return dict(f_hz=freq, amplitude_pico_ms2=amp, amplitude_rms_ms2=amp/math.sqrt(2),
                residuo_rms_ms2=float(np.sqrt(np.mean(res**2))),
                harmonicos_medidos=harmonics, thd_saida_pct=100*math.sqrt(sum(v*v for v in amps[1:]))/max(amps[0],1e-30),
                ciclos=freq*duration, duracao_s=duration)


def lowpass_on_grid(t,y,grid):
    """FIR polifasico antialias; interpolacao sinc final corrige fase fracionaria e pequena razao racional."""
    fs=(len(t)-1)/(t[-1]-t[0]); target=1/np.median(np.diff(grid))
    if target > fs*1.02:
        raise ValueError('A grade comum nao pode exceder a menor taxa de origem.')
    ratio=Fraction(float(target/fs)).limit_denominator(2000)
    z=signal.resample_poly(y,ratio.numerator,ratio.denominator,padtype='line')
    effective=fs*ratio.numerator/ratio.denominator
    tz=t[0]+np.arange(len(z))/effective
    if grid[0]<tz[0] or grid[-1]>tz[-1]:raise ValueError('Grade fora dos dados reamostrados.')
    # Interpolacao fracionaria sinc/Kaiser: a interpolacao linear nesta taxa
    # poderia atenuar amplitudes, sobretudo perto de fmax.
    half=24;u=(grid-tz[0])*effective
    if u.min()<half or u.max()>len(z)-half-2:
        raise ValueError('Preserve margem temporal para interpolacao sinc (24 amostras de cada lado).')
    out=np.empty(len(grid));offsets=np.arange(-half,half+1)
    beta=8.6;normalizer=np.i0(beta)
    for start in range(0,len(grid),2048):
        uu=u[start:start+2048];ids=np.floor(uu).astype(int)[:,None]+offsets
        delta=uu[:,None]-ids
        valid=np.abs(delta)<=half
        window=np.where(valid,np.i0(beta*np.sqrt(np.maximum(0,1-(delta/half)**2)))/normalizer,0)
        weights=np.sinc(delta)*window
        weights/=weights.sum(axis=1)[:,None]
        out[start:start+len(uu)]=np.sum(z[ids]*weights,axis=1)
    return out


def apply_sync(tr,sync):
    if sync.get('schema')!='TEMPO_AFIM_V4' or not sync.get('ajuste_valido'):
        raise ValueError('Arquivo de alinhamento invalido.')
    a,b=float(sync['a_s']),float(sync['b'])
    if b<=0:raise ValueError('Escala temporal negativa.')
    tt=a+b*tr.t
    return Trace(tt,tr.channels,tr.source,dict(tr.meta,sincronismo=sync),validate_trace(tt,tr.channels))


def check_sync_domain(tr,start,end,sync):
    a,b=float(sync['a_s']),float(sync['b'])
    bounds=sorted(a+b*np.array(sync['dominio_no_s']))
    if start<bounds[0] or end>bounds[1]:
        raise ValueError('Janela fora das marcas: nao extrapolar o alinhamento temporal.')
    for key,source in [('csv_no_sha256',tr.source)]:
        if sync.get(key) and sync[key] != sha256(source):
            raise ValueError('Alinhamento pertence a outro CSV do no.')


def prepare_band(t,y,lo,hi):
    fs=(len(t)-1)/(t[-1]-t[0])
    if hi>=.4*fs:raise ValueError('Banda alta demais para a taxa.')
    if (t[-1]-t[0])*lo<10:raise ValueError('Registro com menos de dez periodos da menor frequencia.')
    return signal.sosfiltfilt(signal.butter(4,[lo,hi],btype='bandpass',fs=fs,output='sos'),y)

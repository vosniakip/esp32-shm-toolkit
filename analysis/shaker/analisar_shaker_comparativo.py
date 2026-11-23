"""Comparação descritiva do shaker: ADXL355 calibrado e blocos da referência.

Não estima erro de amplitude nem fase entre equipamentos sem escala e sincronismo.
Os CSVs profissionais são blocos independentes de 1 s; não são concatenados.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, platform, re
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import scipy
from scipy import signal, optimize
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

G0 = 9.80665
GROUPS = {5:'3,7V',15:'15 V',25:'25 V',50:'50 V'}

def digest(data): return hashlib.sha256(data).hexdigest()
def serial(obj):
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, np.generic): return obj.item()
    raise TypeError(type(obj).__name__)
def table(path, rows):
    if not rows: return
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter=';')
        writer.writeheader(); writer.writerows(rows)
def read_calibration(path):
    if path.suffix.lower()=='.zip':
        with ZipFile(path) as z:
            name=next(n for n in z.namelist() if n.endswith('/calibracao.json'))
            raw=z.read(name)
    else: raw=path.read_bytes()
    cal=json.loads(raw)
    return cal,raw
def bin_psd(x,fs,window='boxcar'):
    return signal.periodogram(x,fs=fs,window=window,detrend='constant',scaling='density')
def band_rms(f,p,low,high):
    # Midpoint bin weights; chosen integer bounds and full boundary bins.
    df=f[1]-f[0]
    weights=np.maximum(0,np.minimum(f+df/2,high)-np.maximum(f-df/2,low))
    return float(np.sqrt(np.sum(p*weights)))
def summary(values):
    a=np.asarray(values,float)
    return {'n':len(a),'media':float(a.mean()),'dp':float(a.std(ddof=1)) if len(a)>1 else None,
            'mediana':float(np.median(a)),'p05':float(np.quantile(a,.05)),
            'p95':float(np.quantile(a,.95)),'min':float(a.min()),'max':float(a.max())}
def two_tone_fit(t,y,f0):
    # Frequency estimates use real ISR times and a simultaneous two-tone model.
    tc=t-t.mean(); yn=y-y.mean(); norm=float(yn@yn)
    def design(freqs):
        cols=[np.ones(len(tc)),tc]
        for f in freqs: cols += [np.sin(2*np.pi*f*tc),np.cos(2*np.pi*f*tc)]
        return np.column_stack(cols)
    def solve(freqs):
        a=design(freqs); beta=np.linalg.lstsq(a,yn,rcond=None)[0]
        residual=yn-a@beta
        return float(residual@residual/norm),beta,residual
    fs=(len(t)-1)/(t[-1]-t[0])
    ff,pp=signal.periodogram(yn,fs=fs,window='hann',nfft=2**19)
    initial=[]
    for target in [f0,f0+1]:
        idx=np.where((ff>=target-.20)&(ff<=target+.20))[0]
        initial.append(float(ff[idx[np.argmax(pp[idx])]]))
    fit=optimize.minimize(lambda ff:solve(ff)[0],initial,method='L-BFGS-B',
         bounds=[(f0-.20,f0+.20),(f0+.80,f0+1.20)],options={'ftol':1e-13,'gtol':1e-8,'maxiter':80})
    error,beta,residual=solve(fit.x)
    amplitudes=[float(np.hypot(beta[2+2*k],beta[3+2*k])/np.sqrt(2)) for k in range(2)]
    return {'frequencias_hz':fit.x.tolist(),'amplitudes_rms_ms2':amplitudes,
            'r2':1-error,'residuo_rms_ms2':float(np.sqrt(np.mean(residual**2))),
            'sucesso_otimizador':bool(fit.success),'mensagem':str(fit.message)},beta

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--no',type=Path,required=True);p.add_argument('--profissional',type=Path,required=True)
    p.add_argument('--calibracao',type=Path,required=True);p.add_argument('--saida',type=Path,required=True)
    args=p.parse_args(); out=args.saida
    if out.exists() and any(out.iterdir()):
        out=out/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+uuid4().hex[:6])
    out.mkdir(parents=True,exist_ok=True)
    figs=out/'figuras';figs.mkdir(exist_ok=True)
    cal,cal_raw=read_calibration(args.calibracao)
    (out/'calibracao_aplicada.json').write_bytes(cal_raw)
    C=np.asarray(cal['matriz_correcao_g_lsb']);b=np.array([cal['offset_lsb'][a] for a in 'xyz'])
    result={'metodo':{'fs_profissional_hz':50000,'duracao_bloco_profissional_s':1,
       'fonte_tempo_profissional':'1 s por CSV informado pelo usuario; 50000 amostras por arquivo',
       'gravidade_padrao_ms2':G0,'eixo':'Y do conjunto','calibracao_sha256':digest(cal_raw),
       'pareamento':'por condicao nominal; simultaneidade nao estabelecida',
       'escala_profissional':'unidade original do CSV (u.o.); conversao para aceleracao desconhecida',
       'banda_principal':'[f_nominal - 2, f_nominal + 3] Hz',
       'psd_comum':'Hann periodica em blocos proximos a 1 s para comparacao visual; retangular para potencia de banda; media aritmetica; sem concatenar CSVs profissionais',
       'potencia_banda':'periodograma retangular em blocos proximos a 1 s; evita ponderar a envoltoria de batimentos pela Hann',
       'resolucao_profissional_hz':1,'janela_no':'10 <= t < 55 s',
       'versoes':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__}},
       'fontes':{'no_zip_sha256':digest(args.no.read_bytes()),'profissional_zip_sha256':digest(args.profissional.read_bytes()),
         'calibracao_zip_sha256':digest(args.calibracao.read_bytes())},'condicoes':{}}
    reference={}; professional_rows=[]; node_rows=[];psds={};signals={}; tone_rows=[]
    with ZipFile(args.profissional) as z:
        for f0,group in GROUPS.items():
            files=sorted(n for n in z.namelist() if n.endswith('.csv') and '/'+group+'/' in n)
            data=[]; spectra=[]
            tt=np.arange(50000)/50000;tc=tt-tt.mean()
            design=np.column_stack([np.ones(50000),tc,
                np.sin(2*np.pi*f0*tc),np.cos(2*np.pi*f0*tc),
                np.sin(2*np.pi*(f0+1)*tc),np.cos(2*np.pi*(f0+1)*tc),
                np.sin(2*np.pi*60*tc),np.cos(2*np.pi*60*tc)])
            inverse=np.linalg.pinv(design)
            for i,name in enumerate(files):
                raw=z.read(name);x=np.fromstring(raw.decode('utf-8-sig').strip(),sep=';')
                if len(x)!=50000 or not np.all(np.isfinite(x)):raise ValueError(name)
                f,P=bin_psd(x,50000);_,Pvisual=bin_psd(x,50000,'hann');low,high=f0-2,f0+3
                k=np.where((f>=f0-.25)&(f<=f0+1.25))[0]
                peak=float(f[k[np.argmax(P[k])]])
                coeff=inverse@x
                a1=float(np.hypot(coeff[2],coeff[3])/np.sqrt(2));a2=float(np.hypot(coeff[4],coeff[5])/np.sqrt(2))
                row={'f_nominal_hz':f0,'arquivo':name,'indice_bloco':i+1,'amostras':len(x),
                  'fs_hz':50000,'media_uo':float(x.mean()),'rms_total_uo':float(np.sqrt(np.mean(x*x))),
                  'rms_sem_media_uo':float(np.std(x)),'rms_banda_uo':band_rms(f,P,low,high),
                  'pico_local_hz':peak,'rms_banda_60hz_uo':band_rms(f,P,58,62),
                  'rms_componente_f0_uo':a1,'rms_componente_f0_mais1_uo':a2,
                  'razao_componentes_mais1_por_f0':a2/a1,'sha256':digest(raw)}
                professional_rows.append(row);data.append(row);spectra.append(Pvisual)
            meanpsd=np.mean(spectra,axis=0)
            k=np.where((f>=f0-.25)&(f<=f0+1.25))[0];peak=float(f[k[np.argmax(meanpsd[k])]])
            reference[f0]={'n_blocos':len(data),'duracao_total_armazenada_s':len(data),
                'arquivos_primeiro_ultimo':[files[0],files[-1]],'pico_psd_media_hz':peak,
                'rms_banda_agregado_uo':float(np.sqrt(np.mean([r['rms_banda_uo']**2 for r in data]))),
                'rms_banda_blocos':summary([r['rms_banda_uo'] for r in data]),
                'rms_sem_media_blocos':summary([r['rms_sem_media_uo'] for r in data]),
                'media_blocos':summary([r['media_uo'] for r in data]),
                'rms_banda60_agregado_uo':float(np.sqrt(np.mean([r['rms_banda_60hz_uo']**2 for r in data])))}
            reference[f0]['rms_componente_f0_agregado_uo']=float(np.sqrt(np.mean([r['rms_componente_f0_uo']**2 for r in data])))
            reference[f0]['rms_componente_f0_mais1_agregado_uo']=float(np.sqrt(np.mean([r['rms_componente_f0_mais1_uo']**2 for r in data])))
            reference[f0]['razao_componentes_agregadas']=reference[f0]['rms_componente_f0_mais1_agregado_uo']/reference[f0]['rms_componente_f0_agregado_uo']
            reference[f0]['razao_componentes_blocos']=summary([r['razao_componentes_mais1_por_f0'] for r in data])
            psds[('prof',f0)]=(f,meanpsd)
    with ZipFile(args.no) as z:
        for f0 in GROUPS:
            name=next(n for n in z.namelist() if n.endswith('/aquisicao.csv') and n.split('/')[-2].endswith(f'_{f0}Hz'))
            folder=name.rsplit('/',1)[0];raw=z.read(name)
            a=np.genfromtxt(io.StringIO(raw.decode('utf-8-sig')),delimiter=',',names=True)
            meta=json.loads(z.read(folder+'/meta.json'));aq=json.loads(z.read(folder+'/aquisicao.json'))
            if meta['sensor']!=cal['identificacao_sensor'] or meta['montagem']!=cal['montagem']:raise ValueError('Calibracao incompativel')
            for key in ['faixa_g','fs_nominal_hz','lpf_hz','hpf']:
                if meta['configuracao'][key]!=cal['configuracao_calibracao'][key]:raise ValueError('Configuracao diferente: '+key)
            t=a['t_us']/1e6;dt=np.diff(t);fs=(len(t)-1)/(t[-1]-t[0])
            raw_xyz=np.column_stack([a[f'a{k}_raw'] for k in 'xyz'])
            xyz=((raw_xyz-b)@C.T)*G0
            select=(t>=10)&(t<55); ts=t[select];ys=xyz[select]
            twotone,beta=two_tone_fit(ts,ys[:,1],f0)
            # Power spectral summaries near a 1-s observation length for fair resolution.
            per=round(fs);fw,Pw=signal.welch(ys[:,1],fs=fs,window='hann',nperseg=per,noverlap=0,detrend='constant',scaling='density')
            ff,Pf=signal.periodogram(ys[:,1],fs=fs,window='hann',detrend='constant',scaling='density',nfft=2**19)
            low,high=f0-2,f0+3
            band_axes=[]
            for j in range(3):
                fax,pax=signal.welch(ys[:,j],fs=fs,window='boxcar',nperseg=per,noverlap=0,detrend='constant',scaling='density')
                band_axes.append(band_rms(fax,pax,low,high))
            by=band_axes[1]
            blockrows=[]
            for sec in range(10,55):
                sel=(t>=sec)&(t<sec+1)
                fblock,pblock=bin_psd(xyz[sel,1],fs)
                yy=xyz[sel,1];nrow={'f_nominal_hz':f0,'segundo_inicio':sec,'amostras':len(yy),
                   'media_y_ms2':float(yy.mean()),'rms_y_sem_media_ms2':float(np.std(yy)),
                   'rms_y_banda_ms2':band_rms(fblock,pblock,low,high)}
                node_rows.append(nrow);blockrows.append(nrow)
            k=1 if twotone['amplitudes_rms_ms2'][1]>twotone['amplitudes_rms_ms2'][0] else 0
            for j in range(2):tone_rows.append({'f_nominal_hz':f0,'componente':j+1,
               'f_no_hz':twotone['frequencias_hz'][j],'rms_no_ms2':twotone['amplitudes_rms_ms2'][j]})
            # Header hashes provide independent verification of transport without recoding raw.
            checks={'csv':digest(raw)==aq.get('csv_sha256'),
                    'raw':digest(z.read(folder+'/raw.bin'))==aq.get('binario_sha256'),
                    'meta':digest(z.read(folder+'/meta.json'))==aq.get('metadados_sd_sha256')}
            node={'arquivo':name,'run_id':meta['run_id'],'fs_efetiva_hz':float(fs),
               'desvio_fs_nominal_pct':float(100*(fs/500-1)),'n':len(t),'tempo_entre_primeira_ultima_s':float(t[-1]-t[0]),
               'dt_mediano_us':float(np.median(dt)*1e6),'dt_min_us':float(dt.min()*1e6),'dt_max_us':float(dt.max()*1e6),
               'dt_dp_us':float(np.std(dt)*1e6),'indices_contiguos':bool(np.all(np.diff(a['indice'])==1)),
               'timestamps_crescentes':bool(np.all(dt>0)),'limite_inferior_perdas':int(a['perdidas_acum'].max()),
               'erros_spi':int(a['erros_spi'].max()),'descartes_fila':int(a['descartes_fila'].max()),
               'leituras_descartadas':int(a['leituras_descartadas'].max()),'saturacao_20bits':bool(np.any(abs(raw_xyz)>=.98*524288)),
               'captura_completa':bool(meta['captura_completa']),'transferencia_hashes':checks,
               'calibracao_id_meta':meta['calibracao_id'],'calibracao_status_json':cal['status'],
               'calibracao_aplicada':args.calibracao.name,
               'media_xyz_ms2':ys.mean(axis=0).tolist(),'rms_xyz_sem_media_ms2':np.std(ys,axis=0).tolist(),
               'rms_xyz_banda_ms2':band_axes,'participacao_y_potencia_banda_pct':float(100*by**2/np.sum(np.square(band_axes))),
               'razao_x_y_banda_pct':float(100*band_axes[0]/by),'razao_z_y_banda_pct':float(100*band_axes[2]/by),
               'rms_y_blocos':summary([r['rms_y_banda_ms2'] for r in blockrows]),'ajuste_duas_componentes':twotone,
               'razao_componentes_ajuste':twotone['amplitudes_rms_ms2'][1]/twotone['amplitudes_rms_ms2'][0],
               'pico_principal_ajuste_hz':twotone['frequencias_hz'][k],
               'rms_componente_principal_ms2':twotone['amplitudes_rms_ms2'][k],
               'saturacao_raw_min':raw_xyz.min(axis=0).tolist(),'saturacao_raw_max':raw_xyz.max(axis=0).tolist(),
               'metadados':meta}
            ref=reference[f0]
            result['condicoes'][str(f0)]={'no':node,'profissional':ref,
                'diferenca_pico_hz':float(node['pico_principal_ajuste_hz']-ref['pico_psd_media_hz']),
                'razao_rms_ms2_por_uo_descritiva':float(by/ref['rms_banda_agregado_uo']),
                'banda_hz':[low,high]}
            psds[('no',f0)]=(fw,Pw);psds[('no_fino',f0)]=(ff,Pf)
            signals[f0]=(t,xyz,folder)
    ref_ratio=result['condicoes']['25']['razao_rms_ms2_por_uo_descritiva']
    compare=[]
    for key,c in result['condicoes'].items():
        c['razao_normalizada_25hz_condicional']=c['razao_rms_ms2_por_uo_descritiva']/ref_ratio
        n=c['no'];r=c['profissional'];f0=int(key)
        compare.append({'f_nominal_hz':f0,'n_blocos_prof_1s':r['n_blocos'],'duracao_no_s':n['tempo_entre_primeira_ultima_s'],
          'fs_no_hz':n['fs_efetiva_hz'],'pico_prof_grade_1hz':r['pico_psd_media_hz'],'pico_no_hz':n['pico_principal_ajuste_hz'],
          'diferenca_picos_hz':c['diferenca_pico_hz'],'rms_y_no_banda_ms2':n['rms_xyz_banda_ms2'][1],
          'rms_prof_banda_uo':r['rms_banda_agregado_uo'],'razao_ms2_por_uo_descritiva':c['razao_rms_ms2_por_uo_descritiva'],
          'razao_normalizada_25hz_condicional':c['razao_normalizada_25hz_condicional'],
          'participacao_y_banda_pct':n['participacao_y_potencia_banda_pct'],
          'razao_componentes_no':n['razao_componentes_ajuste'],
          'razao_componentes_prof':r['razao_componentes_agregadas'],
          'cv_rms_no_blocos_pct':100*n['rms_y_blocos']['dp']/n['rms_y_blocos']['media'],
          'cv_rms_prof_blocos_pct':100*r['rms_banda_blocos']['dp']/r['rms_banda_blocos']['media']})
    table(out/'comparacao_condicoes.csv',compare);table(out/'blocos_profissionais.csv',professional_rows)
    table(out/'blocos_no.csv',node_rows);table(out/'componentes_no.csv',tone_rows)
    (out/'resultados_completos.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,default=serial),encoding='utf-8')
    # Figures use independent amplitude normalization only for the spectral shape.
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(2,2,figsize=(8.6,6),layout='constrained')
    for ax,f0 in zip(axs.ravel(),GROUPS):
        for who,label,color in [('prof','Profissional','#a95627'),('no','ADXL355 sem fio','#205f8a')]:
            f,P=psds[(who,f0)]; sel=(f>=f0-5)&(f<=f0+6);norm=np.max(P[(f>=f0-1)&(f<=f0+2)])
            ax.plot(f[sel],10*np.log10(np.maximum(P[sel]/norm,1e-12)),'.-',label=label,color=color,lw=1.3,ms=4)
        ax.axvline(f0,color='gray',ls=':',lw=.8);ax.axvline(f0+1,color='gray',ls=':',lw=.8)
        ax.set(xlabel='Frequência (Hz)',ylabel='PSD normalizada (dB)',title=f'Condição nominal: {f0} Hz',ylim=(-45,3));ax.grid(alpha=.2)
    axs[0,0].legend(fontsize=10);fig.savefig(figs/'01_espectros_resolucao_comparavel.png',dpi=220);fig.savefig(figs/'01_espectros_resolucao_comparavel.svg');plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(8.6,6),layout='constrained')
    for ax,f0 in zip(axs.ravel(),GROUPS):
        f,P=psds[('no_fino',f0)];sel=(f>=f0-1)&(f<=f0+2)
        ax.plot(f[sel],P[sel],color='#205f8a');ax.set(xlabel='Frequência (Hz)',ylabel='PSD [(m/s²)²/Hz]',title=f'ADXL355: condição {f0} Hz');ax.grid(alpha=.2)
    fig.savefig(figs/'02_duas_componentes_no.png',dpi=220);fig.savefig(figs/'02_duas_componentes_no.svg');plt.close(fig)
    fig,axs=plt.subplots(4,2,figsize=(9,10),layout='constrained')
    for i,f0 in enumerate(GROUPS):
        rr=[r for r in professional_rows if r['f_nominal_hz']==f0];nn=[r for r in node_rows if r['f_nominal_hz']==f0]
        axs[i,0].plot([r['indice_bloco'] for r in rr],[r['rms_banda_uo'] for r in rr],'.-',color='#a95627')
        axs[i,0].set(xlabel='Bloco profissional (1 s)',ylabel='RMS na banda (u.o.)',title=f'Profissional: {f0} Hz')
        axs[i,1].plot([r['segundo_inicio'] for r in nn],[r['rms_y_banda_ms2'] for r in nn],'.-',color='#205f8a')
        axs[i,1].set(xlabel='Tempo do nó (s)',ylabel='RMS na banda (m/s²)',title=f'ADXL355: {f0} Hz')
        for ax in axs[i]:ax.grid(alpha=.2)
    fig.savefig(figs/'03_estabilidade_amplitude_sem_sincronismo.png',dpi=200);plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(8.6,6),layout='constrained')
    for ax,f0 in zip(axs.ravel(),GROUPS):
        t,xyz,_=signals[f0]; sel=(t>=20)&(t<22)
        ax.plot(t[sel]-20,xyz[sel,1]-np.mean(xyz[sel,1]),color='#205f8a',lw=.8)
        ax.set(xlabel='Tempo relativo do nó (s)',ylabel='Y sem média (m/s²)',title=f'Condição nominal: {f0} Hz');ax.grid(alpha=.2)
    fig.savefig(figs/'04_sinais_no_dois_segundos.png',dpi=220);plt.close(fig)
    print(json.dumps(compare,indent=2,ensure_ascii=False))
    print('RESULTADOS:',out.resolve())

if __name__=='__main__':main()

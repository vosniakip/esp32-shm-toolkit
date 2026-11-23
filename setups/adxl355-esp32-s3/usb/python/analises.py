"""Analisadores do ADXL355; wrappers numerados mantem a interface de uso."""
from __future__ import annotations
import argparse,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import butter,sosfiltfilt,welch
from comum import (EIXOS,G0,carregar_json,salvar_json,localizar,ler,converter,tempo,diagnostico,exigir_continuidade,integrar_psd,tabela,iniciar_saida,finalizar_saida,plot_setup)
from calibracao_completa import calibrar_completa,validar_completa
def argumentos(tipo):
    p=argparse.ArgumentParser(description=f'ADXL355/S3 — {tipo}; pasta exclusiva por execucao.')
    p.add_argument('entradas',nargs='+',help='CSV(s) ou pasta(s) de capturas com seus JSON.')
    p.add_argument('--saida',default='dados/calibracao' if tipo=='calibracao' else f'dados/processados/{tipo}')
    if tipo!='resumo':
        p.add_argument('--descartar',type=float,default=0 if tipo in ('tempo','termica','allan','dinamico','exportar') else 2)
        p.add_argument('--calibracao')
        p.add_argument('--confirmar-montagem',help='Para reprocessar brutos antigos sem este metadado; informe o mesmo identificador da calibracao somente se a montagem for a mesma.')
    if tipo=='calibracao':
        p.add_argument('--sensor'); p.add_argument('--gravidade-local',type=float,default=G0,help='m/s2')
        p.add_argument('--modelo',choices=['matriz','diagonal'],default='matriz',help='Matriz completa por padrao; diagonal preserva o metodo antigo.')
    if tipo in ('calibracao','validacao'):
        default_refs=Path(__file__).resolve().parents[1]/'fichas'/('orientacoes_calibracao.json' if tipo=='calibracao' else 'orientacoes_validacao.json')
        p.add_argument('--referencias',default=str(default_refs),help='JSON com direcoes conhecidas no referencial do conjunto.')
        p.add_argument('--min-repeticoes',type=int,default=3 if tipo=='calibracao' else 1)
        p.add_argument('--max-dp-mg',type=float,default=5,help='Triagem de movimento/dispersao; nao e tolerancia do componente.')
        p.add_argument('--limite-vetorial-mg',type=float,default=10)
        p.add_argument('--limite-norma-pct',type=float,default=1)
        p.add_argument('--limite-angular-deg',type=float,default=.5)
    if tipo in ('ruido','dinamico'):
        p.add_argument('--fmin',type=float,default=.5); p.add_argument('--fmax',type=float,default=50); p.add_argument('--nperseg',type=int,default=8192)
    if tipo=='ruido':
        p.add_argument('--densidade-fmin',type=float,default=10); p.add_argument('--densidade-fmax',type=float,default=40)
    if tipo=='dinamico':
        p.add_argument('--eixo',choices=['auto','x','y','z'],default='auto'); p.add_argument('--ordem',type=int,default=4)
        p.add_argument('--borda',type=float,default=2); p.add_argument('--freq-referencia',type=float)
    if tipo=='termica': p.add_argument('--janela',type=float,default=60)
    if tipo=='allan': p.add_argument('--pontos',type=int,default=60); p.add_argument('--eixos',default='xyz')
    return p.parse_args()
def rotulo(p,i): return f'{i:02d}_{p.parent.name}_{p.stem}'[:110]
def medias(d):
    r={}
    for e in EIXOS:
        v=d[f'a{e}_g'].to_numpy(); r.update({f'media_a{e}_g':v.mean(),f'dp_a{e}_g':v.std(ddof=1),f'rms_centralizado_a{e}_g':np.sqrt(np.mean((v-v.mean())**2))})
    return r
def conferir_repeticoes(files):
    keys=set()
    for p in files:
        m=carregar_json(p.with_suffix('.json')); c=m['configuracao']
        keys.add((m['sensor'],str(m.get('posicao','')).lower(),int(c['faixa_g']),float(c['fs_nominal_hz']),float(c['lpf_hz']),str(c['hpf'])))
    if len(keys)!=1: raise ValueError('Separe repeticoes por exemplar, posicao, faixa, taxa e filtro.')
def funcional(args,files,out):
    plt=plot_setup(); rows=[]
    for i,p in enumerate(files,1):
        d=converter(ler(p,args.descartar),args.calibracao,args.confirmar_montagem); q=diagnostico(d); norm=np.linalg.norm(d[[f'a{e}_g' for e in EIXOS]],axis=1)
        rows.append(dict(arquivo=str(p),**medias(d),norma_media_g=norm.mean(),norma_dp_g=norm.std(ddof=1),temperatura_media_c=d.temp_c.mean(),desvio_norma_1g_pct=(norm.mean()-1)*100,**q))
        fig,ax=plt.subplots(figsize=(10,4))
        for e in EIXOS: ax.plot(tempo(d),d[f'a{e}_g'],label=e.upper(),lw=.7)
        ax.set(xlabel='Tempo (s)',ylabel='Aceleração (g)',title='Verificação funcional — gravidade preservada'); ax.legend(); fig.tight_layout(); fig.savefig(out/f'{rotulo(p,i)}_sinal.png'); plt.close(fig)
        print(f'{p}: norma={norm.mean():.6f} g; fs={q["fs_efetiva_hz"]:.3f} Hz')
        if abs(norm.mean()-1)>.05: print('AVISO exploratorio: norma difere mais de 5% de 1 g; examine montagem, escala e calibracao.')
    tabela(pd.DataFrame(rows),out,'verificacao_funcional')
def calibrar(args,files,out):
    if args.modelo=='matriz': return calibrar_completa(args,files,out)
    if args.calibracao: raise ValueError('Seis posicoes usa dados brutos sem calibracao anterior.')
    if not 9<args.gravidade_local<10: raise ValueError('Gravidade deve ser informada em m/s2.')
    rows=[]; sensors=set(); ranges=set(); configs=set(); plt=plot_setup()
    for p in files:
        d=ler(p,args.descartar); exigir_continuidade(d); m=d.attrs['metadados']; c=m['configuracao']
        sensors.add(m['sensor']); ranges.add(int(c['faixa_g'])); configs.add((float(c['fs_nominal_hz']),float(c['lpf_hz']),str(c['hpf'])))
        pos=str(m.get('posicao','')).lower().replace('+','pos').replace('-','neg')
        if pos not in {e+s for e in EIXOS for s in ('pos','neg')}: raise ValueError(f'Posicao invalida: {p}')
        r=dict(arquivo=str(p),posicao=pos,n=len(d))
        for e in EIXOS: r[f'media_a{e}_raw']=d[f'a{e}_raw'].mean(); r[f'dp_a{e}_raw']=d[f'a{e}_raw'].std()
        r['temperatura_media_c']=25+(d.loc[d.temp_raw>=0,'temp_raw'].mean()-1885)/-9.05; rows.append(r)
    if len(sensors)!=1 or len(ranges)!=1 or len(configs)!=1: raise ValueError('Nao misture exemplares/faixas/filtros/taxas.')
    sensor=next(iter(sensors)); faixa=next(iter(ranges)); nominal=512000/faixa
    if args.sensor and args.sensor!=sensor: raise ValueError('--sensor difere das capturas.')
    df=pd.DataFrame(rows); groups=df.groupby('posicao'); missing={e+s for e in EIXOS for s in ('pos','neg')}-set(df.posicao)
    if missing: raise ValueError(f'Faltam posicoes: {sorted(missing)}')
    b={}; s={}; coefs=[]; gref=args.gravidade_local/G0
    for e in EIXOS:
        plus=groups.get_group(e+'pos')[f'media_a{e}_raw'].mean(); minus=groups.get_group(e+'neg')[f'media_a{e}_raw'].mean()
        b[e]=(plus+minus)/2; s[e]=(plus-minus)/(2*gref)
        if s[e]<=0: raise ValueError(f'Eixo {e}: posicoes invertidas ou dados invalidos.')
        if not .5*nominal<s[e]<1.5*nominal: raise ValueError(f'Eixo {e}: escala fora da faixa exploratoria 50–150%; confira orientacao/configuracao.')
        coefs.append(dict(eixo=e.upper(),offset_lsb=b[e],sensibilidade_lsb_g=s[e],offset_mg=b[e]/s[e]*1000,erro_escala_pct=(s[e]/nominal-1)*100))
    salvar_json(dict(formato='calibracao_adxl355_diagonal_v1',sensor_modelo='ADXL355',identificacao_sensor=sensor,faixa_g=faixa,offset_lsb=b,sensibilidade_lsb_g=s,sensibilidade_nominal_lsb_g=nominal,gravidade_referencia_ms2=args.gravidade_local,repeticoes_por_posicao=groups.size().to_dict(),arquivos=[str(p) for p in files],observacao='Ajuste diagonal; residuos nao sao validacao independente nem incerteza rastreavel.'),out/'calibracao.json')
    residual=[]
    for r in rows:
        v=np.array([(r[f'media_a{e}_raw']-b[e])/s[e] for e in EIXOS]); target=np.zeros(3); target[EIXOS.index(r['posicao'][0])]=gref*(1 if r['posicao'].endswith('pos') else -1)
        residual.append(dict(arquivo=r['arquivo'],posicao=r['posicao'],**{f'a{e}_corr_g':v[j] for j,e in enumerate(EIXOS)},norma_g=np.linalg.norm(v),erro_norma_pct=(np.linalg.norm(v)/gref-1)*100,erro_vetorial_g=np.linalg.norm(v-target)))
    tabela(df,out,'calibracao_medias_brutas'); tabela(pd.DataFrame(coefs),out,'calibracao_coeficientes'); tabela(pd.DataFrame(residual),out,'calibracao_residuos')
    rep=groups[[f'media_a{e}_raw' for e in EIXOS]].agg(['mean','std','min','max']); rep.columns=['_'.join(x) for x in rep.columns]; tabela(rep.reset_index(),out,'calibracao_repeticoes')
    fig,axes=plt.subplots(1,2,figsize=(10,4)); axes[0].bar(list(EIXOS),[b[e]/s[e]*1000 for e in EIXOS]); axes[0].set(ylabel='Offset (mg)')
    axes[1].bar(list(EIXOS),[s[e] for e in EIXOS]); axes[1].axhline(nominal,color='red',ls='--',label='Nominal'); axes[1].set(ylabel='Sensibilidade (LSB/g)'); axes[1].legend(); fig.tight_layout(); fig.savefig(out/'calibracao_parametros.png'); plt.close(fig)
    print(pd.DataFrame(coefs).to_string(index=False)); print('Calibracao:',out/'calibracao.json')
def espectro(v,fs,nperseg):
    n=min(nperseg,len(v))
    if n<32: raise ValueError('Welch requer ao menos 32 pontos por segmento.')
    return welch(v,fs=fs,window='hann',nperseg=n,noverlap=n//2,detrend='constant',scaling='density')
def ruido(args,files,out):
    conferir_repeticoes(files); plt=plot_setup(); rows=[]; fig,axes=plt.subplots(3,1,figsize=(10,9),sharex=True)
    for i,p in enumerate(files,1):
        d=converter(ler(p,args.descartar),args.calibracao,args.confirmar_montagem); fs=exigir_continuidade(d)
        if not 0<=args.fmin<args.fmax<fs/2: raise ValueError('Banda fora de Nyquist.')
        spectra=[]
        for j,e in enumerate(EIXOS):
            v=d[f'a{e}_g'].to_numpy(); f,psd=espectro(v,fs,args.nperseg)
            rms=integrar_psd(f,psd,args.fmin,args.fmax); density=integrar_psd(f,psd,args.densidade_fmin,args.densidade_fmax)/np.sqrt(args.densidade_fmax-args.densidade_fmin)*1e6
            rows.append(dict(arquivo=str(p),eixo=e.upper(),media_g=v.mean(),dp_g=v.std(ddof=1),rms_centralizado_g=np.sqrt(np.mean((v-v.mean())**2)),rms_banda_g=rms,densidade_equivalente_ug_raiz_hz=density,fs_hz=fs,fmin_hz=args.fmin,fmax_hz=args.fmax,densidade_fmin_hz=args.densidade_fmin,densidade_fmax_hz=args.densidade_fmax))
            spectra.append(pd.DataFrame(dict(eixo=e.upper(),frequencia_hz=f,psd_g2_hz=psd,asd_ug_raiz_hz=np.sqrt(psd)*1e6)))
            mask=(f>0)&(f<=max(args.fmax,args.densidade_fmax)*1.5); axes[j].semilogy(f[mask],np.sqrt(psd[mask])*1e6,lw=.8,label=f'R{i}'); axes[j].set(ylabel=f'{e.upper()}: ASD (µg/√Hz)')
        tabela(pd.concat(spectra,ignore_index=True),out,rotulo(p,i)+'_psd',excel=False)
    table=pd.DataFrame(rows); tabela(table,out,'metricas_ruido'); agg=table.groupby('eixo')[['rms_banda_g','densidade_equivalente_ug_raiz_hz']].agg(['mean','std']); agg.columns=['_'.join(x) for x in agg.columns]; tabela(agg.reset_index(),out,'ruido_repeticoes')
    for ax in axes: ax.axvspan(args.densidade_fmin,args.densidade_fmax,color='grey',alpha=.13); ax.legend()
    axes[-1].set(xlabel='Frequência (Hz)'); fig.suptitle('Ruído observado na montagem'); fig.tight_layout(); fig.savefig(out/'densidade_ruido.png'); plt.close(fig)
    print(agg.to_string()); print('A densidade inclui ambiente, montagem e eletronica; inspecione os picos.')
def temporizacao(args,files,out):
    plt=plot_setup(); rows=[]
    for i,p in enumerate(files,1):
        d=ler(p); rows.append(dict(arquivo=str(p),**diagnostico(d))); dt=np.diff(d.t_us.to_numpy())
        fig,axes=plt.subplots(1,2,figsize=(10,4)); axes[0].plot(tempo(d)[1:],dt,lw=.6); axes[0].set(xlabel='Tempo (s)',ylabel='Δt (µs)'); axes[1].hist(dt,bins=50); axes[1].set(xlabel='Δt (µs)',ylabel='Contagem'); fig.tight_layout(); fig.savefig(out/f'{rotulo(p,i)}_temporizacao.png'); plt.close(fig)
    tabela(pd.DataFrame(rows),out,'temporizacao'); print(pd.DataFrame(rows).to_string(index=False))
def repetibilidade(args,files,out):
    if len(files)<2: raise ValueError('Use ao menos duas capturas, preferencialmente cinco.')
    conferir_repeticoes(files); rows=[]
    for p in files:
        d=converter(ler(p,args.descartar),args.calibracao,args.confirmar_montagem); exigir_continuidade(d); rows.append(dict(arquivo=str(p),**medias(d)))
    df=pd.DataFrame(rows); tabela(df,out,'repetibilidade_por_arquivo'); summary=[]
    for e in EIXOS:
        m=df[f'media_a{e}_g']; r=df[f'rms_centralizado_a{e}_g']; summary.append(dict(eixo=e.upper(),repeticoes=len(df),media_das_medias_g=m.mean(),dp_entre_medias_g=m.std(),amplitude_entre_medias_g=m.max()-m.min(),rms_medio_g=r.mean(),rms_dp_g=r.std(),rms_cv_pct=r.std()/r.mean()*100 if r.mean()>0 else None))
    tabela(pd.DataFrame(summary),out,'repetibilidade_resumo'); print(pd.DataFrame(summary).to_string(index=False))
def termica(args,files,out):
    if args.janela<=0: raise ValueError('Janela deve ser positiva.')
    plt=plot_setup()
    for i,p in enumerate(files,1):
        d=converter(ler(p,args.descartar),args.calibracao,args.confirmar_montagem); exigir_continuidade(d); t=tempo(d); groups=(t//args.janela).astype(int); rows=[]
        for group in np.unique(groups):
            sel=groups==group; b=d.loc[sel]
            if len(b)>=2: rows.append(dict(tempo_s=t[sel].mean(),n=len(b),temperatura_c=b.temp_c.mean(),**medias(b)))
        if not rows: raise ValueError('Janelas sem amostras suficientes.')
        df=pd.DataFrame(rows); regress=[]
        for e in EIXOS:
            df[f'deriva_a{e}_mg']=(df[f'media_a{e}_g']-df[f'media_a{e}_g'].iloc[0])*1000
            valid=df.temperatura_c.notna(); tmp=df.loc[valid,'temperatura_c'].to_numpy(); acc=df.loc[valid,f'media_a{e}_g'].to_numpy(); slope=np.polyfit(tmp,acc,1)[0]*1000 if len(tmp)>=3 and np.ptp(tmp)>=.2 else None
            regress.append(dict(eixo=e,coeficiente_exploratorio_mg_C=slope))
        tabela(df,out,rotulo(p,i)+'_termica'); salvar_json(dict(regressao=regress,nota='Tempo e temperatura confundidos. Nao aplicar compensacao automatica.'),out/(rotulo(p,i)+'_correlacao.json'))
        fig,axes=plt.subplots(3,1,figsize=(10,9))
        for e in EIXOS: axes[0].plot(df.tempo_s/60,df[f'deriva_a{e}_mg'],label=e.upper()); axes[2].plot(df.temperatura_c,df[f'media_a{e}_g'],'.-',label=e.upper())
        axes[0].set(xlabel='Tempo (min)',ylabel='Deriva (mg)'); axes[0].legend(); axes[1].plot(df.tempo_s/60,df.temperatura_c); axes[1].set(xlabel='Tempo (min)',ylabel='Temperatura interna (°C)'); axes[2].set(xlabel='Temperatura interna (°C)',ylabel='Aceleração média (g)'); axes[2].legend(); fig.tight_layout(); fig.savefig(out/f'{rotulo(p,i)}_termica.png'); plt.close(fig)
def dinamico(args,files,out):
    if not 1<=args.ordem<=10 or args.borda<0: raise ValueError('Ordem/borda invalida.')
    if args.freq_referencia is not None and args.freq_referencia<=0: raise ValueError('Referencia deve ser positiva.')
    plt=plot_setup(); rows=[]; fig,axes=plt.subplots(2,1,figsize=(11,8))
    for i,p in enumerate(files,1):
        d=converter(ler(p,args.descartar),args.calibracao,args.confirmar_montagem); fs=exigir_continuidade(d)
        if not 0<args.fmin<args.fmax<fs/2: raise ValueError('Banda fora de Nyquist.')
        sos=butter(args.ordem,[args.fmin,args.fmax],fs=fs,btype='bandpass',output='sos'); t=tempo(d); keep=(t>=args.borda)&(t<=t[-1]-args.borda)
        if keep.sum()<max(32,4*fs/args.fmin): raise ValueError('Registro curto: minimo de quatro ciclos de fmin apos retirar bordas.')
        sig={e:sosfiltfilt(sos,d[f'a{e}_g'].to_numpy()) for e in EIXOS}; eixo=max(EIXOS,key=lambda e:np.mean(sig[e][keep]**2)) if args.eixo=='auto' else args.eixo
        v=sig[eixo][keep]; f,psd=espectro(v,fs,args.nperseg); band=(f>=args.fmin)&(f<=args.fmax); freq=float(f[band][np.argmax(psd[band])])
        rows.append(dict(arquivo=str(p),eixo=eixo.upper(),fs_hz=fs,frequencia_dominante_hz=freq,resolucao_espectral_hz=f[1]-f[0],rms_filtrado_g=np.sqrt(np.mean(v*v)),pico_filtrado_g=np.max(np.abs(v)),perto_limite_digital=diagnostico(d)['perto_limite_digital'],borda_descartada_s=args.borda,erro_frequencia_pct=(freq/args.freq_referencia-1)*100 if args.freq_referencia else None))
        tabela(pd.DataFrame(dict(tempo_s=t,**{f'a{e}_filtrada_g':sig[e] for e in EIXOS},usado_metricas=keep)),out,rotulo(p,i)+'_sinal_filtrado',excel=False); tabela(pd.DataFrame(dict(frequencia_hz=f,psd_g2_hz=psd)),out,rotulo(p,i)+'_psd',excel=False)
        axes[0].plot(t[keep],v,lw=.7,label=f'R{i} {eixo.upper()}'); axes[1].semilogy(f[band],np.sqrt(psd[band]),label=f'R{i}: {freq:.3f} Hz')
    df=pd.DataFrame(rows); tabela(df,out,'metricas_dinamicas'); vals=df.frequencia_dominante_hz
    tabela(pd.DataFrame([dict(repeticoes=len(df),frequencia_media_hz=vals.mean(),frequencia_dp_hz=vals.std() if len(df)>1 else None,frequencia_cv_pct=vals.std()/vals.mean()*100 if len(df)>1 else None)]),out,'resumo_dinamico')
    axes[0].set(xlabel='Tempo (s)',ylabel='Aceleração filtrada (g)'); axes[1].set(xlabel='Frequência (Hz)',ylabel='ASD (g/√Hz)')
    for ax in axes: ax.legend()
    fig.tight_layout(); fig.savefig(out/'dinamico.png'); plt.close(fig); print(df.to_string(index=False))
def allan_sobreposto(v,fs,pontos=60):
    v=np.asarray(v,dtype=float); v=v-v.mean(); n=len(v); max_m=n//10
    if max_m<2 or pontos<2: raise ValueError('Registro/pontos insuficientes.')
    cs=np.r_[0.,np.cumsum(v)]; rows=[]
    for m in np.unique(np.geomspace(1,max_m,pontos).astype(int)):
        diff=(cs[2*m:]-2*cs[m:-m]+cs[:-2*m])/m; rows.append((m/fs,np.sqrt(.5*np.mean(diff**2)),len(diff),n//m))
    return np.asarray(rows)
def allan(args,files,out):
    eixos=[e for e in EIXOS if e in args.eixos.lower()]
    if not eixos: raise ValueError('Selecione x, y e/ou z.')
    plt=plot_setup()
    for i,p in enumerate(files,1):
        d=converter(ler(p,args.descartar),args.calibracao,args.confirmar_montagem); fs=exigir_continuidade(d); rows=[]; summary=[]; fig,ax=plt.subplots(figsize=(9,6))
        for e in eixos:
            a=allan_sobreposto(d[f'a{e}_g'],fs,args.pontos); rows.append(pd.DataFrame(dict(eixo=e.upper(),tau_s=a[:,0],desvio_allan_g=a[:,1],pares_sobrepostos=a[:,2].astype(int),blocos_nao_sobrepostos=a[:,3].astype(int))))
            k=np.argmin(a[:,1]); summary.append(dict(eixo=e.upper(),minimo_g=a[k,1],tau_minimo_s=a[k,0])); ax.loglog(a[:,0],a[:,1],label=e.upper())
        tabela(pd.concat(rows,ignore_index=True),out,rotulo(p,i)+'_allan'); salvar_json(dict(resumo=summary,nota='Minimo descritivo; nao e automaticamente bias instability. Pares sobrepostos nao sao independentes.'),out/(rotulo(p,i)+'_allan_resumo.json'))
        ax.set(xlabel='Tempo de integração τ (s)',ylabel='Desvio de Allan (g)',title='Allan sobreposto — sem passa-altas'); ax.legend(); fig.tight_layout(); fig.savefig(out/f'{rotulo(p,i)}_allan.png'); plt.close(fig)
def exportar(args,files,out):
    for i,p in enumerate(files,1):
        d=converter(ler(p,args.descartar),args.calibracao,args.confirmar_montagem)
        d['tempo_s']=tempo(d); d['norma_g']=np.linalg.norm(d[[f'a{e}_g' for e in EIXOS]],axis=1)
        tabela(d,out,rotulo(p,i)+'_corrigido',excel=False)
        salvar_json(dict(arquivo_bruto=str(p),referencial=d.attrs['calibracao_aplicada'],diagnostico=diagnostico(d)),out/(rotulo(p,i)+'_corrigido.json'))
    print('CSV corrigido exportado; os brutos originais foram preservados.')
def resumo(args):
    files=[]
    for s in args.entradas:
        p=Path(s)
        if p.is_dir(): files.extend(p.rglob('analise.json'))
        elif p.is_file() and p.name=='analise.json': files.append(p)
        else: raise ValueError('Use pastas de resultados ou analise.json.')
    files=sorted(set(files))
    if not files: raise ValueError('Nenhuma analise encontrada.')
    out=iniciar_saida(args,'resumo',files); rows=[]
    for p in files:
        j=carregar_json(p); rows.append(dict(tipo=j.get('tipo'),status=j.get('status'),criado_em=j.get('criado_em'),pasta=str(p.parent.resolve()),entradas=len(j.get('entradas',[]))))
    tabela(pd.DataFrame(rows),out,'indice_resultados'); finalizar_saida(out); print('Indice:',out.resolve())
def executar(tipo):
    out=None
    try:
        args=argumentos(tipo)
        if tipo=='resumo': resumo(args); return
        files=localizar(args.entradas); out=iniciar_saida(args,tipo,files)
        if args.calibracao:
            cal=carregar_json(args.calibracao)
            print('Referencial de saida:',cal.get('referencial_saida',dict(nome='sensor')).get('nome'))
            if cal.get('status')=='ajustada_nao_validada': print('AVISO: coeficientes ajustados; consulte o relatorio independente de 11_validar_calibracao.py antes de concluir sobre sua qualidade.')
        dict(funcional=funcional,calibracao=calibrar,validacao=validar_completa,exportar=exportar,ruido=ruido,tempo=temporizacao,repetibilidade=repetibilidade,termica=termica,dinamico=dinamico,allan=allan)[tipo](args,files,out)
        finalizar_saida(out); print('Resultados:',out.resolve())
    except (ValueError,OSError,KeyError) as e:
        if out: finalizar_saida(out,str(e))
        print('ERRO: '+str(e),file=sys.stderr); raise SystemExit(2)

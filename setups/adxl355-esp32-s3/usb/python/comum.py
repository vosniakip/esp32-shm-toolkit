"""Validacao, unidades, rastreabilidade e saidas compartilhadas."""
from __future__ import annotations
import hashlib,json,math,re,sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import numpy as np
import pandas as pd
from modelos_calibracao import FORMATO_MATRIZ,aplicar_matriz,conferir_matriz
VERSAO_PACOTE='2.0.0'
FORMATO='ADXL355_S3_V1'; EIXOS='xyz'; G0=9.80665
COLUNAS=['indice','t_us','ax_raw','ay_raw','az_raw','temp_raw','perdidas_acum','descartes_fila','leituras_descartadas','erros_spi']
def nome_seguro(s): return re.sub(r'[^a-z0-9_-]+','_',str(s).lower()).strip('_') or 'sem_nome'
def limpar_json(x):
    if isinstance(x,dict): return {str(k):limpar_json(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)): return [limpar_json(v) for v in x]
    if isinstance(x,np.integer): return int(x)
    if isinstance(x,np.bool_): return bool(x)
    if isinstance(x,(float,np.floating)): return float(x) if math.isfinite(x) else None
    if isinstance(x,Path): return str(x)
    return x
def salvar_json(obj,p): Path(p).write_text(json.dumps(limpar_json(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def carregar_json(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha256(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def nova_pasta(raiz,identificador=''):
    raiz=Path(raiz); raiz.mkdir(parents=True,exist_ok=True)
    p=raiz/(datetime.now().astimezone().strftime('%Y%m%d_%H%M%S_%f')+'_'+nome_seguro(identificador)[:48]+'_'+uuid4().hex[:6])
    p.mkdir(exist_ok=False); return p
def localizar(entradas):
    files=[]
    for s in entradas:
        p=Path(s)
        if p.is_dir(): files.extend(p.rglob('*.csv'))
        elif p.is_file() and p.suffix.lower()=='.csv': files.append(p)
        else: raise ValueError(f'Entrada inexistente ou nao CSV: {p}')
    result=sorted({p.resolve() for p in files})
    if not result: raise ValueError('Nenhum CSV encontrado.')
    return result
def ler(p,descartar=0):
    p=Path(p)
    if not p.with_suffix('.json').exists(): raise ValueError(f'Falta o JSON ao lado de {p}. Copie CSV e JSON juntos.')
    meta=carregar_json(p.with_suffix('.json'))
    if meta.get('formato')!=FORMATO: raise ValueError('Formato de outro sensor/pacote.')
    if meta.get('csv_sha256') and sha256(p)!=meta['csv_sha256']: raise ValueError('CSV alterado desde a captura. Use o original, sem salvar pelo Excel.')
    info=meta.get('configuracao',{}); faixa=int(info.get('faixa_g',0)); sens=float(info.get('sensibilidade_lsb_g',0))
    if faixa not in (2,4,8) or sens!=512000/faixa: raise ValueError('Faixa/sensibilidade nominal inconsistente.')
    if float(info.get('fs_nominal_hz',0))<=0: raise ValueError('Taxa nominal ausente/invalida.')
    d=pd.read_csv(p)
    if not set(COLUNAS).issubset(d.columns) or len(d)<2: raise ValueError('Colunas ausentes ou menos de duas amostras.')
    for c in COLUNAS:
        v=pd.to_numeric(d[c],errors='raise').to_numpy(dtype=float)
        if not np.all(np.isfinite(v)) or not np.all(v==np.floor(v)): raise ValueError(f'{c}: use inteiros finitos do CSV original.')
        d[c]=v.astype(np.int64)
    if (np.diff(d.t_us)<=0).any() or (np.diff(d.indice)<=0).any(): raise ValueError('Tempo/indice repetido ou decrescente.')
    if (d[COLUNAS[:2]+COLUNAS[6:]]<0).any().any(): raise ValueError('Contador/tempo negativo.')
    for c in COLUNAS[6:]:
        if (np.diff(d[c])<0).any(): raise ValueError(f'Contador {c} diminuiu.')
    a=d[['ax_raw','ay_raw','az_raw']].to_numpy()
    if (a < -524288).any() or (a>524287).any(): raise ValueError('Aceleracao fora dos 20 bits.')
    if ((d.temp_raw < -1)|(d.temp_raw>4095)).any(): raise ValueError('Temperatura bruta invalida.')
    if descartar<0: raise ValueError('Descarte negativo.')
    d=d.loc[(d.t_us-d.t_us.iloc[0])/1e6>=descartar].copy()
    if len(d)<2: raise ValueError('Descarte deixou menos de duas amostras.')
    d.attrs.update(caminho=str(p.resolve()),metadados=meta); return d
def converter(d,calibracao=None,montagem_confirmada=None):
    meta=d.attrs['metadados']; info=meta['configuracao']
    bruto=d[['ax_raw','ay_raw','az_raw']].to_numpy(dtype=float)
    contexto=dict(modelo='nominal',referencial='sensor',eixos='x/y/z do sensor',montagem=meta.get('montagem'))
    if calibracao:
        cal=carregar_json(calibracao)
        if cal.get('sensor_modelo')!='ADXL355' or int(cal.get('faixa_g',0))!=int(info['faixa_g']): raise ValueError('Calibracao de outro modelo/faixa.')
        if cal['identificacao_sensor']!=meta['sensor']: raise ValueError('Calibracao de outro exemplar.')
        b=np.array([cal['offset_lsb'][e] for e in EIXOS],dtype=float)
        if cal.get('formato')==FORMATO_MATRIZ:
            montagem=str(cal.get('montagem','')).strip()
            if not montagem: raise ValueError('Calibracao matricial sem identificacao da montagem.')
            registrada=str(meta.get('montagem','')).strip()
            if registrada and registrada!=montagem: raise ValueError('Calibracao de outra montagem; refaca a calibracao apos alterar a fixacao.')
            if not registrada and montagem_confirmada!=montagem:
                raise ValueError(f'Captura antiga sem montagem. Se a montagem for a mesma, use --confirmar-montagem "{montagem}".')
            if montagem_confirmada and montagem_confirmada!=montagem: raise ValueError('A montagem confirmada difere da calibracao.')
            cc=cal.get('configuracao_calibracao',{})
            for key in ('fs_nominal_hz','lpf_hz','hpf'):
                if key not in cc or key not in info or float(cc[key])!=float(info[key]):
                    raise ValueError(f'Configuracao {key} difere da calibracao matricial. Use a mesma configuracao ou recalibre.')
            c=conferir_matriz(cal['matriz_correcao_g_lsb'])
            corr=aplicar_matriz(bruto,c,b)
            ref=cal.get('referencial_saida',{})
            if ref.get('nome')!='conjunto' or cal.get('ordem_eixos')!=list(EIXOS): raise ValueError('Referencial/ordem de eixos desconhecido.')
            contexto.update(modelo='matriz_completa',referencial='conjunto',eixos=ref.get('descricao_eixos'),montagem=montagem,
                            montagem_confirmada_para_arquivo_legado=not bool(registrada))
        elif cal.get('formato') in (None,'calibracao_adxl355_diagonal_v1'):
            s=np.array([cal['sensibilidade_lsb_g'][e] for e in EIXOS],dtype=float)
            if not np.isfinite(s).all() or np.any(s<=0) or not np.isfinite(b).all(): raise ValueError('Coeficiente de calibracao invalido.')
            corr=(bruto-b)/s
            contexto.update(modelo='diagonal',referencial='sensor')
        else: raise ValueError('Formato de calibracao desconhecido.')
        contexto.update(arquivo=str(Path(calibracao).resolve()),sha256=sha256(calibracao),formato=cal.get('formato'))
    else: corr=bruto/float(info['sensibilidade_lsb_g'])
    for e in EIXOS:
        d[f'a{e}_g']=corr[:,EIXOS.index(e)]; d[f'a{e}_ms2']=d[f'a{e}_g']*G0
    d.attrs['calibracao_aplicada']=contexto
    d['temp_c']=np.where(d.temp_raw>=0,25+(d.temp_raw-1885)/-9.05,np.nan); return d
def tempo(d): return (d.t_us.to_numpy(dtype=float)-d.t_us.iloc[0])/1e6
def fs_efetiva(d): return (len(d)-1)/((d.t_us.iloc[-1]-d.t_us.iloc[0])/1e6)
def diagnostico(d):
    meta=d.attrs['metadados']; nominal=float(meta['configuracao']['fs_nominal_hz']); dt=np.diff(d.t_us.to_numpy(dtype=float)); end=meta.get('fim_firmware',{})
    return dict(n=len(d),fs_efetiva_hz=fs_efetiva(d),fs_nominal_hz=nominal,erro_fs_pct=100*(fs_efetiva(d)/nominal-1),
        dt_medio_us=np.mean(dt),dt_dp_us=np.std(dt,ddof=1) if len(dt)>1 else 0,dt_min_us=np.min(dt),dt_max_us=np.max(dt),jitter_dp_pct=np.std(dt)/np.mean(dt)*100,
        lacunas_indice=int(np.sum(np.diff(d.indice)-1)),lacunas_temporais=int(np.sum(dt>1.5*np.median(dt))),
        perdas_registradas=max(int(d.perdidas_acum.max()),int(end.get('perdidas',0))),erros_spi=max(int(d.erros_spi.max()),int(end.get('erros_spi',0))),
        transporte_invalido=int(meta.get('linhas_invalidas',0)),captura_completa=bool(meta.get('captura_completa',False)),
        perto_limite_digital=bool((np.abs(d[['ax_raw','ay_raw','az_raw']])>=.98*524287).any().any()))
def exigir_continuidade(d):
    q=diagnostico(d)
    if any(q[k] for k in ('lacunas_indice','lacunas_temporais','perdas_registradas','erros_spi','transporte_invalido')) or not q['captura_completa']:
        raise ValueError('Registro incompleto/com perdas. Execute 05_analisar_temporizacao.py. Nao sao interpoladas lacunas.')
    if q['jitter_dp_pct']>1 or abs(q['erro_fs_pct'])>1: print('AVISO: temporizacao fora da meta exploratoria de 1%; examine antes de interpretar o espectro.')
    return q['fs_efetiva_hz']
def integrar_psd(f,p,lo,hi):
    if not 0<=lo<hi<=f[-1]: raise ValueError('Banda de integracao fora do espectro.')
    m=(f>lo)&(f<hi); fi=np.r_[lo,f[m],hi]; pi=np.r_[np.interp(lo,f,p),p[m],np.interp(hi,f,p)]
    return float(np.sqrt(max(np.trapezoid(pi,fi),0)))
def tabela(d,p,nome,excel=True):
    d.to_csv(Path(p)/(nome+'.csv'),index=False,float_format='%.12g')
    if excel and len(d)<=1048575: d.to_excel(Path(p)/(nome+'.xlsx'),index=False)
def iniciar_saida(args,tipo,files):
    p=nova_pasta(args.saida,tipo)
    j=dict(tipo=tipo,status='em_execucao',versao_pacote=VERSAO_PACOTE,criado_em=datetime.now().astimezone().isoformat(),parametros=vars(args),entradas=[dict(arquivo=str(a),sha256=sha256(a)) for a in files],python=sys.version)
    for attr in ('calibracao','referencias'):
        value=getattr(args,attr,None)
        if value:
            j[attr+'_fonte']=dict(arquivo=str(Path(value).resolve()),sha256=sha256(value))
    if getattr(args,'calibracao',None):
        cal=carregar_json(args.calibracao)
        j['referencial_saida']=cal.get('referencial_saida',dict(nome='sensor'))
        j['montagem_calibracao']=cal.get('montagem')
    else: j['referencial_saida']=dict(nome='sensor')
    salvar_json(j,p/'analise.json'); return p
def finalizar_saida(p,erro=None):
    path=Path(p)/'analise.json'; j=carregar_json(path); j.update(status='falhou' if erro else 'concluida',erro=erro,concluido_em=datetime.now().astimezone().isoformat()); salvar_json(j,path)
def plot_setup():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'figure.dpi':130,'axes.grid':True,'grid.alpha':.25}); return plt

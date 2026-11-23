"""Importacao explicita do CSV profissional; preserva o original e produz dados SI com hash."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from campo import output,finish,table,validate_trace
from comum import salvar_json,sha256


def import_reference(source,config,out):
    cfg=json.loads(Path(config).read_text(encoding='utf-8'))
    model=str(cfg.get('instrumento_modelo','')).strip()
    if not model or 'PREENCHER' in model.upper():raise ValueError('Preencha instrumento_modelo no mapa da referencia.')
    g=float(cfg.get('g_ms2',9.80665))
    if not 9<g<10:raise ValueError('g da referencia invalido.')
    d=pd.read_csv(source,sep=cfg.get('separador',','),decimal=cfg.get('decimal','.'),skiprows=int(cfg.get('linhas_ignorar',0)),encoding=cfg.get('encoding','utf-8-sig'))
    tc=cfg.get('tempo_coluna')
    if tc:
        unit=cfg.get('tempo_unidade','s');factor={'s':1.,'ms':1e-3,'us':1e-6}.get(unit)
        if factor is None:raise ValueError('Tempo deve ser s, ms ou us.')
        t=pd.to_numeric(d[tc],errors='raise').to_numpy(float)*factor
    else:
        fs=float(cfg.get('fs_hz') or 0)
        if not np.isfinite(fs) or fs<=0:raise ValueError('Informe tempo_coluna ou fs_hz valido, sem inferir taxa nominal.')
        t=np.arange(len(d))/fs
    origin=float(t[0]);t=t-origin
    columns={'tempo_s':t};channels={};limits={}
    for axis,c in cfg.get('canais',{}).items():
        if axis not in ['x','y','z','force']:raise ValueError('Canal de saida deve ser x, y, z ou force.')
        unit=c['unidade'];v=pd.to_numeric(d[c['coluna']],errors='raise').to_numpy(float)
        expected='N' if axis=='force' else 'm/s2'
        if unit==expected:factor=1.
        elif axis!='force' and unit=='g':factor=g
        elif unit=='V':
            factor=float(c.get('fator_para_si',0))
            if factor<=0:raise ValueError('Para tensao, informe fator_para_si: (m/s2)/V ou N/V do condicionamento real.')
        else:raise ValueError(f'Unidade {unit} nao suportada para {axis}. Converta o mapa explicitamente.')
        sign=int(c.get('sinal',1))
        if sign not in (-1,1):raise ValueError('Sinal deve ser +1 ou -1.')
        y=(v-float(c.get('offset_entrada',0)))*factor*sign
        if not np.isfinite(y).all():raise ValueError('Canal com valor nao finito.')
        name='forca_n' if axis=='force' else 'a'+axis+'_ms2'
        channels[axis]=y;columns[name]=y
        limits[axis]=c.get('limite_abs_si')
    if not channels:raise ValueError('Mapa sem canais.')
    qc=validate_trace(t,channels)
    dest=Path(out)/'referencia.csv';pd.DataFrame(columns).to_csv(dest,index=False,float_format='%.15g')
    meta=dict(schema='REFERENCIA_SI_V1',instrumento_modelo=model,configuracao_origem=cfg,
              limites_abs_si=limits,tempo_origem_s=origin,tempo_zerado=True,
              arquivo_origem=str(Path(source).resolve()),sha256_origem=sha256(source),
              csv_sha256=sha256(dest),g_ms2=g,qc=qc,
              certificado_verificado_pelo_pacote=False,
              nota='Escala e certificado informados pelo operador; nao sao verificados automaticamente.')
    salvar_json(meta,dest.with_suffix('.json'));return dest,meta


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('csv');p.add_argument('--mapa',required=True);p.add_argument('--saida',default='dados/referencia')
    a=p.parse_args()
    try:
        out=output(a.saida,'referencia',[a.csv,a.mapa],vars(a));dest,meta=import_reference(a.csv,a.mapa,out)
        finish(out,meta['qc']);print('CSV SI:',dest.resolve());return 0
    except Exception as e:print('ERRO:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

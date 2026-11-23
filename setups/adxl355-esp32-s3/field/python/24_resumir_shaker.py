"""Resume repeticoes independentes por frequencia comandada e nivel, sem criterio automatico de aprovacao."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from campo import output,finish,table


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('analises',nargs='+');p.add_argument('--saida',default='dados/processados');a=p.parse_args()
    try:
        groups={};rows=[];seen=set();inputs=[]
        for item in a.analises:
            path=Path(item)/'analise.json';m=json.loads(path.read_text());r=m.get('resultados',{})
            if m.get('status')!='concluido' or 'f_comando_hz' not in r:raise ValueError('Entrada nao e analise de shaker concluida.')
            keyhash=tuple(x['sha256'] for x in m['entradas'][:2])
            if keyhash in seen:raise ValueError('Mesmo par de aquisicoes repetido. Reprocessar nao e repetir o ensaio.')
            seen.add(keyhash);inputs.append(path);key=(r['f_comando_hz'],r['nivel'])
            row=dict(f_comando_hz=key[0],nivel=key[1],repeticao=r['repeticao'],f_no_hz=r['no']['f_hz'],f_ref_hz=r['referencia']['f_hz'],
                     rms_no_ms2=r['no']['amplitude_rms_ms2'],rms_ref_ms2=r['referencia']['amplitude_rms_ms2'],desvio_rms_pct=r['desvio_amplitude_rms_pct'],desvio_f_pct=r['desvio_f_no_ref_pct'])
            rows.append(row);groups.setdefault(key,[]).append(row)
        summary=[]
        for (freq,level),g in groups.items():
            r=dict(f_comando_hz=freq,nivel=level,n=len(g))
            for k in ['f_no_hz','f_ref_hz','rms_no_ms2','rms_ref_ms2','desvio_rms_pct','desvio_f_pct']:
                vals=[x[k] for x in g];r[k+'_media']=np.mean(vals);r[k+'_dp']=np.std(vals,ddof=1) if len(vals)>1 else None
            summary.append(r)
        out=output(a.saida,'resumo_shaker',inputs,vars(a));table(rows,out,'repeticoes');table(summary,out,'resumo_por_frequencia_nivel');finish(out,dict(grupos=len(groups),nota='DP entre aquisicoes; nao e incerteza expandida ou conformidade ISO.'))
        print(out.resolve());return 0
    except Exception as e:print('ERRO:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

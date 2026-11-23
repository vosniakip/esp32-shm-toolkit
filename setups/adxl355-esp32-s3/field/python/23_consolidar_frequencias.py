"""Reune frequencias persistentes de pontos/repeticoes sem estimar formas modais."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from campo import output,finish,table


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('analises',nargs='+',help='Pastas de saida de 22_identificar_passarela.py.')
    p.add_argument('--tolerancia-hz',type=float,default=.05);p.add_argument('--saida',default='dados/processados')
    a=p.parse_args()
    try:
        if a.tolerancia_hz<=0:raise ValueError('Tolerancia deve ser positiva.')
        rows=[];inputs=[];seen=set()
        for item in a.analises:
            folder=Path(item);jp=folder/'analise.json';m=json.loads(jp.read_text(encoding='utf-8'))
            if m.get('status')!='concluido' or 'metodo_principal' not in m.get('resultados',{}):raise ValueError('Pasta nao e uma identificacao concluida da passarela.')
            raw=m['entradas'][0]['sha256']
            if raw in seen:raise ValueError('A mesma aquisicao foi incluída duas vezes. Nao contar reprocessamento como repeticao.')
            seen.add(raw);inputs.append(jp)
            try:d=pd.read_csv(folder/'frequencias_candidatas.csv')
            except pd.errors.EmptyDataError:continue
            for r in d.to_dict('records'):
                if r['classificacao']!='candidata_consistente':continue
                r.update(ponto=m['resultados']['ponto'],condicao=m['resultados']['condicao'],repeticao=m['resultados']['repeticao'],arquivo=str(folder),hash_aquisicao=raw)
                rows.append(r)
        out=output(a.saida,'frequencias_consolidadas',inputs,vars(a));table(rows,out,'ocorrencias')
        groups=[]
        for r in sorted(rows,key=lambda r:r['f_hz']):
            eligible=[g for g in groups if max(abs(r['f_hz']-v['f_hz']) for v in g)<=max(a.tolerancia_hz,2*max(v['df_hz'] for v in g),2*r['df_hz'])]
            if eligible:min(eligible,key=lambda g:abs(r['f_hz']-np.mean([v['f_hz'] for v in g]))).append(r)
            else:groups.append([r])
        summary=[]
        for i,g in enumerate(groups,1):
            # Uma frequencia por aquisicao evita peso extra por aparecer em tres eixos e FDD.
            acquisitions={}
            for r in g:acquisitions.setdefault(r['hash_aquisicao'],[]).append(r['f_hz'])
            vals=[np.mean(v) for v in acquisitions.values()];points=sorted({r['ponto'] for r in g});conditions=sorted({r['condicao'] for r in g})
            summary.append(dict(grupo=i,f_media_hz=np.mean(vals),f_dp_entre_aquisicoes_hz=np.std(vals,ddof=1) if len(vals)>1 else None,
                                f_min_hz=min(vals),f_max_hz=max(vals),aquisicoes_distintas=len(vals),n_pontos=len(points),
                                pontos=';'.join(points),condicoes=';'.join(conditions),metodos=';'.join(sorted({r['metodo'] for r in g})),
                                situacao='observada_multiplos_pontos' if len(points)>1 else 'observada_um_ponto',
                                decisao_humana='',justificativa=''))
        table(summary,out,'frequencias_para_revisao');finish(out,dict(n_grupos=len(groups),nota='Grupos proximos nao equivalem a modos distintos; revisar pares proximos, excitacao e estrutura. Sem MAC espacial.'))
        print(out.resolve());return 0
    except Exception as e:print('ERRO:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

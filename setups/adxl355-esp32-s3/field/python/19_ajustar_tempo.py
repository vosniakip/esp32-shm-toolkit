"""Ajusta t_ref = a + b*t_no com tres ou mais marcas correspondentes, sem correlacao circular."""
import argparse,sys
import numpy as np
import pandas as pd
from campo import output,finish,table
from comum import salvar_json,sha256


def fit_time_pairs(d):
    if len(d)<3:raise ValueError('Use pelo menos tres pares; preferencialmente cinco ou mais, distribuidos no registro.')
    x=d.t_no_s.to_numpy(float);y=d.t_ref_s.to_numpy(float);u=d.u_par_s.to_numpy(float)
    if not np.isfinite(np.c_[x,y,u]).all() or np.any(u<=0):raise ValueError('Tempos finitos e u_par_s positivo obrigatorios.')
    if np.any(np.diff(x)<=0) or np.any(np.diff(y)<=0):raise ValueError('Marcas fora de ordem/duplicadas. Confira a correspondencia.')
    if x[-1]-x[0]<10:raise ValueError('Marcas devem cobrir pelo menos 10 s para estimar a diferenca de relogios.')
    xc=float(np.average(x,weights=1/u**2));A=np.c_[np.ones(len(x)),x-xc]
    B=A/u[:,None];coef=np.linalg.lstsq(B,y/u,rcond=None)[0]
    a=float(coef[0]-coef[1]*xc);b=float(coef[1]);res=y-(a+b*x)
    # Diagnostico, nao incerteza expandida: combina erros declarados e residuos.
    cov=np.linalg.inv(B.T@B);v=np.c_[np.ones(2),np.array([x[0],x[-1]])-xc]
    pred=np.sqrt(np.einsum('ij,jk,ik->i',v,cov,v))
    envelope=float(max(np.max(u),np.max(np.abs(res)),np.max(pred)))
    valid=bool(b>0 and abs(b-1)<.02 and np.max(np.abs(res)/u)<=3)
    result=dict(schema='TEMPO_AFIM_V4',a_s=a,b=b,deriva_relativa_ppm=(b-1)*1e6,
                residuos_rms_s=float(np.sqrt(np.mean(res**2))),residuo_max_s=float(np.max(np.abs(res))),
                dominio_no_s=[float(x[0]),float(x[-1])],diagnostico_tempo_s=envelope,
                limite_fase_50hz_graus=360*50*envelope,
                n_pares=len(x),ajuste_valido=valid,
                nota='u_par_s e declarado pelo operador; envelope e diagnostico, sem cobertura metrologica. Nao inclui atrasos dos sensores/filtros.')
    return result,res


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('pares');p.add_argument('--csv-no',required=True);p.add_argument('--csv-ref',required=True)
    p.add_argument('--tipo',choices=['pulsos','impactos'],required=True);p.add_argument('--saida',default='dados/processados')
    a=p.parse_args()
    try:
        d=pd.read_csv(a.pares);result,res=fit_time_pairs(d)
        result.update(tipo=a.tipo,csv_no_sha256=sha256(a.csv_no),csv_ref_sha256=sha256(a.csv_ref),fase_validada=False)
        out=output(a.saida,'tempo',[a.pares,a.csv_no,a.csv_ref],vars(a));d['residuo_s']=res;table(d,out,'pares_residuos')
        salvar_json(result,out/'sincronismo.json');finish(out,result);print(out.resolve())
        if not result['ajuste_valido']:print('AJUSTE REPROVADO. Reveja pares/erros declarados; nao usar para comparacao temporal.');return 2
        print('Alinhamento valido no dominio das marcas; fase e sincronismo metrologico nao foram validados.');return 0
    except Exception as e:print('ERRO:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

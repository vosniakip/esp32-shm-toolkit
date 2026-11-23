import argparse,json,sys
from pathlib import Path
import pandas as pd
from campo import load_node,load_reference,output,finish
from frf_impacto import estimate_frf,save_frf


def main():
    p=argparse.ArgumentParser(description='FRF H1 opcional: exige martelo instrumentado com forca medida, ao menos 3 impactos e, para o no, alinhamento temporal.')
    p.add_argument('referencia_csv');p.add_argument('--eventos',required=True);p.add_argument('--no-csv');p.add_argument('--calibracao');p.add_argument('--permitir-nominal',action='store_true')
    p.add_argument('--sincronismo');p.add_argument('--eixo-no',choices=list('xyz'),default='z');p.add_argument('--eixo-ref',choices=list('xyz'),default='z')
    p.add_argument('--pre-s',type=float,default=2);p.add_argument('--pos-s',type=float,default=20);p.add_argument('--fmin',type=float,default=.5);p.add_argument('--fmax',type=float,default=50);p.add_argument('--saida',default='dados/processados')
    a=p.parse_args()
    try:
        r=load_reference(a.referencia_csv);n=load_node(a.no_csv,a.calibracao,9.80665,a.permitir_nominal) if a.no_csv else None
        sync=json.loads(Path(a.sincronismo).read_text()) if a.sincronismo else None
        d,q,s=estimate_frf(r,pd.read_csv(a.eventos),a.eixo_ref,a.pre_s,a.pos_s,n,a.eixo_no,sync,a.fmin,a.fmax)
        out=output(a.saida,'frf',[a.referencia_csv,a.eventos,a.no_csv,a.calibracao,a.sincronismo],vars(a));save_frf(d,q,s,out);finish(out,s);print(out.resolve());return 0
    except Exception as e:print('ERRO:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

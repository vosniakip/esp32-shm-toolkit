import argparse,json,sys
from pathlib import Path
from campo import *
from metodos_campo import *


def base_parser(description,reference=True):
    p=argparse.ArgumentParser(description=description);p.add_argument('no_csv')
    if reference:p.add_argument('referencia_csv')
    p.add_argument('--calibracao');p.add_argument('--permitir-nominal',action='store_true')
    p.add_argument('--saida',default='dados/processados')
    return p


def shaker_main():
    p=base_parser('Shaker: ajuste senoidal independente de frequencia e amplitude, sem fase entre equipamentos.')
    p.add_argument('--frequencia',type=float,required=True);p.add_argument('--eixo-no',choices=list('xyz'),default='z');p.add_argument('--eixo-ref',choices=list('xyz'),default='z')
    p.add_argument('--inicio-no',type=float,default=10);p.add_argument('--fim-no',type=float);p.add_argument('--inicio-ref',type=float,default=10);p.add_argument('--fim-ref',type=float)
    p.add_argument('--nivel',default='nivel-01');p.add_argument('--repeticao',type=int,default=1)
    a=p.parse_args()
    try:
        n=load_node(a.no_csv,a.calibracao,9.80665,a.permitir_nominal);r=load_reference(a.referencia_csv)
        result,traces,spectra=shaker(n,r,a.eixo_no,a.eixo_ref,a.frequencia,a.inicio_no,a.fim_no,a.inicio_ref,a.fim_ref)
        result.update(nivel=a.nivel,repeticao=a.repeticao,qc_no=n.qc,qc_ref=r.qc,calibracao=n.meta['calibracao_aplicada'])
        out=output(a.saida,'shaker',[a.no_csv,a.referencia_csv,a.calibracao],vars(a));save_shaker(result,traces,spectra,out);finish(out,result)
        print(out.resolve());return 0
    except Exception as e:print('ERRO:',e,file=sys.stderr);return 2


def impulse_main():
    p=base_parser('Trelica: resposta ao mesmo impacto. Sem marcas, compara espectros e RMS; nao calcula erro temporal.')
    p.add_argument('--impacto-no',type=float);p.add_argument('--impacto-ref',type=float,required=True);p.add_argument('--sincronismo')
    p.add_argument('--eixo-no',choices=list('xyz'),default='z');p.add_argument('--eixo-ref',choices=list('xyz'),default='z')
    p.add_argument('--pre-s',type=float,default=2);p.add_argument('--pos-s',type=float,default=40);p.add_argument('--fmin',type=float,default=.5);p.add_argument('--fmax',type=float,default=50);p.add_argument('--segmento-s',type=float,default=16)
    a=p.parse_args()
    try:
        n=load_node(a.no_csv,a.calibracao,9.80665,a.permitir_nominal);r=load_reference(a.referencia_csv)
        sync=json.loads(Path(a.sincronismo).read_text()) if a.sincronismo else None
        result,traces,spectra,pair=compare_impulse(n,r,a.eixo_no,a.eixo_ref,a.impacto_no,a.impacto_ref,a.pre_s,a.pos_s,a.fmin,a.fmax,a.segmento_s,sync)
        result.update(qc_no=n.qc,qc_ref=r.qc,calibracao=n.meta['calibracao_aplicada'])
        out=output(a.saida,'trelica',[a.no_csv,a.referencia_csv,a.calibracao,a.sincronismo],vars(a));save_impulse(result,traces,spectra,pair,out);finish(out,result);print(out.resolve());return 0
    except Exception as e:print('ERRO:',e,file=sys.stderr);return 2


def bridge_main():
    p=base_parser('Passarela: PP/Welch com persistencia por blocos, mais FDD local dos canais simultaneos.',False)
    p.add_argument('--ponto',required=True);p.add_argument('--condicao',default='ambiente');p.add_argument('--repeticao',type=int,default=1)
    p.add_argument('--fmin',type=float,default=.5);p.add_argument('--fmax',type=float,default=50);p.add_argument('--segmento-s',type=float,default=64);p.add_argument('--blocos',type=int,default=4)
    p.add_argument('--proeminencia-db',type=float,default=6);p.add_argument('--cadencia-hz',type=float,action='append',default=[]);p.add_argument('--descarte-s',type=float,default=2)
    a=p.parse_args()
    try:
        if a.blocos<2:raise ValueError('Use ao menos dois blocos.')
        n=load_node(a.no_csv,a.calibracao,9.80665,a.permitir_nominal)
        result,peaks,vectors,extra=identify(n,a.fmin,a.fmax,a.segmento_s,a.blocos,a.proeminencia_db,a.cadencia_hz,a.descarte_s)
        result.update(ponto=a.ponto,condicao=a.condicao,repeticao=a.repeticao,calibracao=n.meta['calibracao_aplicada'])
        out=output(a.saida,'passarela',[a.no_csv,a.calibracao],vars(a));save_identification(result,peaks,vectors,extra,out);finish(out,result)
        print(out.resolve());print('Frequencias candidatas. Confira persistencia, harmônicos de excitacao e repeticoes; nenhum modo espacial foi identificado.');return 0
    except Exception as e:print('ERRO:',e,file=sys.stderr);return 2

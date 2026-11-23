"""Exporta marcas do log do no. Pareamento com a DAQ permanece explicito."""
import argparse,csv,sys
from pathlib import Path
from campo import output,finish,table


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log');p.add_argument('--incluir-http',action='store_true');p.add_argument('--saida',default='dados/processados');a=p.parse_args()
    try:
        rows=[]
        with Path(a.log).open(encoding='utf-8') as f:
            for r in csv.DictReader(f):
                event=r.get('event','')
                if event=='pulso_externo' or (a.incluir_http and event.startswith('http_')):
                    rows.append(dict(marca=len(rows)+1,tipo=event,tempo_no_s=int(r['value'])/1e6,boot_us=int(r['boot_us'])))
        out=output(a.saida,'marcas',[a.log],vars(a));table(rows,out,'marcas_no');finish(out,dict(n=len(rows),nota='Tempos relativos a start_boot_us. HTTP nao serve como pulso preciso. Confira marcas descartadas no meta.json.'));print(out.resolve());return 0
    except Exception as e:print('ERRO:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

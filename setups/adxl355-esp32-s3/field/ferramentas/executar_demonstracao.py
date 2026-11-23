"""Executa os analisadores v4 com sinais artificiais gerados localmente, sem acessar a rede ou hardware."""
from pathlib import Path
import argparse,subprocess,sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from comum import nova_pasta,salvar_json


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--saida',default=str(ROOT/'exemplos/resultados'));a=p.parse_args()
    out=nova_pasta(a.saida,'demonstracao');d=ROOT/'exemplos/sintetico'
    def run(script,args,folder):
        cmd=[sys.executable,str(ROOT/'python'/script),*map(str,args),'--saida',str(out/folder)]
        print('Executando',script,flush=True);r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=180)
        (out/(folder+'.log.txt')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
        if r.returncode:raise RuntimeError(f'{script} falhou. Consulte {out/(folder+".log.txt")}')
        return next((out/folder).iterdir())
    imp=run('18_importar_referencia.py',[d/'shaker_ref/exportacao_sintetica.csv','--mapa',d/'shaker_ref/mapa.json'],'importacao')
    sh=run('20_analisar_shaker.py',[d/'shaker_no/aquisicao.csv',imp/'referencia.csv','--permitir-nominal','--frequencia','11.37'],'shaker')
    tm=run('19_ajustar_tempo.py',[d/'pares_tempo.csv','--csv-no',d/'trelica_no/aquisicao.csv','--csv-ref',d/'trelica_ref/referencia.csv','--tipo','pulsos'],'tempo')
    tr=run('21_comparar_trelica.py',[d/'trelica_no/aquisicao.csv',d/'trelica_ref/referencia.csv','--permitir-nominal','--impacto-ref','20','--sincronismo',tm/'sincronismo.json'],'trelica')
    br=run('22_identificar_passarela.py',[d/'passarela_no/aquisicao.csv','--permitir-nominal','--ponto','SINTETICO','--segmento-s','24'],'passarela')
    fr=run('26_analisar_frf_martelo.py',[d/'frf_ref/referencia.csv','--eventos',d/'impactos.csv','--pre-s','1','--pos-s','5'],'frf')
    co=run('23_consolidar_frequencias.py',[br],'consolidacao')
    re=run('24_resumir_shaker.py',[sh],'resumo_shaker')
    result={k:json.loads((v/'analise.json').read_text())['resultados'] for k,v in [('shaker',sh),('tempo',tm),('trelica',tr),('passarela',br),('frf',fr)]}
    salvar_json(dict(dados_sinteticos=True,nota='Verificacao do software; nao e resultado de laboratorio.',resultados=result),out/'resumo_sintetico.json')
    print('Demonstracao concluida:',out.resolve())
if __name__=='__main__':main()

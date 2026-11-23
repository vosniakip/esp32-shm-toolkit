"""Controle sem fio v4. START e unico; nenhuma repeticao automatica apos falha de rede."""
import argparse,json,sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from cliente_wifi import Node, capture
from formato_sd import unique_directory,save_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',default='192.168.4.1')
    sub=p.add_subparsers(dest='acao',required=True)
    sub.add_parser('info');sub.add_parser('status');sub.add_parser('listar');sub.add_parser('parar')
    s=sub.add_parser('iniciar');s.add_argument('perfil');s.add_argument('--saida',default='dados/campanhas');s.add_argument('--acompanhar',action='store_true')
    s=sub.add_parser('marcar');s.add_argument('rotulo')
    s=sub.add_parser('baixar');s.add_argument('run_id');s.add_argument('--saida',default='dados/brutos')
    a=p.parse_args();node=Node(a.host)
    try:
        if a.acao=='info':result=node.info()
        elif a.acao=='status':result=node.status()
        elif a.acao=='listar':result=node.files()
        elif a.acao=='parar':result=node.request('/api/stop',{'stop':'1'})
        elif a.acao=='marcar':result=node.mark(a.rotulo)
        elif a.acao=='baixar':
            dest=unique_directory(a.saida,a.run_id)
            result={'csv':str(node.download_run(a.run_id,dest))}
        else:
            profile=json.loads(Path(a.perfil).read_text(encoding='utf-8'))
            params=dict(profile.get('parametros',profile))
            params.pop('request_id',None);params['request_id']=uuid4().hex
            if a.acompanhar:
                result={'arquivos':[str(x) for x in capture(node,params,a.saida)]}
            else:
                if node.status().get('ocupado'):raise RuntimeError('No ocupado. Consulte STATUS.')
                node.clock()
                local=unique_directory(a.saida,params.get('ensaio','ensaio'))
                record=dict(criado_em=datetime.now().astimezone().isoformat(),host=node.base,parametros=params,status='preparado')
                save_json(record,local/'comando.json')
                try:
                    result=node.start(params)
                except Exception as e:
                    record.update(status='start_incerto',erro=str(e));save_json(record,local/'comando.json')
                    raise RuntimeError(f'START incerto. Consulte STATUS antes de repetir. Request {params["request_id"]}.') from e
                record.update(status='aceito',resposta=result);save_json(record,local/'comando.json')
                print('Comando salvo:',local/'comando.json')
                print('Aquisição autonoma. Use STATUS e, ao terminar, LISTAR/BAIXAR ou o navegador.')
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (Exception,KeyboardInterrupt) as e:
        print('ERRO:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

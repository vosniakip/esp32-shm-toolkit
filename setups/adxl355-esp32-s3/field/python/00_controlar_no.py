"""Consulta, parada e configuracao da partida automatica por HTTP."""
import argparse
import json
import sys
from cliente_wifi import Node
from formato_sd import load_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='192.168.4.1')
    p.add_argument('acao', choices=['info', 'status', 'listar', 'stop', 'relogio', 'armar-partida', 'desarmar-partida'])
    p.add_argument('--config', help='JSON de uma campanha, com campos HTTP em docs/API_E_FORMATO.md.')
    a = p.parse_args()
    try:
        n = Node(a.host)
        if a.acao == 'info':
            result = n.info()
        elif a.acao == 'status':
            result = n.status()
        elif a.acao == 'listar':
            result = n.files()
        elif a.acao == 'stop':
            result = n.request('/api/stop', {'stop': 1})
        elif a.acao == 'relogio':
            result = n.clock()
        elif a.acao == 'desarmar-partida':
            result = n.request('/api/autostart', {'habilitar': 0})
        else:
            if not a.config:
                p.error('armar-partida requer --config, por exemplo configuracoes/aquecimento_partida_frio.json')
            params = load_json(a.config)
            if 'etapas' in params:
                p.error('Use uma configuracao simples, nao um roteiro de varias posicoes.')
            params['habilitar'] = 1
            result = n.request('/api/autostart', params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as e:
        print('ERRO:', e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

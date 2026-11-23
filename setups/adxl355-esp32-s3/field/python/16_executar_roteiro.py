"""Executa etapas de um JSON; exige reposicionamento confirmado antes de cada pose."""
import argparse
import sys
from cliente_wifi import Node, capture
from formato_sd import load_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('roteiro')
    p.add_argument('--host', default='192.168.4.1')
    p.add_argument('--saida', default='dados/brutos')
    p.add_argument('--xlsx', action='store_true')
    a = p.parse_args()
    try:
        script = load_json(a.roteiro)
        if script.get('schema') != 'roteiro_adxl355_v3' or not script.get('etapas'):
            raise ValueError('Roteiro deve conter schema roteiro_adxl355_v3 e uma lista etapas.')
        node = Node(a.host)
        for i, step in enumerate(script['etapas'], 1):
            params = dict(script.get('padrao', {}))
            params.update(step['parametros'])
            print(f'Etapa {i}/{len(script["etapas"])}: {step["instrucao"]}')
            answer = input('Com o conjunto apoiado e parado, digite CONFIRMO para executar (ou SAIR): ').strip()
            if answer != 'CONFIRMO':
                print('Roteiro encerrado. Nenhum comando desta etapa foi enviado.')
                return 0
            capture(node, params, a.saida, xlsx=a.xlsx)
        print('Roteiro concluido. Todos os dados baixados foram preservados.')
        return 0
    except (OSError, ValueError, RuntimeError, EOFError, KeyboardInterrupt) as e:
        print('Roteiro interrompido:', e, file=sys.stderr)
        print('Se havia aquisicao em andamento, ela pode continuar no no; consulte STATUS.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

"""Recupera downloads de ensaios ja existentes, sem iniciar novas aquisicoes."""
import argparse
import sys
from pathlib import Path
from cliente_wifi import Node


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='192.168.4.1')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--run', help='Identificador devolvido por listar/status.')
    group.add_argument('--todos', action='store_true')
    p.add_argument('--saida', help='Para um --run: pasta exata para retomar. Para --todos: pasta pai.')
    p.add_argument('--xlsx', action='store_true')
    a = p.parse_args()
    try:
        node = Node(a.host)
        runs = [a.run] if a.run else [r['id'] for r in node.files() if r.get('finalizado')]
        if not runs:
            raise ValueError('Nenhum arquivo finalizado. Consulte listar e o guia de recuperacao parcial.')
        for run in runs:
            if a.run and a.saida:
                dest = Path(a.saida)
            else:
                dest = Path(a.saida or 'dados/brutos/recuperados') / run
            csv_path = node.download_run(run, dest, xlsx=a.xlsx)
            print('CSV:', csv_path.resolve())
        return 0
    except (OSError, ValueError, RuntimeError) as e:
        print('ERRO:', e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

"""Importa arquivos copiados do cartao ou baixados manualmente pelo navegador."""
import argparse
import sys
from pathlib import Path
from formato_sd import convert_run, unique_directory


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('binario')
    p.add_argument('--metadados', help='Padrao: meta.json na pasta do binario.')
    p.add_argument('--manifesto', help='Padrao: manifest.json na mesma pasta, se existir.')
    p.add_argument('--log', help='Padrao: events.log na mesma pasta.')
    p.add_argument('--saida', default='dados/brutos/importados')
    p.add_argument('--recuperar-parcial', action='store_true', help='Aproveita apenas blocos inteiros de arquivo truncado; nao aprova dados incompletos.')
    p.add_argument('--xlsx', action='store_true')
    a = p.parse_args()
    try:
        raw = Path(a.binario)
        meta = Path(a.metadados) if a.metadados else raw.parent / 'meta.json'
        manifest = Path(a.manifesto) if a.manifesto else raw.parent / 'manifest.json'
        log = Path(a.log) if a.log else raw.parent / 'events.log'
        dest = unique_directory(a.saida, raw.parent.name)
        result = convert_run(raw, meta, dest, manifest if manifest.exists() else None,
                             log if log.exists() else None, a.recuperar_parcial, a.xlsx)
        print('CSV:', result.resolve())
        if a.recuperar_parcial:
            print('Recuperacao para diagnostico. Confira captura_completa no JSON; os analisadores espectrais rejeitam registros incompletos.')
        return 0
    except (OSError, ValueError, RuntimeError) as e:
        print('ERRO:', e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

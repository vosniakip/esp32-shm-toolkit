"""Compara qualidade/temporizacao dos modos de radio; nao comprova sincronismo entre nos."""
import argparse
import sys
import pandas as pd
from comum import localizar, ler, diagnostico, iniciar_saida, finalizar_saida, tabela


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('entradas', nargs='+')
    p.add_argument('--saida', default='dados/processados/validacao_wifi_sd')
    a = p.parse_args()
    out = None
    try:
        files = localizar(a.entradas)
        out = iniciar_saida(a, 'validacao_wifi_sd', files)
        rows = []
        for file in files:
            d = ler(file)
            m = d.attrs['metadados']
            q = diagnostico(d)
            sd = m.get('metadados_sd', {})
            approved = (q['captura_completa'] and not any(q[k] for k in
                ('lacunas_indice', 'lacunas_temporais', 'perdas_registradas', 'erros_spi', 'transporte_invalido')) and
                m.get('integridade_transferencia_verificada') is True)
            rows.append(dict(arquivo=str(file), radio=m.get('radio', 'legado'),
                             buffer_pico=sd.get('buffer_pico_registros'),
                             buffer_capacidade=sd.get('buffer_capacidade_registros'),
                             integridade_recebimento=m.get('integridade_transferencia_verificada', False),
                             continuidade_e_integridade_ok=approved, **q))
        frame = pd.DataFrame(rows)
        tabela(frame, out, 'validacao_wifi_sd')
        table = frame.groupby('radio')[['fs_efetiva_hz', 'jitter_dp_pct']].agg(['mean', 'std', 'min', 'max'])
        table.columns = ['_'.join(c) for c in table.columns]
        tabela(table.reset_index(), out, 'comparacao_modos')
        finalizar_saida(out)
        print(frame[['radio', 'n', 'fs_efetiva_hz', 'jitter_dp_pct', 'continuidade_e_integridade_ok']].to_string(index=False))
        print('Resultados:', out.resolve())
        return 0
    except (OSError, ValueError, KeyError) as e:
        if out:
            finalizar_saida(out, str(e))
        print('ERRO:', e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

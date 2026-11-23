"""CLI de captura. Cada sequencia e executada pelo no, independentemente do PC."""
import argparse
import sys
from cliente_wifi import Node, capture


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='192.168.4.1')
    p.add_argument('--duracao', type=int, default=30, help='Segundos inteiros, de 1 a 21600.')
    p.add_argument('--ensaio', default='funcional')
    p.add_argument('--posicao', default='zpos')
    p.add_argument('--repeticao', type=int, default=1)
    p.add_argument('--repeticoes', type=int, default=1, help='Quantidade executada autonomamente pelo no (1-20).')
    p.add_argument('--intervalo', type=int, default=10)
    p.add_argument('--atraso', type=int, default=5)
    p.add_argument('--sensor', default='adxl355-01')
    p.add_argument('--montagem', default='pcb-inclinada-v1')
    p.add_argument('--referencial', choices=['conjunto', 'sensor'], default='conjunto')
    p.add_argument('--taxa', type=int, choices=[250, 500], default=500)
    p.add_argument('--faixa', type=int, choices=[2, 4, 8], default=2)
    p.add_argument('--radio', choices=['ativo', 'desligado'], default='ativo')
    p.add_argument('--nota', default='')
    p.add_argument('--calibracao-id', default='nao-aplicada')
    p.add_argument('--saida', default='dados/brutos')
    p.add_argument('--margem', type=int, default=1800, help='Segundos adicionais para reconectar/finalizar.')
    p.add_argument('--xlsx', action='store_true', help='Exporta tambem XLSX; requer openpyxl.')
    args = p.parse_args()
    if not 1 <= args.duracao <= 21600 or not 1 <= args.repeticoes <= 20 or args.margem < 0:
        p.error('Duracao, repeticoes ou margem fora dos limites.')
    params = dict(duracao_s=args.duracao, ensaio=args.ensaio, posicao=args.posicao,
                  repeticao=args.repeticao, repeticoes=args.repeticoes, intervalo_s=args.intervalo,
                  atraso_s=args.atraso, sensor=args.sensor, montagem=args.montagem,
                  referencial=args.referencial, taxa=args.taxa, faixa=args.faixa,
                  radio=args.radio, nota=args.nota, calibracao_id=args.calibracao_id)
    try:
        files = capture(Node(args.host), params, args.saida, args.margem, args.xlsx)
        print(f'Concluido. {len(files)} arquivo(s) CSV verificado(s). A copia no microSD foi mantida.')
        return 0
    except (OSError, ValueError, RuntimeError) as e:
        print('ERRO:', e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

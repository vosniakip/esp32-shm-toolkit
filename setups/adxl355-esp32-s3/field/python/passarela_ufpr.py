"""Campanha persistente: um no, dois meios de vao, 1200 s em cada ponto.

O arquivo de campanha e local ao computador. O no recebe um START por tentativa.
STATUS e BAIXAR nunca iniciam aquisicoes. Reposicionamento permanece manual.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime
from uuid import uuid4

from cliente_wifi import Node
from formato_sd import load_json, sha256, unique_directory

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'PASSARELA_UFPR_2P_V1'
DURATION = 1200
POINTS = {
    'P01': {'descricao': 'Meio do vao entre os pilares A e B', 'vao': 'V1', 'fracao_vao': 0.5},
    'P02': {'descricao': 'Meio do vao entre os pilares B e C', 'vao': 'V2', 'fracao_vao': 0.5},
}


def now():
    return datetime.now().astimezone().isoformat()


def write_atomic(value, path):
    path = Path(path)
    tmp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with tmp.open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def campaign_path(path):
    p = Path(path).resolve()
    return p / 'campanha.json' if p.is_dir() else p


def load_campaign(path):
    p = campaign_path(path)
    data = load_json(p)
    if data.get('schema') != SCHEMA or set(data.get('pontos', {})) != set(POINTS):
        raise ValueError('Campanha desconhecida: esperado um plano UFPR com P01 e P02.')
    cal = p.parent / data['calibracao']['arquivo']
    if sha256(cal) != data['calibracao']['sha256']:
        raise ValueError('A copia da calibracao foi alterada. Preserve a campanha original.')
    for pid in POINTS:
        profile = data['pontos'][pid]['perfil']
        if (profile.get('duracao_s') != DURATION or profile.get('repeticoes') != 1
                or profile.get('posicao') != pid or profile.get('ensaio') != 'passarela'
                or profile.get('calibracao_id') != data['calibracao']['id_registrado']):
            raise ValueError('Plano alterado: cada ponto deve ter um registro de 1200 s e o mesmo identificador de calibracao.')
    return p, data


def persist(path, data):
    data['atualizado_em'] = now()
    write_atomic(data, path)


def prepare(calibration, root='dados/campanhas', host='192.168.4.1', radio='ativo'):
    from modelos_calibracao import conferir_matriz, array_finito
    calpath = Path(calibration).resolve()
    cal = load_json(calpath)
    if (cal.get('formato') != 'calibracao_adxl355_matriz_v1'
            or cal.get('sensor_modelo') != 'ADXL355'
            or cal.get('ordem_eixos') != list('xyz')
            or cal.get('referencial_saida', {}).get('nome') != 'conjunto'):
        raise ValueError('Use o JSON da matriz completa ADXL355, no referencial do conjunto.')
    conferir_matriz(cal.get('matriz_correcao_g_lsb'))
    array_finito([cal.get('offset_lsb', {}).get(e) for e in 'xyz'], (3,), 'Offsets')
    sensor, mount = cal.get('identificacao_sensor', ''), cal.get('montagem', '')
    for text, maximum, label in [(sensor, 24, 'sensor'), (mount, 32, 'montagem')]:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,' + str(maximum) + '}', text):
            raise ValueError(f'Identificador de {label} incompativel com o firmware.')
    config = cal.get('configuracao_calibracao', {})
    rate = config.get('fs_nominal_hz')
    if (rate not in (250, 500) or cal.get('faixa_g') != 2
            or config.get('lpf_hz') != rate / 4 or config.get('hpf') != 0):
        raise ValueError('O plano requer faixa +/-2 g, HPF desativado e taxa 250/500 Hz com LPF taxa/4, iguais a calibracao.')
    if radio not in ('ativo', 'desligado'):
        raise ValueError('Modo de radio invalido.')
    Node(host)  # Valida a sintaxe, sem acesso a rede.
    folder = unique_directory(root, 'passarela_ufpr_2p')
    (folder / 'calibracao').mkdir()
    (folder / 'perfis').mkdir()
    copied = folder / 'calibracao/calibracao.json'
    shutil.copyfile(calpath, copied)
    digest = sha256(copied)
    tag = 'cal_' + digest[:16]
    points = {}
    for pid, definition in POINTS.items():
        profile = dict(sensor=sensor, montagem=mount, referencial='conjunto', taxa=int(rate), faixa=2,
                       repeticao=1, repeticoes=1, atraso_s=10, intervalo_s=0, radio=radio,
                       calibracao_id=tag, ensaio='passarela', posicao=pid, duracao_s=DURATION,
                       nota='UFPR; ' + definition['descricao'] + '; aquisicao sucessiva, sem sincronismo espacial.')
        points[pid] = dict(definition, perfil=profile, tentativas=[], tentativa_aceita=None)
        write_atomic(profile, folder / 'perfis' / (pid + '_20min.json'))
    data = dict(schema=SCHEMA, versao='4.1.0', criado_em=now(), host=host,
                estrutura='Passarela UFPR Jardim Botanico - Centro Politecnico',
                arranjo='Um no reposicionado; duas aquisicoes sucessivas de 1200 s',
                calibracao=dict(arquivo='calibracao/calibracao.json', sha256=digest,
                                origem=str(calpath), id_registrado=tag, status_origem=cal.get('status')),
                geometria=dict(ordem_pilares='A-B-C, do lado Botanico para o Politecnico; confirmar em campo',
                               vao_v1_m=None, vao_v2_m=None,
                               nota='Comprimentos nao foram presumidos iguais e nao foram inferidos dos 89 m totais.'),
                pontos=points, analises=[])
    write_atomic(data, folder / 'campanha.json')
    with (folder / 'eventos_campo.csv').open('x', newline='', encoding='utf-8-sig') as f:
        csv.writer(f).writerow(['ponto', 'tentativa', 'tempo_desde_inicio_s', 'hora_local',
                               'evento', 'pedestres_aproximado', 'sentido', 'cadencia_hz',
                               'vento', 'temperatura_ambiente_c', 'observacao'])
    print('Calibracao copiada sem alteracao. Estado de origem:', cal.get('status', 'nao informado'))
    print('A campanha nao aprova nem refaz a calibracao. Confira a validacao e a montagem real.')
    print('Campanha:', (folder / 'campanha.json').resolve())
    return folder / 'campanha.json'


def latest(point):
    return point['tentativas'][-1] if point['tentativas'] else None


def start(path, point_id, confirmed=False, repeat=False, reason='', note='', node=None):
    p, data = load_campaign(path)
    if not confirmed:
        raise ValueError('Confirme a fixacao, o ponto e a orientacao com --confirmar-montagem. Nenhum START foi enviado.')
    point = data['pontos'][point_id]
    old = latest(point)
    for other_id, other in data['pontos'].items():
        pending = latest(other)
        if pending and pending['estado'] not in ('verificado', 'rejeitado', 'falha'):
            raise ValueError(f'Existe tentativa pendente ou START incerto em {other_id}. Use status/baixar; nenhum novo START sera enviado.')
    if point_id == 'P02' and data['pontos']['P01']['tentativa_aceita'] is None:
        raise ValueError('Baixe e verifique P01 antes de reposicionar o no e iniciar P02.')
    if old:
        if old['estado'] not in ('verificado', 'rejeitado', 'falha'):
            raise ValueError('Existe tentativa pendente ou START incerto. Use status/baixar; nao sera enviado outro START.')
        if not repeat or not reason.strip():
            raise ValueError('Para repetir preservando os arquivos, use --nova-tentativa --motivo "justificativa".')
    elif repeat:
        raise ValueError('Ainda nao existe uma tentativa neste ponto.')
    number = len(point['tentativas']) + 1
    if number > 999:
        raise ValueError('Limite de repeticoes do firmware excedido.')
    profile = dict(point['perfil'], repeticao=number, request_id=uuid4().hex)
    if note:
        profile['nota'] = note
    if len(profile['nota'].encode('utf-8')) > 240:
        raise ValueError('Observacao excede 240 bytes UTF-8.')
    node = node or Node(data['host'])
    if node.status().get('ocupado'):
        raise RuntimeError('O no esta ocupado. Aguarde a conclusao antes de mover ou iniciar.')
    info = node.info()
    if not all(info.get(key) is True for key in ('sensor_pronto', 'sd_pronto', 'tarefas_prontas')):
        raise RuntimeError('INFO indica sensor, microSD ou tarefas indisponiveis.')
    required = int(DURATION * profile['taxa'] * 32 * 1.03 + 10_000_000)
    if int(info.get('sd_livre_bytes_ultima_consulta', 0)) < required:
        raise RuntimeError('Espaco livre informado pelo no insuficiente para este registro e uma margem de 10 MB.')
    node.clock()
    relative = f'tentativas/{point_id}/r{number:02d}'
    folder = p.parent / relative
    folder.mkdir(parents=True, exist_ok=False)
    attempt = dict(numero=number, estado='preparado', request_id=profile['request_id'], run_id=None,
                   pasta=relative, preparado_em=now(), motivo_repeticao=reason, parametros=profile, info_antes=info)
    point['tentativas'].append(attempt)
    persist(p, data)  # O request_id existe em disco antes do unico POST.
    write_atomic(attempt, folder / 'comando.json')
    try:
        response = node.start(profile)
    except Exception as exc:
        attempt.update(estado='start_incerto', erro=str(exc))
        persist(p, data)
        write_atomic(attempt, folder / 'comando.json')
        raise RuntimeError('START com resultado incerto. O no pode estar gravando. Reconecte e use status/baixar; nao reinicie.') from exc
    attempt.update(estado='aceito', aceito_em=now(), resposta=response)
    persist(p, data)
    write_atomic(attempt, folder / 'comando.json')
    print(point_id, ': comando aceito. 1200 s de coleta apos 10 s de espera. Nao movimente o conjunto.')
    print('Pode fechar o computador. Consulte status; ao concluir, execute baixar para este ponto.')
    return attempt


def status(path, node=None):
    p, data = load_campaign(path)
    node = node or Node(data['host'])
    remote = node.status()
    for point in data['pontos'].values():
        attempt = latest(point)
        if attempt and attempt['request_id'] == remote.get('request_id'):
            attempt['ultimo_status'] = remote
            if remote.get('run_id'):
                attempt['run_id'] = remote['run_id']
            if not remote.get('ocupado') and remote.get('estado') in ('falha', 'cancelado'):
                attempt['estado'] = 'falha'
            persist(p, data)
    print(json.dumps(dict(resumo_local={pid: dict(estado=(latest(v) or {}).get('estado', 'nao_iniciado'),
                     tentativa_aceita=v['tentativa_aceita']) for pid, v in data['pontos'].items()},
                     estado_no=remote), ensure_ascii=False, indent=2))
    return remote


def verify_capture(csv_path, profile, cal_path):
    from campo import load_node
    from formato_sd import verify_files
    side = load_json(Path(csv_path).with_suffix('.json'))
    folder = Path(csv_path).parent
    verified = verify_files(folder / 'raw.bin', folder / 'meta.json', folder / 'manifest.json', folder / 'events.log')
    if (side.get('binario_sha256') != verified['raw_sha256']
            or side.get('metadados_sd_sha256') != verified['meta_sha256']):
        raise ValueError('A origem binaria do CSV nao coincide com os arquivos verificados.')
    sd = side.get('metadados_sd', {})
    if (not side.get('captura_completa') or not side.get('integridade_transferencia_verificada')
            or side.get('recuperacao_parcial') or sd.get('motivo') != 'tempo_concluido'):
        raise ValueError('O registro nao e completo e verificado; preserve os arquivos para diagnostico.')
    for key in ('sensor', 'montagem', 'ensaio', 'posicao', 'repeticao', 'request_id', 'calibracao_id'):
        if sd.get(key) != profile[key]:
            raise ValueError(f'O registro nao corresponde ao plano: {key}.')
    if sd.get('duracao_solicitada_s') != DURATION:
        raise ValueError('O arquivo nao foi programado para 1200 s.')
    tr = load_node(csv_path, cal_path)
    duration = tr.t[-1] - tr.t[0]
    if not DURATION - .5 <= duration <= DURATION + .5:
        raise ValueError(f'Duracao observada {duration:.6f} s fora de 1200 +/-0,5 s.')
    if abs(tr.fs / profile['taxa'] - 1) > .01:
        raise ValueError('Taxa efetiva fora da triagem operacional de +/-1% da nominal.')
    return dict(duracao_observada_s=float(duration), qc=tr.qc, csv_sha256=sha256(csv_path),
                sidecar_sha256=sha256(Path(csv_path).with_suffix('.json')),
                raw_sha256=verified['raw_sha256'], calibracao_sha256=sha256(cal_path), registrado_em=now())


def download(path, point_id, run=None, node=None):
    p, data = load_campaign(path)
    point = data['pontos'][point_id]
    attempt = latest(point)
    if not attempt:
        raise ValueError('Ponto ainda nao iniciado por esta campanha.')
    node = node or Node(data['host'])
    remote = node.status()
    if remote.get('ocupado'):
        raise RuntimeError('O no ainda esta ocupado. Espere o fim, inclusive a finalizacao do microSD.')
    if remote.get('request_id') == attempt['request_id']:
        attempt['ultimo_status'] = remote
        if remote.get('run_id'):
            attempt['run_id'] = remote['run_id']
    selected = run or attempt.get('run_id')
    if not selected:
        raise ValueError('Run desconhecido apos reinicio/queda de rede. Use 17 listar e baixar --run ID, preservando a campanha.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,31}', selected):
        raise ValueError('Run invalido.')
    if attempt.get('run_id') and selected != attempt['run_id']:
        raise ValueError('Run diferente do ja vinculado a tentativa.')
    attempt.update(run_id=selected, estado='download_pendente')
    persist(p, data)
    folder = p.parent / attempt['pasta'] / selected
    try:
        csv_path = node.download_run(selected, folder)
    except Exception as exc:
        failed = (remote.get('request_id') == attempt['request_id'] and remote.get('estado') in ('falha', 'cancelado'))
        attempt.update(estado='falha' if failed else 'download_pendente', erro=str(exc))
        persist(p, data)
        raise
    try:
        check = verify_capture(csv_path, attempt['parametros'], p.parent / data['calibracao']['arquivo'])
    except Exception as exc:
        attempt.update(estado='rejeitado', erro=str(exc), csv=str(Path(csv_path).relative_to(p.parent)))
        persist(p, data)
        raise
    attempt.update(estado='verificado', verificacao=check, csv=str(Path(csv_path).relative_to(p.parent)))
    point['tentativa_aceita'] = attempt['numero']
    persist(p, data)
    write_atomic(check, folder / 'qualidade_passarela.json')
    print(point_id, ': arquivo completo e verificado.', Path(csv_path).resolve())
    if point_id == 'P01':
        print('Salve uma copia. Somente agora reposicione e fixe o no em P02.')
    return Path(csv_path)


def analyze(path, cadences_p01=(), cadences_p02=()):
    import numpy as np
    from campo import load_node, output, finish, table
    from metodos_campo import identify, save_identification
    p, data = load_campaign(path)
    chosen = {}
    for pid, point in data['pontos'].items():
        accepted = point['tentativa_aceita']
        if accepted is None:
            raise ValueError('Baixe e verifique os dois pontos antes da analise conjunta.')
        attempt = next(v for v in point['tentativas'] if v['numero'] == accepted)
        if attempt.get('estado') != 'verificado':
            raise ValueError('Tentativa selecionada sem verificacao valida.')
        csv_path = p.parent / attempt['csv']
        if sha256(csv_path) != attempt['verificacao']['csv_sha256']:
            raise ValueError('CSV alterado desde a verificacao; use o bruto original.')
        if sha256(csv_path.with_suffix('.json')) != attempt['verificacao']['sidecar_sha256']:
            raise ValueError('Metadados do CSV alterados desde a verificacao.')
        chosen[pid] = (attempt, csv_path)
    if len({sha256(v[1]) for v in chosen.values()}) != 2:
        raise ValueError('A mesma aquisicao nao pode representar os dois pontos.')
    cal = p.parent / data['calibracao']['arquivo']
    root = unique_directory(p.parent / 'analises', 'dois_pontos_20min')
    write_atomic(data, root / 'campanha_fonte.json')
    folders, rows, spectra = [], [], {}
    for pid, cadences in zip(POINTS, (cadences_p01, cadences_p02)):
        if any(not math.isfinite(c) or c <= 0 for c in cadences):
            raise ValueError('Cadencias devem ser positivas e medidas/estimadas em campo.')
        attempt, csv_path = chosen[pid]
        verify_capture(csv_path, attempt['parametros'], cal)
        tr = load_node(csv_path, cal)
        result, peaks, vectors, extra = identify(tr, lo=.5, hi=50, segment=64, blocks=4,
                                                prominence=6, cadences=cadences, discard=2)
        result.update(ponto=pid, condicao='operacional_20min', repeticao=attempt['numero'],
                      calibracao=tr.meta['calibracao_aplicada'], descricao_ponto=POINTS[pid],
                      aquisicao_sucessiva=True, duracao_solicitada_s=DURATION)
        dest = output(root, pid, [csv_path, cal], dict(ponto=pid, segmento_s=64, blocos=4, fmin=.5, fmax=50))
        save_identification(result, peaks, vectors, extra, dest)
        finish(dest, result)
        folders.append(dest)
        spectra[pid] = extra[2]
        rows.append(dict(ponto=pid, vao=POINTS[pid]['vao'], run_id=attempt['run_id'],
                         duracao_s=tr.qc['duracao_s'], fs_hz=tr.fs,
                         **{f'rms_{e}_ms2': result['rms_banda_ms2'][e] for e in 'xyz'},
                         csv_sha256=sha256(csv_path), calibracao_sha256=sha256(cal)))
        del tr, extra
    table(rows, root, 'qualidade_e_rms_por_ponto')
    command = [sys.executable, str(ROOT / 'python/23_consolidar_frequencias.py'),
               *[str(v) for v in folders], '--saida', str(root)]
    consolidated = subprocess.run(command, text=True, capture_output=True)
    (root / 'consolidacao.log.txt').write_text(consolidated.stdout + consolidated.stderr, encoding='utf-8')
    if consolidated.returncode:
        raise RuntimeError('Analises individuais preservadas. Falha na consolidacao; consulte o log em ' + str(root))
    from comum import plot_setup
    plt = plot_setup()
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), layout='constrained')
    for ax, e in zip(axes, 'xyz'):
        for pid in POINTS:
            f, power = spectra[pid][e]
            ax.semilogy(f, np.maximum(power, 1e-30), label=pid)
        ax.set(xlim=(.5, 50), xlabel='Frequencia (Hz)', ylabel='PSD ((m/s2)^2/Hz)', title='Eixo ' + e.upper())
        ax.legend()
    fig.suptitle('Dois pontos sucessivos: a excitacao pode diferir entre registros')
    fig.savefig(root / 'comparacao_psd_pontos.png', dpi=200)
    fig.savefig(root / 'comparacao_psd_pontos.svg')
    plt.close(fig)
    summary = dict(schema='ANALISE_PASSARELA_UFPR_2P_V1', status='concluido',
                   calibracao_sha256=sha256(cal), arquivos=rows,
                   pastas_analises=[str(v.relative_to(root)) for v in folders],
                   consolidacao=consolidated.stdout.strip().splitlines()[-1],
                   fase_entre_pontos_estimada=False, formas_modais_espaciais_estimadas=False,
                   nota='Coincidencias de picos sao candidatas. Diferencas de RMS nao sao erro de sensor, pois a excitacao foi sucessiva.')
    write_atomic(summary, root / 'resumo_campanha.json')
    data['analises'].append(dict(criado_em=now(), pasta=str(root.relative_to(p.parent))))
    persist(p, data)
    print('Resultados:', root.resolve())
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='acao', required=True)
    prep = actions.add_parser('preparar', help='Cria a campanha sem acessar o no.')
    prep.add_argument('--calibracao', required=True)
    prep.add_argument('--saida', default='dados/campanhas')
    prep.add_argument('--host', default='192.168.4.1')
    prep.add_argument('--radio', choices=['ativo', 'desligado'], default='ativo')
    for label in ('status', 'iniciar', 'baixar', 'analisar'):
        sub = actions.add_parser(label)
        sub.add_argument('campanha', help='Pasta da campanha ou caminho de campanha.json.')
        if label in ('iniciar', 'baixar'):
            sub.add_argument('--ponto', choices=list(POINTS), required=True)
        if label == 'iniciar':
            sub.add_argument('--confirmar-montagem', action='store_true')
            sub.add_argument('--nova-tentativa', action='store_true')
            sub.add_argument('--motivo', default='')
            sub.add_argument('--observacao', default='')
        if label == 'baixar':
            sub.add_argument('--run', help='Recuperacao apos reinicio: run_id da mesma tentativa, sem novo START.')
        if label == 'analisar':
            sub.add_argument('--cadencia-p01', type=float, action='append', default=[])
            sub.add_argument('--cadencia-p02', type=float, action='append', default=[])
    args = parser.parse_args()
    try:
        if args.acao == 'preparar':
            prepare(args.calibracao, args.saida, args.host, args.radio)
        elif args.acao == 'iniciar':
            start(args.campanha, args.ponto, args.confirmar_montagem, args.nova_tentativa, args.motivo, args.observacao)
        elif args.acao == 'status':
            status(args.campanha)
        elif args.acao == 'baixar':
            download(args.campanha, args.ponto, args.run)
        else:
            analyze(args.campanha, args.cadencia_p01, args.cadencia_p02)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print('ERRO:', exc, file=sys.stderr)
        print('Os registros anteriores foram preservados. Se houve START, o no pode continuar gravando; use status.', file=sys.stderr)
        return 2

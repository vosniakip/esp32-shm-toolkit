"""HTTP de bancada, somente biblioteca padrao: comandos, retomada e SHA-256."""
from __future__ import annotations

import http.client
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from formato_sd import convert_run, load_json, save_json, sha256, unique_directory, publish_no_replace


class NodeError(RuntimeError):
    pass


class Node:
    def __init__(self, host='192.168.4.1', timeout=15):
        if '://' not in host:
            host = 'http://' + host
        parsed = urllib.parse.urlparse(host)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Host deve ser um endereco HTTP(S), sem credenciais na URL.')
        if parsed.path not in ('', '/') or parsed.query or parsed.fragment:
            raise ValueError('Informe somente o host, por exemplo 192.168.4.1.')
        self.base = host.rstrip('/')
        self.timeout = timeout
        # Nao envie o endereco local por um proxy configurado no Windows.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, path, data=None):
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(self.base + path, data=body)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            try:
                details = json.loads(e.read().decode('utf-8'))
                message = details.get('erro', str(details))
            except (ValueError, UnicodeError):
                message = e.reason
            raise NodeError(f'HTTP {e.code}: {message}') from e

    def info(self):
        return self.request('/api/info')

    def status(self):
        return self.request('/api/status')

    def clock(self):
        return self.request('/api/clock', {'epoch_ms': int(time.time() * 1000)})

    def mark(self, label="evento"):
        return self.request("/api/mark", {"rotulo": label})

    def files(self):
        offset, result = 0, []
        while True:
            response = self.request('/api/files?offset=' + str(offset))
            result.extend(response['arquivos'])
            if not response.get('mais'):
                return result
            next_offset = response['proximo_offset']
            if next_offset <= offset:
                raise NodeError('Paginacao do no nao avancou.')
            offset = next_offset

    def start(self, params):
        return self.request('/api/start', params)

    def wait(self, request_id, timeout, poll=2, on_status=print):
        deadline = time.monotonic() + timeout
        last_message, last_print = None, 0
        while time.monotonic() < deadline:
            try:
                state = self.status()
                if state.get('request_id') != request_id:
                    raise NodeError('O no informa outro request_id (pode ter reiniciado). Nao sera iniciado outro ensaio automaticamente.')
                message = (state.get('estado'), state.get('run_id'), state.get('amostras_gravadas'))
                if on_status and (message[:2] != (last_message or ())[:2] or time.monotonic() - last_print >= 10):
                    on_status(f"{state.get('estado')}: {state.get('run_id')} | gravadas={state.get('amostras_gravadas')}")
                    last_print = time.monotonic()
                last_message = message
                if not state.get('ocupado'):
                    return state
            except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, http.client.HTTPException) as e:
                if on_status and time.monotonic() - last_print >= 10:
                    on_status('Sem conexao. O no pode continuar gravando. Reconecte a rede Wi-Fi ao terminar. ' + str(e))
                    last_print = time.monotonic()
            time.sleep(poll)
        raise TimeoutError('Tempo de espera excedido. Nao reinicie nem envie START novamente; consulte STATUS e baixe a campanha existente.')

    def download_file(self, run, kind, destination, expected_size=None, expected_sha=None, retries=5):
        if not re.fullmatch('[A-Za-z0-9_-]{1,31}', run):
            raise ValueError('Identificador de aquisicao invalido.')
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if expected_sha and sha256(dest) == expected_sha and (expected_size is None or dest.stat().st_size == expected_size):
                return dest
            raise FileExistsError(f'Arquivo ja existe sem coincidir com a verificacao: {dest}. Escolha outra pasta.')
        partial = dest.with_name(dest.name + '.download.part')
        last_error = None
        for attempt in range(retries):
            offset = partial.stat().st_size if partial.exists() else 0
            if expected_size is not None and offset > expected_size:
                raise ValueError('Download parcial excede o tamanho remoto. Preserve-o e escolha outra pasta.')
            if expected_size is not None and offset == expected_size:
                break
            query = urllib.parse.urlencode(dict(run=run, kind=kind, offset=offset))
            try:
                with self.opener.open(self.base + '/api/download?' + query, timeout=self.timeout) as response:
                    if offset and response.status != 206:
                        raise NodeError('Servidor nao confirmou a retomada por offset; arquivo parcial preservado.')
                    length = response.headers.get('Content-Length')
                    wanted = int(length) if length is not None else None
                    received = 0
                    with partial.open('ab') as f:
                        while True:
                            data = response.read(64 * 1024)
                            if not data:
                                break
                            f.write(data)
                            received += len(data)
                    if wanted is not None and received != wanted:
                        raise ConnectionError(f'Resposta truncada: {received}/{wanted} bytes.')
                if expected_size is not None and partial.stat().st_size != expected_size:
                    raise ConnectionError('Tamanho recebido incompleto.')
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as e:
                last_error = e
                if attempt + 1 < retries:
                    time.sleep(min(attempt + 1, 3))
        else:
            raise NodeError(f'Download interrompido, parcial preservado em {partial}: {last_error}')
        if expected_size is not None and partial.stat().st_size != expected_size:
            raise NodeError('Tamanho final incorreto; parcial preservado.')
        if expected_sha and sha256(partial) != expected_sha:
            raise ValueError(f'SHA-256 incorreto em {partial}. Nenhum ACK foi enviado.')
        publish_no_replace(partial, dest)
        return dest

    def download_run(self, run, output_dir, xlsx=False):
        """Baixa manifesto, metadados, log e binario; verifica antes de enviar ACK."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / 'manifest.json'
        # Manifestos sao imutaveis apos a finalizacao. A retentativa reutiliza o local.
        if not manifest_path.exists():
            self.download_file(run, 'manifest', manifest_path)
        manifest = load_json(manifest_path)
        if manifest.get('schema') != 'ADXL355_SD_MANIFEST_V3' or manifest.get('run_id') != run:
            raise ValueError('Manifesto invalido/de outra aquisicao.')
        for key in ('raw_sha256', 'meta_sha256', 'log_sha256'):
            if not re.fullmatch('[0-9a-f]{64}', str(manifest.get(key, ''))):
                raise ValueError('Hash remoto invalido.')
        meta = self.download_file(run, 'meta', output_dir / 'meta.json', expected_sha=manifest['meta_sha256'])
        log = self.download_file(run, 'log', output_dir / 'events.log', expected_sha=manifest['log_sha256'])
        raw = self.download_file(run, 'bin', output_dir / 'raw.bin', expected_size=int(manifest['raw_bytes']), expected_sha=manifest['raw_sha256'])
        csv_path = convert_run(raw, meta, output_dir, manifest_path, log, xlsx=xlsx)
        receipt = dict(run_id=run, host=self.base, recebido_em=datetime.now().astimezone().isoformat(),
                       raw_sha256=sha256(raw), csv_sha256=sha256(csv_path), ack_no=False)
        try:
            answer = self.request('/api/ack', dict(run=run, sha256=manifest['raw_sha256']))
            receipt['ack_no'] = bool(answer.get('recebimento_registrado'))
        except (NodeError, urllib.error.URLError, TimeoutError) as e:
            receipt['observacao_ack'] = str(e)
        save_json(receipt, output_dir / 'recebimento.json')
        return csv_path


def capture(node, params, root='dados/brutos', margin=1800, xlsx=False, on_status=print):
    request_id = params.setdefault('request_id', uuid4().hex)
    local = unique_directory(root, params.get('ensaio', 'ensaio'))
    save_json(dict(host=node.base, request_id=request_id, parametros=params,
                   criado_em=datetime.now().astimezone().isoformat(), status='preparado'), local / 'comando.json')
    before = node.status()
    if before.get('ocupado'):
        raise NodeError('No ocupado. Consulte o estado e baixe a campanha anterior.')
    node.clock()
    # Um POST por chamada. Resultado incerto exige consultar o mesmo request_id.
    try:
        answer = node.start(params)
    except Exception as e:
        save_json(dict(request_id=request_id, parametros=params, status='resultado_do_start_incerto', erro=str(e)), local / 'comando.json')
        raise NodeError(f'Resultado do START incerto; consulte STATUS antes de repetir. Request: {request_id}; pasta: {local}') from e
    save_json(dict(request_id=request_id, parametros=params, resposta=answer, status='aceito'), local / 'comando.json')
    repetitions = int(params.get('repeticoes', 1))
    estimate = repetitions * (int(params['duracao_s']) + int(params.get('atraso_s', 5)) + 1) + max(0, repetitions - 1) * int(params.get('intervalo_s', 10))
    state = node.wait(request_id, estimate + margin, on_status=on_status)
    save_json(state, local / 'estado_final.json')
    files = []
    for run in state.get('sequencia_ids', []):
        try:
            csv_path = node.download_run(run, local / run, xlsx=xlsx)
            files.append(csv_path)
            if on_status:
                on_status('CSV: ' + str(csv_path.resolve()))
        except (NodeError, ValueError, OSError, urllib.error.URLError) as e:
            save_json(dict(erro=str(e), run_id=run, observacao='Arquivos ja baixados foram preservados.'), local / ('falha_download_' + run + '.json'))
            raise NodeError(f'Aquisicao encerrada; falha no download de {run}: {e}. Use 13_baixar_dados.py com --saida {local / run}') from e
    if state.get('estado') != 'concluido':
        raise NodeError(f"Sequencia nao concluiu normalmente: {state.get('motivo')}. Dados preservados em {local}.")
    return files

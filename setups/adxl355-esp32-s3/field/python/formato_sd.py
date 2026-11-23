"""Formato binario v3: leitura em blocos, CRC32, rodape e verificacao SHA-256.

Nao depende de numpy/pandas: a captura e a conversao CSV podem funcionar antes
da instalacao das bibliotecas de analise. Nenhuma lacuna e interpolada.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import struct
import zlib
from datetime import datetime
from pathlib import Path
from uuid import uuid4

HEADER = struct.Struct('<8sHHHHIIQ32s')
BLOCK = struct.Struct('<4sIHHI')
RECORD = struct.Struct('<QQiiihH')
FOOTER = struct.Struct('<4sIQ')
MAGIC = b'A355SD3\0'
CSV_COLUMNS = ['indice', 't_us', 'ax_raw', 'ay_raw', 'az_raw', 'temp_raw',
               'perdidas_acum', 'descartes_fila', 'leituras_descartadas', 'erros_spi', 'flags']


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save_json(value, path):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def publish_no_replace(source, destination):
    """Publica no mesmo diretorio sem substituir um arquivo criado por outra instancia."""
    source, destination = Path(source), Path(destination)
    if os.name == 'nt':
        # No Windows, rename falha se o destino ja existir.
        source.rename(destination)
    else:
        # No POSIX, rename substituiria o destino; link faz a criacao exclusiva.
        os.link(source, destination)
        source.unlink()


def unique_directory(root, label):
    safe = re.sub('[^A-Za-z0-9_-]', '_', str(label))[:48]
    p = Path(root) / (datetime.now().astimezone().strftime('%Y%m%d_%H%M%S_%f') + '_' + safe + '_' + uuid4().hex[:6])
    p.mkdir(parents=True, exist_ok=False)
    return p


class RawReader:
    """Iterador de blocos. A inspecao completa so termina depois do rodape.

    recuperar_parcial aceita somente um ultimo bloco truncado/rodape ausente;
    CRC incorreto, repeticao de blocos e valores invalidos continuam fatais.
    """
    def __init__(self, path, recuperar_parcial=False):
        self.path = Path(path)
        self.recover = recuperar_parcial
        self.header = None
        self.records = self.blocks = self.index_gaps = 0
        self.complete = False
        self.partial_reason = None
        self.first_us = self.last_us = None

    def _truncated(self, message):
        if not self.recover:
            raise ValueError(message)
        self.partial_reason = message

    def __iter__(self):
        previous_index = previous_time = None
        with self.path.open('rb') as f:
            raw = f.read(HEADER.size)
            if len(raw) != HEADER.size:
                raise ValueError('Cabecalho ausente/truncado; nenhum registro pode ser recuperado.')
            magic, version, hsize, rsize, reserved, rate, span, duration, run = HEADER.unpack(raw)
            if (magic, version, hsize, rsize, reserved) != (MAGIC, 3, 64, 32, 0):
                raise ValueError('Cabecalho/formato binario nao reconhecido.')
            if rate not in (250, 500) or span not in (2, 4, 8) or not 1_000_000 <= duration <= 21_600_000_000:
                raise ValueError('Configuracao invalida no cabecalho.')
            run_id = run.split(b'\0', 1)[0].decode('ascii')
            if not re.fullmatch('[A-Za-z0-9_-]{1,31}', run_id):
                raise ValueError('Identificador invalido no binario.')
            self.header = dict(run_id=run_id, taxa_hz=rate, faixa_g=span, duracao_us=duration)
            while True:
                marker = f.read(4)
                if marker == b'END3':
                    tail = f.read(12)
                    if len(tail) != 12:
                        self._truncated('Rodape truncado.')
                        break
                    _, blocks, records = FOOTER.unpack(marker + tail)
                    if (blocks, records) != (self.blocks, self.records) or f.read(1):
                        raise ValueError('Rodape inconsistente ou bytes excedentes no arquivo.')
                    self.complete = True
                    break
                if not marker:
                    self._truncated('Rodape ausente; arquivo nao finalizado.')
                    break
                if marker != b'BLK3':
                    raise ValueError('Marcador de bloco invalido; nao se procura outro marcador para ocultar corrupcao.')
                tail = f.read(12)
                if len(tail) != 12:
                    self._truncated('Cabecalho do ultimo bloco truncado.')
                    break
                _, sequence, count, size, expected_crc = BLOCK.unpack(marker + tail)
                if sequence != self.blocks or size != 32 or not 1 <= count <= 128:
                    raise ValueError('Bloco fora de ordem, tamanho ou contagem invalidos.')
                data = f.read(count * size)
                if len(data) != count * size:
                    self._truncated('Ultimo bloco truncado: apenas os blocos anteriores sao aproveitados.')
                    break
                if zlib.crc32(data) != expected_crc:
                    raise ValueError(f'CRC32 incorreto no bloco {sequence}.')
                rows = []
                for row in RECORD.iter_unpack(data):
                    index, time_us, x, y, z, temp, flags = row
                    if previous_index is not None:
                        if index <= previous_index or time_us <= previous_time:
                            raise ValueError('Indice ou timestamp repetido/decrescente.')
                        self.index_gaps += index - previous_index - 1
                    elif index != 0:
                        raise ValueError('O primeiro indice deve ser zero.')
                    if any(v < -524288 or v > 524287 for v in (x, y, z)):
                        raise ValueError('Aceleracao fora dos 20 bits com sinal.')
                    if temp < -1 or temp > 4095 or flags & ~3 or bool(flags & 2) != (temp == -1):
                        raise ValueError('Temperatura/flags invalidos.')
                    if time_us >= duration:
                        raise ValueError('Timestamp fora da janela solicitada.')
                    if self.first_us is None:
                        self.first_us = time_us
                    self.last_us = time_us
                    previous_index, previous_time = index, time_us
                    rows.append(row)
                self.blocks += 1
                self.records += count
                yield rows


def verify_files(raw, metadata, manifest=None, log=None, recuperar_parcial=False):
    raw, metadata = Path(raw), Path(metadata)
    meta = load_json(metadata)
    if meta.get('schema') != 'ADXL355_SD_META_V3':
        raise ValueError('Metadados nao pertencem ao formato SD V3 (firmware 3/4).')
    result = dict(raw_sha256=sha256(raw), meta_sha256=sha256(metadata), manifesto_verificado=False)
    if manifest is not None:
        m = load_json(manifest)
        if m.get('schema') != 'ADXL355_SD_MANIFEST_V3' or m.get('run_id') != meta.get('run_id'):
            raise ValueError('Manifesto de outro formato/aquisicao.')
        if raw.stat().st_size != m.get('raw_bytes') or result['raw_sha256'] != m.get('raw_sha256'):
            raise ValueError('Tamanho/SHA-256 do binario nao corresponde ao manifesto.')
        if result['meta_sha256'] != m.get('meta_sha256'):
            raise ValueError('SHA-256 dos metadados nao corresponde ao manifesto.')
        if log is None or sha256(log) != m.get('log_sha256'):
            raise ValueError('Log ausente ou SHA-256 diferente do manifesto.')
        result['manifesto_verificado'] = True
        result['manifesto'] = m
    elif not recuperar_parcial:
        raise ValueError('Manifesto ausente. Use --recuperar-parcial somente para diagnostico de uma captura interrompida.')
    result['metadados'] = meta
    return result


def convert_run(raw, metadata, output_dir, manifest=None, log=None,
                recuperar_parcial=False, xlsx=False):
    """Converte atomicamente; nao sobrescreve CSV existente nem cria tempos artificiais."""
    raw, metadata, output_dir = Path(raw), Path(metadata), Path(output_dir)
    checked = verify_files(raw, metadata, manifest, log, recuperar_parcial)
    meta = checked['metadados']
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / 'aquisicao.csv'
    sidecar = dest.with_suffix('.json')
    if dest.exists() or sidecar.exists():
        if dest.exists() and sidecar.exists():
            previous = load_json(sidecar)
            if (previous.get('binario_sha256') == checked['raw_sha256'] and
                previous.get('metadados_sd_sha256') == checked['meta_sha256'] and
                previous.get('csv_sha256') == sha256(dest)):
                if xlsx and not dest.with_suffix('.xlsx').exists():
                    export_xlsx(dest, previous)
                return dest
        raise FileExistsError('A saida ja existe e difere da conversao verificada. Use uma pasta nova.')
    temp = output_dir / ('aquisicao_' + uuid4().hex + '.csv.part')
    reader = RawReader(raw, recuperar_parcial)
    total_lost = int(meta.get('perdas_limite_inferior', 0))
    queue_drops = int(meta.get('descartes_fila', 0))
    spi_errors = int(meta.get('erros_spi', 0))
    discarded = int(meta.get('fifo_overruns', 0)) + int(meta.get('fila_drdy_overruns', 0))
    last_row = None
    previous_index, cumulative_gaps = None, 0
    try:
        with temp.open('x', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
            # Mantem apenas a ultima linha em memoria para anexar os contadores finais.
            for block in reader:
                for index, stamp, x, y, z, temp_raw, flags in block:
                    if previous_index is not None:
                        cumulative_gaps += index - previous_index - 1
                    previous_index = index
                    if last_row is not None:
                        writer.writerow(last_row)
                    last_row = [index, stamp, x, y, z, temp_raw, cumulative_gaps, 0, 0, 0, flags]
            if last_row is not None:
                last_row[6:10] = [max(total_lost, reader.index_gaps), queue_drops, discarded, spi_errors]
                writer.writerow(last_row)
        if reader.header['run_id'] != meta.get('run_id'):
            raise ValueError('O binario e o JSON identificam aquisicoes diferentes.')
        cfg = meta['configuracao']
        if (reader.header['taxa_hz'], reader.header['faixa_g']) != (cfg.get('fs_nominal_hz'), cfg.get('faixa_g')):
            raise ValueError('Configuracoes do cabecalho e JSON diferem.')
        if checked['manifesto_verificado']:
            m = checked['manifesto']
            if (reader.records, reader.blocks) != (m.get('records'), m.get('blocks')):
                raise ValueError('Contagem de registros/blocos difere do manifesto.')
            if reader.records != meta.get('amostras_gravadas') or not reader.complete or not meta.get('arquivo_finalizado'):
                raise ValueError('Finalizacao do binario e metadados inconsistente.')
        complete = bool(reader.complete and checked['manifesto_verificado'] and meta.get('captura_completa') and
                        meta.get('motivo') == 'tempo_concluido')
        side = dict(formato='ADXL355_S3_V1', versao_pacote='4.1.0',
                    sensor=meta['sensor'], montagem=meta['montagem'], ensaio=meta['ensaio'],
                    posicao=meta['posicao'], repeticao=meta['repeticao'], referencial_posicao=meta['referencial_posicao'],
                    configuracao=cfg, captura_completa=complete, linhas_invalidas=0,
                    binario_sha256=checked['raw_sha256'], metadados_sd_sha256=checked['meta_sha256'],
                    origem_binario=str(raw.resolve()), origem_metadados_sd=str(metadata.resolve()),
                    transporte='WiFi_SD', tempo_origem='DRDY_ISR_esp_timer_64bit', timestamps_reconstruidos=False,
                    integridade_transferencia_verificada=checked['manifesto_verificado'],
                    radio=meta.get('radio'), run_id=meta['run_id'], request_id=meta.get('request_id'),
                    recuperacao_parcial=not checked['manifesto_verificado'] or not reader.complete,
                    recuperacao_observacao=reader.partial_reason, metadados_sd=meta,
                    fim_firmware=dict(motivo=meta.get('motivo'), perdas=total_lost, descartes_fila=queue_drops,
                                      leituras_descartadas=discarded, erros_spi=spi_errors,
                                      fifo_overruns=meta.get('fifo_overruns', 0), amostras_gravadas=reader.records))
        side['csv_sha256'] = sha256(temp)
        # O nome final so aparece depois de toda a validacao; nao substitui dados anteriores.
        if dest.exists() or sidecar.exists():
            raise FileExistsError('Saida criada simultaneamente; nenhum arquivo foi substituido.')
        publish_no_replace(temp, dest)
        with sidecar.open('x', encoding='utf-8') as f:
            json.dump(side, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    if xlsx:
        export_xlsx(dest, side)
    return dest


def export_xlsx(csv_path, metadata):
    try:
        from openpyxl import Workbook
    except ImportError as e:
        raise RuntimeError('CSV pronto. Para XLSX, instale as dependencias de requirements.txt.') from e
    dest = Path(csv_path).with_suffix('.xlsx')
    if dest.exists():
        raise FileExistsError('XLSX ja existe; o original nao sera substituido.')
    wb = Workbook(write_only=True)
    summary = wb.create_sheet('Resumo')
    summary.append(['Campo', 'Valor'])
    for key in ('sensor', 'montagem', 'ensaio', 'posicao', 'repeticao', 'run_id', 'captura_completa',
                'integridade_transferencia_verificada', 'binario_sha256', 'csv_sha256'):
        summary.append([key, str(metadata.get(key))])
    count = int(metadata['fim_firmware']['amostras_gravadas'])
    if count <= 1_048_575:
        sheet = wb.create_sheet('Amostras_brutas')
        with Path(csv_path).open(newline='', encoding='utf-8') as f:
            rows = csv.reader(f)
            sheet.append(next(rows))
            for row in rows:
                sheet.append([int(x) for x in row])
    else:
        summary.append(['Amostras', count])
        summary.append(['Observacao', 'Serie excede o limite de linhas do Excel. Todos os dados estao no CSV; esta planilha contem apenas o resumo.'])
    wb.save(dest)
    return dest

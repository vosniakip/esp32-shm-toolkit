"""Arquivos sinteticos identificados; nao representam uma medicao do hardware."""
import math
import struct
import zlib
from pathlib import Path
from formato_sd import sha256, save_json


def make_run(root, count=1000, run='SINTETICO_0001', rate=500, reason='tempo_concluido'):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    raw = root / 'raw.bin'
    duration = max(1, math.ceil(count / rate))
    block_count = 0
    with raw.open('wb') as f:
        f.write(struct.pack('<8sHHHHIIQ32s', b'A355SD3\0', 3, 64, 32, 0, rate, 2, duration * 1_000_000, run.encode()))
        for start in range(0, count, 128):
            rows = []
            for i in range(start, min(start + 128, count)):
                # Senoide conhecida; timestamp com 500 us de fase inicial.
                stamp = 500 + round(i * 1_000_000 / rate)
                z = round(256000 * (1 + .02 * math.sin(2 * math.pi * 7.5 * i / rate)))
                rows.append(struct.pack('<QQiiihH', i, stamp, -120, 250, z, 1885, int(i % rate == 0)))
            payload = b''.join(rows)
            f.write(struct.pack('<4sIHHI', b'BLK3', block_count, len(rows), 32, zlib.crc32(payload)))
            f.write(payload)
            block_count += 1
        f.write(struct.pack('<4sIQ', b'END3', block_count, count))
    meta = dict(schema='ADXL355_SD_META_V3', firmware='3.0.0', run_id=run, request_id='SINTETICO',
                sensor='adxl355-sintetico', montagem='pcb-inclinada-sintetica', ensaio='dinamico',
                posicao='zpos', repeticao=1, referencial_posicao='conjunto',
                configuracao=dict(faixa_g=2, fs_nominal_hz=rate, sensibilidade_lsb_g=256000,
                                  lpf_hz=rate / 4, hpf=0),
                arquivo_finalizado=True, captura_completa=reason == 'tempo_concluido', motivo=reason,
                amostras_gravadas=count, amostras_adquiridas=count, perdas_limite_inferior=0,
                descartes_fila=0, erros_spi=0, fifo_overruns=0, fila_drdy_overruns=0,
                radio='ativo', start_boot_us=123456, end_boot_us=123456 + duration * 1_000_000,
                nota='DADOS SINTETICOS: somente verificacao do software.')
    save_json(meta, root / 'meta.json')
    (root / 'events.log').write_text('DADOS SINTETICOS; NAO SAO ENSAIO FISICO\n')
    manifest = dict(schema='ADXL355_SD_MANIFEST_V3', run_id=run, raw_bytes=raw.stat().st_size,
                    raw_sha256=sha256(raw), meta_sha256=sha256(root / 'meta.json'),
                    log_sha256=sha256(root / 'events.log'), records=count, blocks=block_count)
    save_json(manifest, root / 'manifest.json')
    return meta, manifest

"""Confere arquivos do ZIP extraido com seu manifesto SHA-256; nao altera arquivos."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root/'MANIFESTO_SHA256.json').read_text(encoding='utf-8'))
bad = []
for name, expected in manifest['arquivos'].items():
    p = (root/name).resolve()
    if not p.is_relative_to(root) or not p.is_file():
        bad.append(name + ': ausente/caminho invalido')
        continue
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    if h.hexdigest() != expected:
        bad.append(name + ': diferente')
if bad:
    print('\n'.join(bad))
    raise SystemExit(2)
print(f"{len(manifest['arquivos'])} arquivos conferidos; nenhum foi alterado.")

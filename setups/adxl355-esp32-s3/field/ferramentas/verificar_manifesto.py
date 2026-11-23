"""Confere o conteudo extraido do pacote, sem acessar rede ou modificar arquivos."""
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parents[1]
m=json.loads((root/'MANIFESTO_SHA256.json').read_text(encoding='utf-8'))
fail=[]
for item in m['arquivos']:
 p=root/item['arquivo']
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:fail.append(item['arquivo'])
if fail:
 print('Arquivos ausentes/alterados:',*fail,sep='\n');raise SystemExit(2)
print('Manifesto correto:',len(m['arquivos']),'arquivos. Isso confere integridade do pacote, nao validacao fisica.')

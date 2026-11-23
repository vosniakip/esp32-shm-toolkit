import json
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
sys.path.insert(0, str(ROOT / 'tests'))
from fabrica_sd import make_run
from formato_sd import RawReader, convert_run, load_json, save_json, sha256, verify_files
from cliente_wifi import Node, capture


class Binary(unittest.TestCase):
    def test_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_run(root)
            out = root / 'out'
            result = convert_run(root/'raw.bin', root/'meta.json', out, root/'manifest.json', root/'events.log')
            self.assertFalse(result.with_suffix('.xlsx').exists())
            convert_run(root/'raw.bin', root/'meta.json', out, root/'manifest.json', root/'events.log', xlsx=True)
            from comum import ler, converter, diagnostico
            d = converter(ler(result))
            self.assertEqual(len(d), 1000)
            self.assertAlmostEqual(d.temp_c.mean(), 25)
            self.assertAlmostEqual(diagnostico(d)['fs_efetiva_hz'], 500)
            self.assertTrue(d.attrs['metadados']['integridade_transferencia_verificada'])
            self.assertTrue(result.with_suffix('.xlsx').exists())
            self.assertEqual(convert_run(root/'raw.bin', root/'meta.json', out, root/'manifest.json', root/'events.log'), result)
            result.write_text(result.read_text().replace('256000', '250000', 1))
            with self.assertRaises(FileExistsError):
                convert_run(root/'raw.bin', root/'meta.json', out, root/'manifest.json', root/'events.log')

    def test_crc_corruption_not_hidden_by_updated_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, m = make_run(root)
            raw = bytearray((root/'raw.bin').read_bytes())
            raw[100] ^= 1
            (root/'raw.bin').write_bytes(raw)
            m['raw_sha256'] = sha256(root/'raw.bin')
            save_json(m, root/'manifest.json')
            with self.assertRaisesRegex(ValueError, 'CRC32'):
                convert_run(root/'raw.bin', root/'meta.json', root/'out', root/'manifest.json', root/'events.log')
            self.assertFalse((root/'out/aquisicao.csv').exists())

    def test_meta_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta, _ = make_run(root)
            meta['sensor'] = 'outro-sensor'
            save_json(meta, root/'meta.json')
            with self.assertRaisesRegex(ValueError, 'metadados'):
                verify_files(root/'raw.bin', root/'meta.json', root/'manifest.json', root/'events.log')

    def test_partial_only_complete_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_run(root)
            raw = root/'raw.bin'
            raw.write_bytes(raw.read_bytes()[:64 + 16 + 128*32 + 16 + 30])
            with self.assertRaises(ValueError):
                list(RawReader(raw))
            out = convert_run(raw, root/'meta.json', root/'out', recuperar_parcial=True)
            meta = load_json(out.with_suffix('.json'))
            self.assertEqual(meta['fim_firmware']['amostras_gravadas'], 128)
            self.assertFalse(meta['captura_completa'])
            self.assertFalse(meta['integridade_transferencia_verificada'])
            self.assertTrue(meta['recuperacao_parcial'])

    def test_manual_stop_is_not_approved_as_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_run(root, reason='comando_stop')
            out = convert_run(root/'raw.bin', root/'meta.json', root/'out', root/'manifest.json', root/'events.log')
            from comum import ler, exigir_continuidade
            with self.assertRaisesRegex(ValueError, 'incompleto'):
                exigir_continuidade(ler(out))

    def test_wrong_footer_and_trailing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_run(root)
            raw = root/'raw.bin'
            raw.write_bytes(raw.read_bytes() + b'X')
            with self.assertRaisesRegex(ValueError, 'Rodape'):
                list(RawReader(raw))

    def test_native_codec_cross_language(self):
        compiler = shutil.which('g++')
        if not compiler:
            self.skipTest('g++ ausente; execute o teste nativo em um ambiente com compilador C++.')
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp)/'native'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', str(ROOT/'tests/native_format.cpp'), '-o', str(exe)], check=True, capture_output=True)
            raw = Path(tmp)/'cpp.bin'
            subprocess.run([str(exe), str(raw)], check=True, capture_output=True)
            reader = RawReader(raw)
            rows = [row for block in reader for row in block]
            self.assertTrue(reader.complete)
            self.assertEqual(rows[0][2:5], (-524288, 524287, -1))

    def test_web_javascript_syntax(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js ausente para verificacao de sintaxe JS.')
        text = (ROOT/'firmware/adxl355_wifi_sd/web_ui.h').read_text()
        script = text.split('<script>', 1)[1].split('</script>', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'ui.js'
            p.write_text(script)
            subprocess.run([node, '--check', str(p)], check=True, capture_output=True)

    def test_firmware_metadata_serialization(self):
        compiler = shutil.which('g++')
        if not compiler:
            self.skipTest('g++ ausente para verificar o serializador C++.')
        with tempfile.TemporaryDirectory() as tmp:
            exe, output = Path(tmp)/'metadata', Path(tmp)/'meta.json'
            result = subprocess.run([compiler, '-std=c++17', '-I'+str(ROOT/'tests/native_stubs'),
                str(ROOT/'tests/native_metadata.cpp'), '-o', str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(exe), str(output)], check=True)
            meta = load_json(output)
            self.assertEqual(meta['devid_ad'], 0xAD)
            self.assertEqual(meta['partid'], 0xED)
            self.assertEqual(meta['nota'], 'linha 1\nlinha "2" e \\ final')
            self.assertEqual(meta['configuracao']['gpio_sd_miso'], 18)
            self.assertTrue(meta['captura_completa'])
            self.assertFalse(meta['sincronismo_entre_nos_validado'])


class Wireless(unittest.TestCase):
    def test_capture_resume_hash_and_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, manifest = make_run(root/'remote', count=10000)
            state = {'request_id': '', 'ocupado': False, 'estado': 'concluido',
                     'sequencia_ids': ['SINTETICO_0001'], 'run_id': 'SINTETICO_0001', 'amostras_gravadas': 10000}
            events = dict(ack=0, starts=0, offsets=[], disconnected=False)
            files = {'bin': 'raw.bin', 'meta': 'meta.json', 'manifest': 'manifest.json', 'log': 'events.log'}

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def response(self, obj):
                    data = json.dumps(obj).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

                def do_GET(self):
                    parsed = urllib.parse.urlparse(self.path)
                    if parsed.path == '/api/status':
                        return self.response(state)
                    if parsed.path == '/api/info':
                        return self.response({'sensor_pronto': True})
                    if parsed.path == '/api/files':
                        return self.response({'arquivos': [{'id': 'SINTETICO_0001', 'finalizado': True}], 'mais': False})
                    q = urllib.parse.parse_qs(parsed.query)
                    kind, offset = q['kind'][0], int(q['offset'][0])
                    data = (root/'remote'/files[kind]).read_bytes()[offset:]
                    if kind == 'bin':
                        events['offsets'].append(offset)
                    self.send_response(206 if offset else 200)
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    if kind == 'bin' and not events['disconnected']:
                        events['disconnected'] = True
                        self.wfile.write(data[:90000])
                        self.wfile.flush()
                        self.close_connection = True
                        return
                    self.wfile.write(data)

                def do_POST(self):
                    q = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get('Content-Length', '0'))).decode())
                    if self.path == '/api/start':
                        rid = q['request_id'][0]
                        if state['request_id'] != rid:
                            events['starts'] += 1
                        state['request_id'] = rid
                        return self.response(state)
                    if self.path == '/api/ack':
                        self.assert_hash = q['sha256'][0]
                        if self.assert_hash == manifest['raw_sha256']:
                            events['ack'] += 1
                        return self.response({'recebimento_registrado': True})
                    self.response({'hora_recebida': True})

            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                node = Node(f'127.0.0.1:{server.server_port}', timeout=2)
                result = capture(node, {'duracao_s': 20, 'ensaio': 'dinamico', 'request_id': 'teste'}, root/'local', on_status=None)
                self.assertEqual(len(result), 1)
                self.assertTrue(load_json(result[0].with_suffix('.json'))['captura_completa'])
                self.assertEqual(events['starts'], 1)
                self.assertEqual(events['ack'], 1)
                self.assertTrue(any(n > 0 for n in events['offsets']))
                node.start({'request_id': 'teste'})
                self.assertEqual(events['starts'], 1)
                self.assertEqual(node.files()[0]['id'], 'SINTETICO_0001')
            finally:
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    unittest.main()

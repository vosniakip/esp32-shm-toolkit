"""Protecoes da campanha e exercicio numerico de dois registros completos de 20 min."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
sys.path.insert(0, str(ROOT / 'tests'))
import passarela_ufpr as campaign
from fabrica_sd import make_run
from formato_sd import convert_run, load_json, save_json, sha256


def calibration(path):
    data = dict(formato='calibracao_adxl355_matriz_v1', sensor_modelo='ADXL355',
                identificacao_sensor='adxl355-sintetico', montagem='pcb-inclinada-sintetica',
                ordem_eixos=list('xyz'), referencial_saida=dict(nome='conjunto', mao_direita=True),
                faixa_g=2, configuracao_calibracao=dict(fs_nominal_hz=500, lpf_hz=125, hpf=0),
                offset_lsb=dict(x=0, y=0, z=0), status='ajustada_nao_validada',
                matriz_correcao_g_lsb=[[1/256000, 0, 0], [0, 1/256000, 0], [0, 0, 1/256000]],
                gravidade_referencia_ms2=9.7876,
                nota='CALIBRACAO SINTETICA PARA TESTE, NAO USAR NO HARDWARE.')
    save_json(data, path)
    return path


class FakeNode:
    def __init__(self, root, count=1000):
        self.root = Path(root)
        self.count = count
        self.starts = 0
        self.fail_post = False
        self.fail_download = False
        self.current = dict(ocupado=False, estado='ocioso')
        self.params = None

    def status(self):
        return dict(self.current)

    def info(self):
        return dict(sensor_pronto=True, sd_pronto=True, tarefas_prontas=True,
                    sd_livre_bytes_ultima_consulta=1_000_000_000)

    def clock(self):
        return {'ok': True}

    def start(self, params):
        self.starts += 1
        self.params = dict(params)
        self.current = dict(ocupado=True, estado='gravando', request_id=params['request_id'],
                            run_id=f'SINTETICO_{self.starts:04d}')
        if self.fail_post:
            raise TimeoutError('SINTETICO: resposta de START perdida depois de aceito.')
        return {'aceito': True}

    def conclude(self, reason='tempo_concluido'):
        self.current.update(ocupado=False, estado='concluido' if reason == 'tempo_concluido' else 'falha', motivo=reason)

    def download_run(self, run, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        if self.fail_download:
            (folder / 'raw.bin.download.part').write_bytes(b'SINTETICO')
            self.fail_download = False
            raise ConnectionError('SINTETICO: transferencia interrompida, sem novo START.')
        meta, manifest = make_run(folder, count=self.count, run=run, phase=.17 * self.starts)
        meta.update({key: self.params[key] for key in ('sensor', 'montagem', 'ensaio', 'posicao',
                                                    'repeticao', 'request_id', 'calibracao_id')})
        meta['duracao_solicitada_s'] = 1200
        save_json(meta, folder / 'meta.json')
        manifest['meta_sha256'] = sha256(folder / 'meta.json')
        save_json(manifest, folder / 'manifest.json')
        return convert_run(folder / 'raw.bin', folder / 'meta.json', folder,
                           folder / 'manifest.json', folder / 'events.log')


class Campaign(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cal = calibration(self.root / 'cal.json')
        with contextlib.redirect_stdout(io.StringIO()):
            self.path = campaign.prepare(self.cal, self.root / 'campanhas')
        self.node = FakeNode(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def start(self, pid='P01', **kw):
        with contextlib.redirect_stdout(io.StringIO()):
            return campaign.start(self.path, pid, node=self.node, **kw)

    def test_plan_exactly_two_points_twenty_minutes_no_recalibration(self):
        _, state = campaign.load_campaign(self.path)
        self.assertEqual(set(state['pontos']), {'P01', 'P02'})
        self.assertEqual(state['calibracao']['sha256'], sha256(self.cal))
        self.assertEqual((self.path.parent / 'calibracao/calibracao.json').read_bytes(), self.cal.read_bytes())
        for pid, point in state['pontos'].items():
            self.assertEqual(point['perfil']['duracao_s'], 1200)
            self.assertEqual(point['perfil']['repeticoes'], 1)
            self.assertEqual(point['perfil']['posicao'], pid)
        self.assertIsNone(state['geometria']['vao_v1_m'])
        self.assertEqual(self.node.starts, 0)

    def test_changed_calibration_rejected_before_network(self):
        (self.path.parent / 'calibracao/calibracao.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'alterada'):
            self.start(confirmed=True)
        self.assertEqual(self.node.starts, 0)

    def test_confirmation_and_point_order_do_not_send_start(self):
        with self.assertRaisesRegex(ValueError, 'Confirme'):
            self.start()
        with self.assertRaisesRegex(ValueError, 'P01'):
            self.start('P02', confirmed=True)
        self.assertEqual(self.node.starts, 0)

    def test_post_uncertain_can_recover_but_never_reposts(self):
        self.node.fail_post = True
        with self.assertRaisesRegex(RuntimeError, 'incerto'):
            self.start(confirmed=True)
        _, state = campaign.load_campaign(self.path)
        self.assertEqual(state['pontos']['P01']['tentativas'][0]['estado'], 'start_incerto')
        with self.assertRaisesRegex(ValueError, 'incerto'):
            self.start(confirmed=True, repeat=True, reason='nao sei se gravou')
        with contextlib.redirect_stdout(io.StringIO()):
            campaign.status(self.path, node=self.node)
        self.assertEqual(self.node.starts, 1)

    def test_short_capture_is_rejected_even_when_metadata_says_1200(self):
        self.start(confirmed=True)
        self.node.conclude()
        with self.assertRaisesRegex(ValueError, 'Duracao observada'):
            campaign.download(self.path, 'P01', node=self.node)
        _, state = campaign.load_campaign(self.path)
        self.assertEqual(state['pontos']['P01']['tentativas'][0]['estado'], 'rejeitado')
        self.assertIsNone(state['pontos']['P01']['tentativa_aceita'])

    def test_download_retry_uses_same_attempt_and_never_starts(self):
        self.start(confirmed=True)
        self.node.conclude()
        self.node.fail_download = True
        with self.assertRaises(ConnectionError):
            campaign.download(self.path, 'P01', node=self.node)
        with self.assertRaisesRegex(ValueError, 'pendente'):
            self.start(confirmed=True)
        # A segunda transferencia chega, mas o fixture curto nao pode passar como 20 min.
        with self.assertRaisesRegex(ValueError, 'Duracao observada'):
            campaign.download(self.path, 'P01', node=self.node)
        self.assertEqual(self.node.starts, 1)

    def test_second_point_not_started_automatically(self):
        self.start(confirmed=True)
        self.node.conclude()
        with patch.object(campaign, 'verify_capture', return_value={'csv_sha256': 'SINTETICO'}):
            with contextlib.redirect_stdout(io.StringIO()):
                campaign.download(self.path, 'P01', node=self.node)
        self.assertEqual(self.node.starts, 1)
        _, state = campaign.load_campaign(self.path)
        self.assertEqual(state['pontos']['P02']['tentativas'], [])
        self.start('P02', confirmed=True)
        self.node.conclude()
        # Nem uma repeticao de P01 pode substituir um P02 ainda nao recuperado.
        with self.assertRaisesRegex(ValueError, 'P02'):
            self.start('P01', confirmed=True, repeat=True, reason='teste')
        self.assertEqual(self.node.starts, 2)


class FullDuration(unittest.TestCase):
    def test_two_real_size_synthetic_records_and_analysis(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            path = campaign.prepare(calibration(root / 'cal.json'), root / 'campanhas')
            node = FakeNode(root, count=600000)
            for pid in ('P01', 'P02'):
                campaign.start(path, pid, confirmed=True, node=node)
                node.conclude()
                csv_path = campaign.download(path, pid, node=node)
                self.assertTrue(csv_path.exists())
            result = campaign.analyze(path)
            summary = load_json(result / 'resumo_campanha.json')
            self.assertEqual(len(summary['arquivos']), 2)
            self.assertFalse(summary['fase_entre_pontos_estimada'])
            self.assertFalse(summary['formas_modais_espaciais_estimadas'])
            self.assertTrue(all(abs(v['duracao_s'] - 1199.998) < 1e-6 for v in summary['arquivos']))
            import pandas as pd
            pairs = pd.read_csv(Path(summary['consolidacao']) / 'frequencias_para_revisao.csv')
            common = pairs[(pairs.n_pontos == 2) & ((pairs.f_media_hz - 7.5).abs() < .04)]
            self.assertGreater(len(common), 0)
            self.assertTrue((result / 'comparacao_psd_pontos.png').exists())
            self.assertEqual(node.starts, 2)
            print('SINTETICO: dois arquivos de 600000 amostras, 1200 s, pico 7,5 Hz; nenhum hardware conectado.')


if __name__ == '__main__':
    unittest.main()

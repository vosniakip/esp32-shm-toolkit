import binascii,json,os,select,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.name=='posix','PTY disponivel no teste POSIX')
class SerialVirtual(unittest.TestCase):
    def simular(self,mode):
        import pty
        master,slave=pty.openpty(); port=os.ttyname(slave); stop=threading.Event(); errors=[]
        def device():
            pending=b''
            try:
                while not stop.is_set():
                    if not select.select([master],[],[],.1)[0]: continue
                    pending+=os.read(master,8192)
                    while b'\n' in pending:
                        cmd,pending=pending.split(b'\n',1)
                        if cmd.strip()==b'INFO': os.write(master,b'#INFO,formato=ADXL355_S3_V1,pronto=1,sensor_modelo=ADXL355,faixa_g=2,sensibilidade_lsb_g=256000,fs_nominal_hz=500,lpf_hz=125,hpf=0\n')
                        if cmd.startswith(b'START,'):
                            os.write(master,b'#START,duracao_ms=100\n')
                            if mode=='sem_drdy': os.write(master,b'#END,motivo=sem_drdy,enviadas=0,perdidas=0,erros_spi=0,eventos_drdy=0\n'); continue
                            for i in range(50):
                                line=f'D,{i},{(i+1)*2000},2,-3,256000,1885,0,0,0,0'; crc=binascii.crc_hqx(line.encode(),0xFFFF)
                                if mode=='crc' and i==20: crc^=1
                                packet=(line+f',{crc:04X}\n').encode()
                                if i==0: os.write(master,packet[:8]); time.sleep(.15); os.write(master,packet[8:])
                                else: os.write(master,packet)
                            os.write(master,b'#END,motivo=tempo_concluido,enviadas=50,perdidas=0,erros_spi=0,eventos_drdy=50\n')
            except Exception as e: errors.append(str(e))
        th=threading.Thread(target=device,daemon=True); th.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                p=subprocess.run([sys.executable,str(ROOT/'python/01_capturar.py'),'--porta',port,'--duracao','.1','--ensaio','virtual','--espera-reset','0','--saida-raiz',tmp,'--montagem','TESTE_M1','--referencial','conjunto'],capture_output=True,text=True,timeout=20)
                js=list(Path(tmp).rglob('aquisicao.json')); self.assertEqual(len(js),1,p.stdout+p.stderr); meta=json.loads(js[0].read_text()); self.assertFalse(errors)
                self.assertEqual(p.returncode,0 if mode=='ok' else 1,p.stdout+p.stderr); self.assertEqual(meta['captura_completa'],mode=='ok'); self.assertEqual(meta['linhas_invalidas'],1 if mode=='crc' else 0)
                if mode=='ok':
                    self.assertEqual(meta['amostras_recebidas'],50)
                    self.assertEqual(meta['montagem'],'TESTE_M1'); self.assertEqual(meta['referencial_posicao'],'conjunto')
                    self.assertEqual(meta['versao_pacote'],'2.0.0')
                self.assertTrue(js[0].with_suffix('.csv').exists()); self.assertTrue(meta['csv_sha256'])
        finally: stop.set(); th.join(2); os.close(master); os.close(slave)
    def test_sucesso_fragmentado(self): self.simular('ok')
    def test_crc_preserva_parcial(self): self.simular('crc')
    def test_sem_drdy_preserva_log(self): self.simular('sem_drdy')
if __name__=='__main__': unittest.main()

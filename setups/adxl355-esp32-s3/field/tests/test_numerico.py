import binascii,sys,tempfile,unittest
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import welch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from analises import allan_sobreposto
from comum import COLUNAS,FORMATO,converter,exigir_continuidade,integrar_psd,ler,nova_pasta,salvar_json,sha256
class Numerico(unittest.TestCase):
    def test_allan_direto(self):
        v=np.random.default_rng(77).normal(size=1200)+1e3
        for tau,adev,npairs,nblocks in allan_sobreposto(v,500,pontos=15):
            m=round(tau*500); diff=np.array([v[i+m:i+2*m].mean()-v[i:i+m].mean() for i in range(len(v)-2*m+1)])
            self.assertAlmostEqual(adev,np.sqrt(.5*np.mean(diff**2)),places=11); self.assertEqual(npairs,len(diff))
    def test_psd_branco(self):
        fs=500; sigma=.001; v=np.random.default_rng(443).normal(0,sigma,500000)
        f,p=welch(v,fs=fs,nperseg=8192,window='hann',noverlap=4096,scaling='density')
        self.assertAlmostEqual(integrar_psd(f,p,0,fs/2)/sigma,1,delta=.015)
        self.assertAlmostEqual(integrar_psd(f,p,10,40)/np.sqrt(30)/(sigma*np.sqrt(2/fs)),1,delta=.025)
    def test_unidades_hash_lacuna(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'aquisicao.csv'; a=np.zeros((10,len(COLUNAS)),dtype=int); a[:,0]=np.arange(10); a[:,1]=np.arange(1,11)*2000; a[:,4]=256000; a[:,5]=1885
            pd.DataFrame(a,columns=COLUNAS).to_csv(p,index=False)
            salvar_json(dict(formato=FORMATO,sensor='ADXL355-01',captura_completa=True,linhas_invalidas=0,configuracao=dict(faixa_g=2,sensibilidade_lsb_g=256000,fs_nominal_hz=500),csv_sha256=sha256(p)),p.with_suffix('.json'))
            d=converter(ler(p)); self.assertTrue((d.az_g==1).all()); self.assertTrue((d.temp_c==25).all()); self.assertAlmostEqual(exigir_continuidade(d),500,places=9)
            d.loc[d.index[-1],'indice']+=1
            with self.assertRaises(ValueError): exigir_continuidade(d)
            p.write_text(p.read_text().replace('256000','260000'))
            with self.assertRaisesRegex(ValueError,'alterado'): ler(p)
    def test_pastas_unicas(self):
        with tempfile.TemporaryDirectory() as tmp: self.assertEqual(len({nova_pasta(tmp,'ensaio') for _ in range(25)}),25)
if __name__=='__main__': unittest.main()

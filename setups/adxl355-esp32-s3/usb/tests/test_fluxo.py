"""Teste de todos os analisadores com parametros conhecidos; sem hardware."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from comum import COLUNAS,FORMATO,salvar_json,sha256
ROOT=Path(__file__).resolve().parents[1]
class Fluxo(unittest.TestCase):
    def test_fluxo_completo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); rng=np.random.default_rng(1234); offsets=np.array([120.,-200.,750.]); sensitivities=np.array([253000.,258000.,255000.])
            def salvar(name,v,position='zpos',temp=None):
                p=root/'brutos'/name/'aquisicao.csv'; p.parent.mkdir(parents=True); n=len(v); a=np.zeros((n,len(COLUNAS)),dtype=np.int64)
                a[:,0]=np.arange(n); a[:,1]=np.arange(1,n+1)*2000; a[:,2:5]=np.rint(offsets+v*sensitivities); a[:,5]=1885 if temp is None else np.rint(temp)
                pd.DataFrame(a,columns=COLUNAS).to_csv(p,index=False)
                salvar_json(dict(formato=FORMATO,sensor='ADXL355-SINTETICO',posicao=position,captura_completa=True,linhas_invalidas=0,csv_sha256=sha256(p),configuracao=dict(faixa_g=2,sensibilidade_lsb_g=256000,fs_nominal_hz=500,lpf_hz=125,hpf=0)),p.with_suffix('.json')); return p
            positions=[]
            for j,e in enumerate('xyz'):
                for sign,suffix in [(1,'pos'),(-1,'neg')]:
                    for rep in range(3):
                        v=rng.normal(0,.00004,(6000,3)); v[:,j]+=sign; positions.append(salvar(f'cal_{e}{suffix}_{rep}',v,e+suffix))
            noises=[]
            for i in range(5):
                v=rng.normal(0,.001,(30000,3)); v[:,2]+=1; noises.append(salvar(f'noise_{i}',v))
            t=np.arange(60000)/500; v=rng.normal(0,.0001,(len(t),3)); v[:,2]+=1+.02*np.sin(2*np.pi*7.5*t); dyn=salvar('dinamico',v)
            v=rng.normal(0,.00005,(len(t),3)); v[:,2]+=1+.000002*t; thermal=salvar('termica',v,temp=1885-.2*t); outputs=root/'resultados'
            def run(script,paths,extra=(),expected=0):
                dest=outputs/script[:2]; cmd=[sys.executable,str(ROOT/'python'/script),*map(str,paths),'--saida',str(dest),*map(str,extra)]
                p=subprocess.run(cmd,capture_output=True,text=True,timeout=120); self.assertEqual(p.returncode,expected,p.stdout+'\n'+p.stderr)
                out=sorted(dest.iterdir())[-1]; self.assertEqual(json.loads((out/'analise.json').read_text())['status'],'concluida' if expected==0 else 'falhou'); return out
            out=run('03_calibrar_seis_posicoes.py',positions,['--modelo','diagonal']); cal=out/'calibracao.json'; c=json.loads(cal.read_text())
            np.testing.assert_allclose([c['offset_lsb'][e] for e in 'xyz'],offsets,atol=.5,rtol=0); np.testing.assert_allclose([c['sensibilidade_lsb_g'][e] for e in 'xyz'],sensitivities,atol=.5,rtol=0)
            first=run('02_verificar_funcional.py',[noises[0]],['--calibracao',cal]); second=run('02_verificar_funcional.py',[noises[0]]); self.assertNotEqual(first,second)
            out=run('04_analisar_ruido_psd.py',noises,['--calibracao',cal]); observed=pd.read_csv(out/'metricas_ruido.csv').densidade_equivalente_ug_raiz_hz.mean(); self.assertAlmostEqual(observed,.001*np.sqrt(2/500)*1e6,delta=2)
            run('05_analisar_temporizacao.py',[noises[0]]); run('06_analisar_repetibilidade.py',noises,['--calibracao',cal]); run('07_analisar_deriva_termica.py',[thermal],['--janela','10'])
            out=run('08_analisar_dinamico.py',[dyn],['--calibracao',cal]); m=pd.read_csv(out/'metricas_dinamicas.csv').iloc[0]; self.assertEqual(m.eixo,'Z'); self.assertAlmostEqual(m.frequencia_dominante_hz,7.5,delta=m.resolucao_espectral_hz); self.assertAlmostEqual(m.rms_filtrado_g,.02/np.sqrt(2),delta=.0004)
            run('09_desvio_allan.py',[noises[0]],['--pontos','20'])
            meta=json.loads(noises[0].with_suffix('.json').read_text()); meta['captura_completa']=False; salvar_json(meta,noises[0].with_suffix('.json')); run('04_analisar_ruido_psd.py',[noises[0]],expected=2); run('10_gerar_resumo.py',[outputs])
            for p in positions+noises+[dyn,thermal]: self.assertEqual(sha256(p),json.loads(p.with_suffix('.json').read_text())['csv_sha256'])
            for x in outputs.rglob('*.xlsx'): self.assertGreater(len(pd.read_excel(x)),0)
if __name__=='__main__': unittest.main()

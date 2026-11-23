"""Verifica ganhos, bias, rotacao, misturas e validacao independente conhecida."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from comum import COLUNAS,FORMATO,converter,ler,salvar_json,sha256
from modelos_calibracao import FORMATO_MATRIZ,ajustar_modelo,aplicar_matriz,avaliar_vetores


def resposta_conhecida():
    # Ganhos diferentes + inclinacao em dois planos + pequena mistura entre canais.
    x,y,z=np.deg2rad([4.,-3.,1.5])
    rx=np.array([[1,0,0],[0,np.cos(x),-np.sin(x)],[0,np.sin(x),np.cos(x)]])
    ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
    rz=np.array([[np.cos(z),-np.sin(z),0],[np.sin(z),np.cos(z),0],[0,0,1]])
    mix=np.eye(3); mix[0,1]=.002; mix[2,0]=-.001
    return np.diag([253856.,256179.,259909.])@mix@rz@ry@rx


class Modelo(unittest.TestCase):
    def test_recupera_matriz_offsets_e_vetores_fora_do_ajuste(self):
        a=resposta_conhecida(); b=np.array([325.,326.,-1484.])
        t=np.vstack((np.eye(3),-np.eye(3))); r=t@a.T+b
        fit=ajustar_modelo(r,t,256000)
        np.testing.assert_allclose(fit['matriz'],np.linalg.inv(a),rtol=1e-12,atol=1e-15)
        np.testing.assert_allclose(fit['offset'],b,rtol=0,atol=1e-8)
        rng=np.random.default_rng(73); other=rng.normal(size=(45,3)); other/=np.linalg.norm(other,axis=1)[:,None]
        np.testing.assert_allclose(aplicar_matriz(other@a.T+b,fit['matriz'],fit['offset']),other,atol=1e-12)

    def test_norma_nao_basta_para_validar_direcao(self):
        angle=np.deg2rad(7)
        m=avaliar_vetores(np.array([[np.sin(angle),0,np.cos(angle)]]),np.array([[0,0,1.]]))
        self.assertAlmostEqual(m['erro_norma_pct'][0],0,places=10)
        self.assertAlmostEqual(m['erro_angular_deg'][0],7,places=10)
        self.assertGreater(m['erro_vetorial_mg'][0],100)

    def test_recusa_referencias_sem_cobertura_e_reflexao(self):
        t=np.tile([0.,0.,1.],(6,1))
        with self.assertRaisesRegex(ValueError,'posto'): ajustar_modelo(t*256000,t,256000)
        t=np.vstack((np.eye(3),-np.eye(3))); raw=t@np.diag([-256000,256000,256000])
        with self.assertRaisesRegex(ValueError,'invertidas'): ajustar_modelo(raw,t,256000)


class FluxoMatriz(unittest.TestCase):
    def test_matriz_em_todas_analises_e_validacao(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); rng=np.random.default_rng(20261005); a=resposta_conhecida(); b=np.array([325.,326.,-1484.])
            original_hashes={}
            refs=json.loads((ROOT/'fichas/orientacoes_calibracao.json').read_text())['orientacoes']
            vrefs=json.loads((ROOT/'fichas/orientacoes_validacao.json').read_text())['orientacoes']
            def salvar(name,v,position='zpos',rep=1):
                p=root/'brutos'/name/'aquisicao.csv'; p.parent.mkdir(parents=True)
                n=len(v); values=np.zeros((n,len(COLUNAS)),dtype=np.int64)
                values[:,0]=np.arange(n); values[:,1]=(np.arange(n)+1)*2000
                values[:,2:5]=np.rint(np.asarray(v)@a.T+b); values[:,5]=1885
                pd.DataFrame(values,columns=COLUNAS).to_csv(p,index=False)
                salvar_json(dict(formato=FORMATO,sensor='ADXL355-MATRIZ-TESTE',montagem='TESTE_M1',
                                  referencial_posicao='conjunto',posicao=position,repeticao=rep,
                                  captura_completa=True,linhas_invalidas=0,csv_sha256=sha256(p),
                                  configuracao=dict(faixa_g=2,sensibilidade_lsb_g=256000,fs_nominal_hz=500,lpf_hz=125,hpf=0)),p.with_suffix('.json'))
                original_hashes[p]=sha256(p); return p
            def run(script,inputs,extra=(),expected=0):
                dest=root/'resultados'/script[:2]
                before=set(dest.iterdir()) if dest.exists() else set()
                result=subprocess.run([sys.executable,str(ROOT/'python'/script),*map(str,inputs),'--saida',str(dest),*map(str,extra)],
                                      capture_output=True,text=True,timeout=120)
                self.assertEqual(result.returncode,expected,result.stdout+'\n'+result.stderr)
                fresh=set(dest.iterdir())-before; self.assertEqual(len(fresh),1)
                out=fresh.pop(); j=json.loads((out/'analise.json').read_text())
                self.assertEqual(j['status'],'concluida' if expected==0 else 'falhou')
                return out
            poses=[]
            for label,ref in refs.items():
                for rep in range(1,4):
                    v=rng.normal(0,.00004,(4000,3))+ref['direcao']
                    poses.append(salvar(f'cal_{label}_{rep}',v,label,rep))
            out=run('03_calibrar_matriz_completa.py',poses); cal=out/'calibracao.json'; j=json.loads(cal.read_text())
            self.assertEqual(j['formato'],FORMATO_MATRIZ)
            np.testing.assert_allclose(j['matriz_correcao_g_lsb'],np.linalg.inv(a),rtol=0,atol=3e-11)
            np.testing.assert_allclose([j['offset_lsb'][e] for e in 'xyz'],b,atol=.5,rtol=0)
            valid=[]
            for label,ref in vrefs.items():
                valid.append(salvar('val_'+label,rng.normal(0,.00004,(5000,3))+ref['direcao'],label))
            vout=run('11_validar_calibracao.py',valid,['--calibracao',cal])
            report=json.loads((vout/'validacao_calibracao.json').read_text())
            self.assertTrue(report['resumo']['atende_metas_exploratorias'])
            self.assertLess(report['resumo']['erro_vetorial_max_mg'],.02)
            run('11_validar_calibracao.py',poses,['--calibracao',cal,'--referencias',ROOT/'fichas/orientacoes_calibracao.json'],expected=2)
            # Mesmo modulo correto, porem uma pose de validacao sete graus errada.
            bad=[*valid]
            angle=np.deg2rad(7); rot=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
            wrong=np.asarray(vrefs['xypos']['direcao'])@rot.T
            bad[0]=salvar('val_pose_errada',rng.normal(0,.00004,(5000,3))+wrong,'xypos')
            badout=run('11_validar_calibracao.py',bad,['--calibracao',cal])
            badreport=json.loads((badout/'validacao_calibracao.json').read_text())
            self.assertFalse(badreport['resumo']['atende_metas_exploratorias'])
            self.assertGreater(badreport['resumo']['erro_angular_max_deg'],6.9)
            noises=[]
            for rep in range(1,4):
                v=rng.normal(0,.001,(12000,3)); v[:,2]+=1
                noises.append(salvar(f'ruido_{rep}',v,rep=rep))
            run('02_verificar_funcional.py',[noises[0]],['--calibracao',cal])
            noiseout=run('04_analisar_ruido_psd.py',noises,['--calibracao',cal])
            noise=pd.read_csv(noiseout/'metricas_ruido.csv').densidade_equivalente_ug_raiz_hz.mean()
            self.assertAlmostEqual(noise,.001*np.sqrt(2/500)*1e6,delta=3)
            run('06_analisar_repetibilidade.py',noises,['--calibracao',cal])
            run('07_analisar_deriva_termica.py',[noises[0]],['--calibracao',cal,'--janela','4'])
            run('09_desvio_allan.py',[noises[0]],['--calibracao',cal,'--pontos','10'])
            t=np.arange(20000)/500; v=rng.normal(0,.00004,(len(t),3)); v[:,2]+=1+.02*np.sin(2*np.pi*7.5*t)
            dyn=salvar('dinamico',v,'barra')
            dynout=run('08_analisar_dinamico.py',[dyn],['--calibracao',cal,'--eixo','auto'])
            drow=pd.read_csv(dynout/'metricas_dinamicas.csv').iloc[0]
            self.assertEqual(drow.eixo,'Z'); self.assertAlmostEqual(drow.frequencia_dominante_hz,7.5,delta=.07)
            self.assertAlmostEqual(drow.rms_filtrado_g,.02/np.sqrt(2),delta=.0002)
            exported=run('12_exportar_corrigido.py',[dyn],['--calibracao',cal])
            exp=pd.read_csv(next(exported.glob('*_corrigido.csv')))
            np.testing.assert_allclose(exp[['ax_g','ay_g','az_g']],v,atol=8e-6,rtol=0)
            # Calibracao de outra fixacao/configuracao e recusada.
            meta=json.loads(dyn.with_suffix('.json').read_text()); wrongmeta=copy.deepcopy(meta); wrongmeta['montagem']='TESTE_M2'
            d=ler(dyn); d.attrs['metadados']=wrongmeta
            with self.assertRaisesRegex(ValueError,'outra montagem'): converter(d,cal)
            wrongmeta=copy.deepcopy(meta); wrongmeta['configuracao']['lpf_hz']=62.5
            d=ler(dyn); d.attrs['metadados']=wrongmeta
            with self.assertRaisesRegex(ValueError,'Configuracao'): converter(d,cal)
            legacy=ler(dyn); legacy.attrs['metadados'].pop('montagem')
            with self.assertRaisesRegex(ValueError,'confirmar-montagem'): converter(legacy,cal)
            converter(legacy,cal,'TESTE_M1')
            for p,h in original_hashes.items(): self.assertEqual(sha256(p),h)
            self.assertEqual(sha256(cal),report['calibracao_sha256'])

if __name__=='__main__': unittest.main()

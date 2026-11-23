import importlib.util
import json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import signal
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from campo import Trace,validate_trace,fit_sine,lowpass_on_grid
from metodos_campo import shaker,identify,fdd,compare_impulse
from frf_impacto import estimate_frf
from comum import sha256

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'python'/name)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
TIME=module('19_ajustar_tempo.py');IMPORT=module('18_importar_referencia.py')


class Campo(unittest.TestCase):
    def test_seno_escala_e_bases_tempo_distintas(self):
        tn=np.arange(0,60,1/501.7);tr=np.arange(0,60,1/1000)
        physical=11.37;b=1.0007
        n=Trace(tn,{'z':1.08*np.sin(2*np.pi*physical*b*tn)+9.8})
        r=Trace(tr,{'z':np.sin(2*np.pi*physical*tr)+.02})
        result,_,_=shaker(n,r,'z','z',physical)
        self.assertAlmostEqual(result['desvio_amplitude_rms_pct'],8.,delta=.02)
        self.assertAlmostEqual(result['desvio_f_no_ref_pct'],.07,delta=.003)
        self.assertFalse(result['fase_comparada'])

    def test_seno_curto_rejeitado(self):
        t=np.arange(0,10,.002)
        with self.assertRaisesRegex(ValueError,'20 ciclos'):fit_sine(t,np.sin(t),.5)

    def test_lacuna_e_nao_finitos_rejeitados(self):
        t=np.arange(100)*.002;t[50:]+=.01
        with self.assertRaisesRegex(ValueError,'Lacuna'):validate_trace(t,{'x':np.ones(100)})
        t=np.arange(100)*.002;x=np.ones(100);x[3]=np.nan
        with self.assertRaises(ValueError):validate_trace(t,{'x':x})

    def test_mapeamento_unidades_referencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);t=np.arange(1000)/1000
            pd.DataFrame({'tempo':t*1000+5000,'sensor':np.ones(1000)*.1}).to_csv(root/'orig.csv',sep=';',decimal=',',index=False)
            cfg=dict(instrumento_modelo='SINTETICO',separador=';',decimal=',',tempo_coluna='tempo',tempo_unidade='ms',
                     canais={'z':dict(coluna='sensor',unidade='V',fator_para_si=10,sinal=-1)})
            (root/'mapa.json').write_text(json.dumps(cfg))
            dest,meta=IMPORT.import_reference(root/'orig.csv',root/'mapa.json',root)
            d=pd.read_csv(dest);self.assertAlmostEqual(d.az_ms2.mean(),-1);self.assertAlmostEqual(d.tempo_s.iloc[0],0)
            self.assertEqual(meta['tempo_origem_s'],5)

    def test_pares_recuperam_offset_e_deriva(self):
        x=np.array([5,30,60,90,120.]);y=.43+1.0008*x
        result,res=TIME.fit_time_pairs(pd.DataFrame(dict(t_no_s=x,t_ref_s=y,u_par_s=np.ones(5)*.0002)))
        self.assertTrue(result['ajuste_valido']);self.assertAlmostEqual(result['a_s'],.43,places=9);self.assertAlmostEqual(result['deriva_relativa_ppm'],800,places=5)
        self.assertGreater(result['diagnostico_tempo_s'],0)
        y[2]+=.03
        result,_=TIME.fit_time_pairs(pd.DataFrame(dict(t_no_s=x,t_ref_s=y,u_par_s=np.ones(5)*.0002)))
        self.assertFalse(result['ajuste_valido'])

    def test_dois_pares_e_incerteza_nula_rejeitados(self):
        for n,u in [(2,.001),(3,0)]:
            with self.assertRaises(ValueError):TIME.fit_time_pairs(pd.DataFrame(dict(t_no_s=np.arange(n)*10,t_ref_s=np.arange(n)*10,u_par_s=np.ones(n)*u)))

    def test_fdd_sinal_vetorial_complexo(self):
        fs=200;t=np.arange(0,60,1/fs)
        x=np.c_[np.cos(2*np.pi*5*t),np.sin(2*np.pi*5*t)]
        f,s,v=fdd(x,fs,10);i=np.argmin(abs(f-5))
        self.assertGreater(s[i,0]/max(s[i,1],1e-30),1e6)
        # Convencao Sij=Xi*conj(Xj): o canal seno fica a -90 graus de cosseno.
        relative=v[i,1,0]/v[i,0,0]
        self.assertLess(relative.imag,-.9)

    def test_passarela_persistencia_e_cadencia(self):
        rng=np.random.default_rng(44);fs=250;t=np.arange(0,320,1/fs);components=[]
        for freq in [2.35,7.5]:
            r=.997
            x=signal.lfilter([1],[1,-2*r*np.cos(2*np.pi*freq/fs),r*r],rng.normal(size=len(t)))
            components.append(x/np.std(x))
        x=components[0]*.02;y=components[1]*.012
        tr=Trace(t,{'x':x+.3*y,'y':.2*x+y,'z':.8*x+.7*y})
        result,peaks,_,_=identify(tr,segment=24,blocks=4,cadences=[2.35],discard=2)
        main=peaks[(peaks.canal=='fdd1')&(abs(peaks.f_hz-7.5)<.15)]
        self.assertTrue(len(main)>0)
        self.assertGreaterEqual(main.persistencia.max(),.75)
        cadence=peaks[abs(peaks.f_hz-2.35)<.15]
        self.assertTrue((cadence.classificacao=='possivel_harmonico_da_excitacao').any())
        self.assertFalse(result['formas_modais_espaciais_estimadas'])

    def test_passarela_curta_rejeitada(self):
        t=np.arange(0,60,.004);tr=Trace(t,{'z':np.sin(2*np.pi*3*t)})
        with self.assertRaisesRegex(ValueError,'Registro curto'):identify(tr)

    def test_antialias_antes_grade_comum(self):
        t=np.arange(0,10,.001);grid=np.arange(1,9,.005)
        y=np.sin(2*np.pi*10*t)+np.sin(2*np.pi*150*t)
        z=lowpass_on_grid(t,y,grid)
        self.assertLess(np.sqrt(np.mean((z-np.sin(2*np.pi*10*grid))**2)),.003)

    def test_interpolacao_fracionaria_preserva_50_hz(self):
        t=np.arange(0,10,1/501.7);grid=np.arange(1.00329,9,.005)
        y=np.sin(2*np.pi*50*t)
        z=lowpass_on_grid(t,y,grid)
        self.assertLess(np.sqrt(np.mean((z-np.sin(2*np.pi*50*grid))**2)),.001)

    def test_comparacao_temporal_so_com_marcas(self):
        with tempfile.TemporaryDirectory() as tmp:
            nr=Path(tmp)/'no.csv';rr=Path(tmp)/'ref.csv';nr.write_text('SINTETICO_NO');rr.write_text('SINTETICO_REF')
            tn=np.arange(0,90,.002);tr=np.arange(0,90,.001);a=.4;b=1.0002
            def response(t):
                v=np.maximum(t-20,0);return np.where(t>=20,np.sin(2*np.pi*7.5*v)*np.exp(-v/7),0)
            n=Trace(tn,{'z':1.02*response(a+b*tn)},str(nr))
            r=Trace(tr,{'z':response(tr)},str(rr))
            res,_,_,_=compare_impulse(n,r,'z','z',(20-a)/b,20,post=40)
            self.assertFalse(res['comparacao_temporal']);self.assertNotIn('nrmse_pct',res)
            sync=dict(schema='TEMPO_AFIM_V4',ajuste_valido=True,a_s=a,b=b,dominio_no_s=[1,85],diagnostico_tempo_s=.0001,csv_no_sha256=sha256(nr),csv_ref_sha256=sha256(rr))
            res,_,_,_=compare_impulse(n,r,'z','z',event_r=20,post=40,sync=sync)
            self.assertTrue(res['comparacao_temporal']);self.assertAlmostEqual(res['nrmse_pct'],2.,delta=.15)
            self.assertGreater(res['correlacao'],.999)
            sync['dominio_no_s']=[1,30]
            with self.assertRaisesRegex(ValueError,'extrapolar'):compare_impulse(n,r,'z','z',event_r=20,sync=sync)

    def test_frf_ensemble_ganho_conhecido(self):
        fs=1000;t=np.arange(0,100,1/fs);force=np.zeros(len(t));times=[10,35,60,85]
        for i,ev in enumerate(times):force+= (1+.1*i)*np.exp(-((t-ev)/.0015)**2)
        ref=Trace(t,{'force':force,'z':2.5*force})
        data,quality,summary=estimate_frf(ref,pd.DataFrame(dict(t_ref_s=times,aceito=[1]*4)),pre=1,post=5,lo=1,hi=50)
        m=(data.f_hz>2)&(data.f_hz<40)&data.excitacao_suficiente
        np.testing.assert_allclose(data.loc[m,'h1_ref_ms2_n'],2.5,rtol=.0001)
        self.assertGreater(data.loc[m,'coerencia_ref'].min(),.999)
        self.assertEqual(summary['n_impactos_usados'],4)
        with self.assertRaisesRegex(ValueError,'tres impactos'):estimate_frf(ref,pd.DataFrame(dict(t_ref_s=times[:2],aceito=[1]*2)),pre=1,post=5)

if __name__=='__main__':unittest.main()

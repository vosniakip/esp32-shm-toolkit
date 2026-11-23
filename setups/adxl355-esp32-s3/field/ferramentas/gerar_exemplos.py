"""Gera sinais artificiais conhecidos. Nenhum arquivo e uma medicao real."""
from pathlib import Path
import argparse,json,sys
import numpy as np
import pandas as pd
from scipy import signal
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from comum import COLUNAS,FORMATO,salvar_json,sha256
from importlib.util import spec_from_file_location,module_from_spec
sp=spec_from_file_location('import_ref',ROOT/'python/18_importar_referencia.py');im=module_from_spec(sp);sp.loader.exec_module(im)


def node(dest,t,a):
    dest.mkdir(parents=True,exist_ok=False);n=len(t);v=np.zeros((n,len(COLUNAS)),np.int64)
    v[:,0]=np.arange(n);v[:,1]=np.rint(t*1e6);v[:,2:5]=np.rint(a/9.80665*256000);v[:,5]=1885
    p=dest/'aquisicao.csv';pd.DataFrame(v,columns=COLUNAS).to_csv(p,index=False)
    salvar_json(dict(formato=FORMATO,versao_pacote='4.0.0',sensor='ADXL355-SINTETICO',montagem='MONTAGEM-SINTETICA',ensaio='demonstracao',posicao='zpos',repeticao=1,referencial_posicao='sensor',
                     configuracao=dict(faixa_g=2,sensibilidade_lsb_g=256000,fs_nominal_hz=500,lpf_hz=125,hpf=0),captura_completa=True,linhas_invalidas=0,csv_sha256=sha256(p),
                     fim_firmware=dict(perdas=0,erros_spi=0),dados_sinteticos=True,nota='SINTETICO. Nao representa hardware ou resultado do TCC.'),p.with_suffix('.json'))
    return p


def reference(dest,t,a,force=None):
    dest.mkdir(parents=True,exist_ok=False)
    d=dict(Time=t,Acceleration=a)
    if force is not None:d['Force']=force
    source=dest/'exportacao_sintetica.csv';pd.DataFrame(d).to_csv(source,index=False)
    cfg=dict(instrumento_modelo='REFERENCIA-SINTETICA',certificado=None,tempo_coluna='Time',tempo_unidade='s',separador=',',decimal='.',canais={'z':dict(coluna='Acceleration',unidade='m/s2')})
    if force is not None:cfg['canais']['force']=dict(coluna='Force',unidade='N')
    cp=dest/'mapa.json';cp.write_text(json.dumps(cfg,indent=2));return im.import_reference(source,cp,dest)[0]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destino',default=str(ROOT/'exemplos/sintetico'));a=p.parse_args();out=Path(a.destino)
    out.mkdir(parents=True,exist_ok=False);rng=np.random.default_rng(20261104)
    tn=np.arange(0,60,1/501.7);tr=np.arange(0,60,.001);freq=11.37
    data=np.zeros((len(tn),3));data[:,2]=9.80665+1.08*np.sin(2*np.pi*freq*1.0007*tn)
    n=node(out/'shaker_no',tn,data);r=reference(out/'shaker_ref',tr,np.sin(2*np.pi*freq*tr))
    tn=np.arange(0,90,.002);tr=np.arange(0,90,.001)
    def response(t):
        v=np.maximum(t-20,0);return np.where(t>=20,np.sin(2*np.pi*7.5*v)*np.exp(-v/7),0)
    data=np.zeros((len(tn),3));data[:,2]=9.80665+1.02*response(.4+1.0002*tn)
    ni=node(out/'trelica_no',tn,data);ri=reference(out/'trelica_ref',tr,response(tr))
    x=np.array([5,10,40,65,85.]);pd.DataFrame(dict(t_no_s=x,t_ref_s=.4+1.0002*x,u_par_s=np.ones(5)*.0002)).to_csv(out/'pares_tempo.csv',index=False)
    fs=500;tt=np.arange(0,320,1/fs);components=[]
    for fr in [2.35,7.5]:
        radius=.998
        v=signal.lfilter([1],[1,-2*radius*np.cos(2*np.pi*fr/fs),radius*radius],rng.normal(size=len(tt)))
        components.append(v/np.std(v))
    x=components[0]*.02;y=components[1]*.012
    aa=np.c_[x+.3*y,.2*x+y,9.80665+.8*x+.7*y];nb=node(out/'passarela_no',tt,aa)
    # FRF conhecida: aceleracao=2.5*forca. Serve para conferir escala e coerencia do codigo.
    tf=np.arange(0,100,.001);force=np.zeros(len(tf));evs=[10,35,60,85]
    for i,ev in enumerate(evs):force+=(1+.1*i)*np.exp(-((tf-ev)/.0015)**2)
    rf=reference(out/'frf_ref',tf,2.5*force,force)
    pd.DataFrame(dict(evento=range(1,5),t_ref_s=evs,aceito=[1]*4,motivo=['']*4)).to_csv(out/'impactos.csv',index=False)
    salvar_json(dict(dados_sinteticos=True,shaker=dict(f_fisica_hz=freq,desvio_amplitude_pct=8,desvio_relogio_pct=.07),
                     trelica=dict(f_hz=7.5,desvio_amplitude_pct=2,a_s=.4,b=1.0002),passarela=dict(frequencias_hz=[2.35,7.5]),frf=dict(h1_ms2_n=2.5)),out/'verdade_conhecida.json')
    print(out.resolve())
if __name__=='__main__':main()

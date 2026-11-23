"""Reanálise auditável do ADXL355 sem fio a partir dos arquivos originais.

Uso: python analisar_wireless.py --dados PASTA_DADOS --calibracao-id ID --saida PASTA_SAIDA
Informe o identificador da calibração usada na sua campanha.
Os outros arquivos ZIP não são abertos. Dependências: numpy, pandas, scipy.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import zlib
from collections import Counter
from zipfile import ZipFile

import numpy as np
import pandas as pd
from scipy.linalg import polar
from scipy.signal import welch

G0 = 9.80665
POSES = {'xpos':[1,0,0], 'xneg':[-1,0,0], 'ypos':[0,1,0],
         'yneg':[0,-1,0], 'zpos':[0,0,1], 'zneg':[0,0,-1]}
HEADER = struct.Struct('<8sHHHHIIQ32s')
BLOCK = struct.Struct('<4sIHHI')
FOOTER = struct.Struct('<4sIQ')
DTYPE = np.dtype([('indice','<u8'), ('t_us','<u8'), ('ax_raw','<i4'),
                 ('ay_raw','<i4'), ('az_raw','<i4'), ('temp_raw','<i2'), ('flags','<u2')])

def readj(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def plain(v):
    if isinstance(v,dict):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)):return [plain(x) for x in v]
    if isinstance(v,np.generic):return plain(v.item())
    if isinstance(v,float) and not np.isfinite(v):return None
    if isinstance(v,Path):return str(v)
    return v

def writej(path,obj):
    path.write_text(json.dumps(plain(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def raw_records(path):
    """Confere CRC, ordem, cabeçalho e rodapé; não recupera trechos truncados."""
    parts=[];blocks=0;records=0
    with path.open('rb') as f:
        h=f.read(HEADER.size)
        magic,ver,hsize,rsize,res,rate,span,duration,run=HEADER.unpack(h)
        assert (magic,ver,hsize,rsize,res)==(b'A355SD3\0',3,64,32,0)
        assert rate in (250,500) and span in (2,4,8)
        while True:
            mark=f.read(4)
            if mark==b'END3':
                _,bc,nc=FOOTER.unpack(mark+f.read(12))
                assert bc==blocks and nc==records and not f.read(1)
                break
            assert mark==b'BLK3','Bloco ausente ou arquivo não finalizado'
            _,seq,count,size,crc=BLOCK.unpack(mark+f.read(12))
            assert seq==blocks and size==32 and 1<=count<=128
            payload=f.read(count*size)
            assert len(payload)==count*size and zlib.crc32(payload)==crc
            parts.append(np.frombuffer(payload,dtype=DTYPE).copy())
            records+=count;blocks+=1
    a=np.concatenate(parts)
    assert len(a)==records and a['indice'][0]==0
    assert np.all(np.diff(a['indice'].astype('i8'))>0)
    assert np.all(np.diff(a['t_us'].astype('i8'))>0) and a['t_us'][-1]<duration
    return a,blocks,run.split(b'\0',1)[0].decode('ascii')

def band_rms(f,p,lo,hi):
    mask=(f>lo)&(f<hi)
    x=np.r_[lo,f[mask],hi]
    y=np.r_[np.interp(lo,f,p),p[mask],np.interp(hi,f,p)]
    return np.sqrt(max(np.trapezoid(y,x),0))

def residual(raw,C,b,ref):
    acc=(raw-b)@C.T
    norms=np.linalg.norm(acc,axis=1)
    target=np.linalg.norm(ref,axis=1)
    angle=np.degrees(np.arccos(np.clip(np.sum(acc*ref,axis=1)/norms/target,-1,1)))
    return acc,np.linalg.norm(acc-ref,axis=1)*1000,(norms/target-1)*100,angle

def metrics(vec,norm,ang):
    return dict(erro_vetorial_rms_mg=np.sqrt(np.mean(vec**2)),
                erro_vetorial_max_mg=np.max(vec),
                erro_norma_max_abs_pct=np.max(np.abs(norm)),
                erro_angular_max_deg=np.max(ang))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dados',type=Path,default=Path(__file__).parent/'entrada/dados')
    parser.add_argument('--saida',type=Path,default=Path(__file__).parent/'trabalho/reanalise')
    parser.add_argument('--calibracao-id', required=True, help='Nome da pasta de calibração do conjunto em dados/calibracao.')
    args=parser.parse_args();root=args.dados;out=args.saida;out.mkdir(parents=True,exist_ok=True)
    cal_id=args.calibracao_id
    if Path(cal_id).name!=cal_id or cal_id in ('.','..'):
        parser.error('--calibracao-id deve ser o nome da pasta de calibração, sem caminho')
    cal_path=root/'calibracao'/cal_id/'calibracao.json'
    cal=readj(cal_path);C=np.array(cal['matriz_correcao_g_lsb']);b=np.array([cal['offset_lsb'][e] for e in 'xyz'])
    chosen_zip=root/'calibracao'/(cal_id+'.zip')
    if chosen_zip.exists():
        with ZipFile(chosen_zip) as z:
            names=[n for n in z.namelist() if n=='calibracao.json' or n.endswith('/calibracao.json')]
            assert len(names)==1 and z.read(names[0])==cal_path.read_bytes()
    S=np.linalg.inv(C);gref=cal['gravidade_referencia_ms2']/G0
    fit_hashes={r['csv_sha256'] for r in cal['arquivos_ajuste']}
    val_file=next((root/'processados/validacao').rglob('validacao_calibracao.json'))
    valj=readj(val_file)
    assert valj['calibracao_sha256']==sha(cal_path)
    val_hashes={r['csv_sha256'] for r in valj['arquivos_validacao']}
    assert not (fit_hashes&val_hashes)
    records=[];means=[];spectra=[];noise=[];cache={};byhash={}
    for p in sorted((root/'brutos').rglob('meta.json')):
        folder=p.parent;m=readj(p);manifest=readj(folder/'manifest.json')
        cm=readj(folder/'aquisicao.json');receipt=readj(folder/'recebimento.json')
        df=pd.read_csv(folder/'aquisicao.csv');ch=sha(folder/'aquisicao.csv')
        phase=('ajuste' if ch in fit_hashes else 'validacao_selecionada' if ch in val_hashes
               else 'ruido' if m['ensaio']=='ruido' else 'radio' if m['ensaio']=='validacao_wifi'
               else 'funcional' if m['ensaio']=='funcional' else 'outros_registros_arquivados')
        if phase=='outros_registros_arquivados':
            continue
        integrity={}
        for file,key in [('raw.bin','raw_sha256'),('meta.json','meta_sha256'),('events.log','log_sha256')]:
            integrity[key]=sha(folder/file)==manifest[key]
        integrity['csv_sha256']=ch==cm['csv_sha256']==receipt['csv_sha256']
        a,nblocks,run=raw_records(folder/'raw.bin')
        assert len(a)==len(df)==manifest['records']==m['amostras_gravadas']
        assert nblocks==manifest['blocks'] and run==m['run_id']
        assert (folder/'raw.bin').stat().st_size==manifest['raw_bytes']
        assert all(np.array_equal(a[k],df[k].to_numpy()) for k in DTYPE.names)
        assert all(integrity.values()),(folder,integrity)
        t=df.t_us.to_numpy(dtype=float);dt=np.diff(t);ix=df.indice.to_numpy(dtype=np.int64)
        raw=df[['ax_raw','ay_raw','az_raw']].to_numpy(dtype=float)
        sample=dict(run_id=run,pasta=str(folder.relative_to(root)),csv_sha256=ch,
                    raw_sha256=manifest['raw_sha256'],ensaio=m['ensaio'],grupo=phase,
                    posicao=m['posicao'],repeticao=m['repeticao'],radio=m['radio'],
                    n=len(df),duracao_s=(t[-1]-t[0])/1e6,fs_hz=(len(t)-1)*1e6/(t[-1]-t[0]),
                    dt_medio_us=np.mean(dt),dt_dp_us=np.std(dt,ddof=1),dt_min_us=dt.min(),dt_max_us=dt.max(),
                    jitter_pct=np.std(dt)/np.mean(dt)*100,lacunas_indice=np.sum(np.diff(ix)-1),
                    lacunas_temporais=np.sum(dt>1.5*np.median(dt)),
                    perdas=int(df.perdidas_acum.max()),erros_spi=int(df.erros_spi.max()),
                    descartes_fila=int(df.descartes_fila.max()),leituras_descartadas=int(df.leituras_descartadas.max()),
                    captura_completa=m['captura_completa'],buffer_pico=m['buffer_pico_registros'],
                    buffer_capacidade=m['buffer_capacidade_registros'],saturacao=bool((np.abs(raw)>=.98*524287).any()),
                    integridade_hashes=True,crc32_todos_blocos=True,csv_confere_binario=True)
        records.append(sample)
        keep=t-t[0]>=2e6;arr=raw[keep];trimt=t[keep]
        temp=25+(df.temp_raw.to_numpy()[keep]-1885)/-9.05
        mean=arr.mean(axis=0);cov=np.cov(arr,rowvar=False)
        corr=(arr-b)@C.T
        row=dict(run_id=run,csv_sha256=ch,grupo=phase,posicao=m['posicao'],repeticao=m['repeticao'],
                 temperatura_c=temp.mean(),n=len(arr),inicio_epoch_ms=m['epoch_inicio_ms'])
        for j,e in enumerate('xyz'):
            row['media_'+e+'_raw']=mean[j]
            row['media_'+e+'_g']=corr[:,j].mean()
            row['dp_'+e+'_g']=corr[:,j].std(ddof=1)
        means.append(row);byhash[ch]=row
        if phase in ('ruido','radio'):
            fs=(len(trimt)-1)*1e6/(trimt[-1]-trimt[0])
            for j,e in enumerate('XYZ'):
                f,psd=welch(corr[:,j],fs=fs,window='hann',nperseg=8192,noverlap=4096,detrend='constant',scaling='density')
                nrow=dict(run_id=run,grupo=phase,radio=m['radio'],eixo=e,
                          rms_banda_g=band_rms(f,psd,.5,50),
                          densidade_ug_raiz_hz=band_rms(f,psd,10,40)/np.sqrt(30)*1e6,
                          rms_baixa_g=band_rms(f,psd,.5,10),
                          media_g=corr[:,j].mean(),dp_g=corr[:,j].std(ddof=1),fs_hz=fs)
                noise.append(nrow)
                if phase=='ruido':
                    spectra.append(pd.DataFrame(dict(run_id=run,eixo=e,frequencia_hz=f,psd_g2_hz=psd)))
        if phase in ('ajuste','validacao_selecionada','funcional'):
            cache[run]=dict(means=mean,n=len(arr))
    rr=pd.DataFrame(records);mm=pd.DataFrame(means);nn=pd.DataFrame(noise)
    rr.to_csv(out/'integridade_e_temporizacao.csv',index=False)
    mm.to_csv(out/'medias_apos_descarte.csv',index=False)
    nn.to_csv(out/'metricas_espectrais_recalculadas.csv',index=False)
    pd.concat(spectra,ignore_index=True).to_csv(out/'psd_ruido.csv',index=False)
    # Reproduz o ajuste com peso igual para cada média de arquivo.
    fit=[byhash[h['csv_sha256']] for h in cal['arquivos_ajuste']]
    rf=np.array([[r['media_'+e+'_raw'] for e in 'xyz'] for r in fit])
    ref=np.array([POSES[r['posicao']] for r in fit])*gref
    X=np.column_stack((ref,np.ones(len(ref))))
    coeff=np.linalg.lstsq(X,rf,rcond=None)[0];S2=coeff[:3].T;b2=coeff[3];C2=np.linalg.inv(S2)
    assert np.allclose(C,C2,rtol=1e-10,atol=1e-16) and np.allclose(b,b2,rtol=1e-9,atol=1e-6)
    _,vf,nf,af=residual(rf,C,b,ref)
    valid=[byhash[h['csv_sha256']] for h in valj['arquivos_validacao']]
    rv=np.array([[r['media_'+e+'_raw'] for e in 'xyz'] for r in valid])
    refs=np.array([POSES[r['posicao']] for r in valid])*gref
    comparisons={};validation=None
    for label,mat,bias in [('nominal',np.eye(3)/256000,np.zeros(3)),('diagonal',np.diag(1/np.diag(S)),b),('matriz',C,b)]:
        acc,v,n,a=residual(rv,mat,bias,refs);comparisons[label]=metrics(v,n,a)
        if label=='matriz':
            validation=pd.DataFrame(valid)[['run_id','posicao','repeticao','temperatura_c']]
            validation['erro_vetorial_mg']=v;validation['erro_norma_pct']=n;validation['erro_angular_deg']=a
            for j,e in enumerate('xyz'):
                validation['a_'+e+'_g']=acc[:,j];validation['erro_'+e+'_mg']=(acc[:,j]-refs[:,j])*1000
    validation.to_csv(out/'validacao_recalculada.csv',index=False)
    position=validation.groupby('posicao').agg(erro_vetorial_medio_mg=('erro_vetorial_mg','mean'),
        erro_vetorial_max_mg=('erro_vetorial_mg','max'),erro_norma_medio_pct=('erro_norma_pct','mean'),
        erro_angular_max_deg=('erro_angular_deg','max'))
    position.to_csv(out/'validacao_por_posicao.csv')
    for k,v in metrics(vf,nf,af).items():assert np.isclose(v,cal['diagnostico_ajuste'][k],rtol=1e-7,atol=1e-7)
    for k,v in comparisons['matriz'].items():assert np.isclose(v,valj['resumo'][k],rtol=1e-7,atol=1e-7)
    ns=nn[nn.grupo=='ruido'].groupby('eixo').agg(rms_g=('rms_banda_g','mean'),rms_dp_g=('rms_banda_g','std'),
             densidade=('densidade_ug_raiz_hz','mean'),densidade_dp=('densidade_ug_raiz_hz','std'))
    ns['rms_cv_pct']=ns.rms_dp_g/ns.rms_g*100
    ns.to_csv(out/'ruido_resumo.csv')
    nr=rr[rr.grupo=='ruido'];nm=mm[mm.grupo=='ruido']
    original_noise=pd.read_csv(next((root/'processados/ruido').rglob('ruido_repeticoes.csv'))).set_index('eixo')
    assert np.allclose(ns.rms_g,original_noise.rms_banda_g_mean,rtol=1e-8)
    assert np.allclose(ns.densidade,original_noise.densidade_equivalente_ug_raiz_hz_mean,rtol=1e-8)
    modes=rr[rr.grupo=='radio'].groupby('radio').agg(n=('run_id','count'),amostras=('n','sum'),
        fs_media_hz=('fs_hz','mean'),fs_dp_hz=('fs_hz','std'),dt_dp_medio_us=('dt_dp_us','mean'),
        jitter_medio_pct=('jitter_pct','mean'),jitter_dp_pct=('jitter_pct','std'),buffer_max=('buffer_pico','max'))
    modes.to_csv(out/'radio_resumo.csv')
    failures=[]
    for p in (root/'brutos').rglob('estado_final.json'):
        j=readj(p)
        if j.get('estado')!='concluido':failures.append(dict(pasta=str(p.parent.relative_to(root)),**j))
    rotation,_=polar(S);rot_angle=np.degrees(np.arccos(np.clip((np.trace(rotation)-1)/2,-1,1)))
    gain=np.linalg.norm(S,axis=1)
    summary=dict(calibracao_utilizada=cal_id,sha256_calibracao=sha(cal_path),offset_lsb=b,
       offset_nominal_mg=b/256000*1000,ganhos_efetivos_lsb_g=gain,desvio_ganhos_pct=(gain/256000-1)*100,
       matriz_C=C,matriz_S=S,rotacao_polar_graus=rot_angle,gravidade_referencia_ms2=cal['gravidade_referencia_ms2'],
       gravidade_referencia_em_g0=gref,diagnostico_ajuste=metrics(vf,nf,af),validacao=comparisons,
       validacao_por_posicao=position.reset_index().to_dict('records'),
       temperatura_ajuste_c=[min(r['temperatura_c'] for r in fit),max(r['temperatura_c'] for r in fit)],
       temperatura_validacao_c=[min(r['temperatura_c'] for r in valid),max(r['temperatura_c'] for r in valid)],
       ruído=ns.reset_index().to_dict('records'),radio=modes.reset_index().to_dict('records'),
       ruido_taxa_media_hz=nr.fs_hz.mean(),ruido_taxa_dp_hz=nr.fs_hz.std(),
       ruido_dt_dp_medio_us=nr.dt_dp_us.mean(),ruido_taxa_erro_pct=(nr.fs_hz.mean()/500-1)*100,
       ruido_temperaturas_c=[nm.temperatura_c.min(),nm.temperatura_c.max()],
       medias_ruido_dp_mg={e:nm['media_'+e+'_g'].std()*1000 for e in 'xyz'},
       medias_ruido_amplitude_mg={e:np.ptp(nm['media_'+e+'_g'])*1000 for e in 'xyz'},
       medias_ruido_deslocamento_mg={e:(nm['media_'+e+'_g'].iloc[-1]-nm['media_'+e+'_g'].iloc[0])*1000 for e in 'xyz'},
       integridade=dict(arquivos_completos=len(rr),crc_ok=int(rr.crc32_todos_blocos.sum()),
       amostras_totais=int(rr.n.sum()),csv_distintos=rr.csv_sha256.nunique(),binarios_distintos=rr.raw_sha256.nunique(),
       amostras_por_grupo=rr.groupby('grupo').n.sum().to_dict(),arquivos_por_grupo=rr.grupo.value_counts().to_dict(),
       lacunas=int(rr.lacunas_indice.sum()),erros_spi=int(rr.erros_spi.max()),saturados=int(rr.saturacao.sum())),
       falhas_de_sequencia_documentadas=failures,
       politica='Verificação aplicada à calibração selecionada e aos registros de validação associados.',
       escopo='Reanálise da calibração, do ruído e do estado do rádio; não inclui ensaios de Allan, térmicos ou dinâmicos.')
    writej(out/'resumo.json',summary)
    print(json.dumps(plain({k:v for k,v in summary.items() if k not in ('validacao_por_posicao','falhas_de_sequencia_documentadas','matriz_S')}),ensure_ascii=False,indent=2))

if __name__=='__main__':main()

"""Calibracao estatica do conjunto montado e validacao em novos registros.

Nenhum coeficiente e enviado ao sensor. A placa/gabarito define o referencial.
A rigidez da montagem e a exatidao das poses continuam sendo requisitos fisicos.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from comum import (EIXOS, G0, VERSAO_PACOTE, carregar_json, salvar_json, sha256,
                   ler, exigir_continuidade, diagnostico, converter, tabela, plot_setup)
from modelos_calibracao import (FORMATO_MATRIZ, array_finito, aplicar_matriz,
                                ajustar_modelo, avaliar_vetores)


def normalizar_posicao(s):
    return str(s).lower().replace('+', 'pos').replace('-', 'neg')


def carregar_referencias(path):
    j = carregar_json(path)
    if j.get('formato') != 'orientacoes_conjunto_v1' or j.get('referencial') != 'conjunto':
        raise ValueError('Use um arquivo de referencias no formato orientacoes_conjunto_v1, referencial conjunto.')
    axes = j.get('descricao_eixos', {})
    if set(axes) != set(EIXOS) or any(not str(axes[e]).strip() for e in EIXOS):
        raise ValueError('Descreva os tres eixos do conjunto no arquivo de referencias.')
    refs = {}
    for name, item in j.get('orientacoes', {}).items():
        key = normalizar_posicao(name)
        direction = array_finito(item['direcao'], (3,), f'Direcao {name}')
        if abs(np.linalg.norm(direction) - 1) > 1e-6:
            raise ValueError(f'{name}: direcao deve ter norma 1. O programa nao normaliza referencias erradas.')
        if key in refs: raise ValueError('Etiquetas de posicao duplicadas.')
        refs[key] = direction
    if not refs: raise ValueError('Arquivo de referencias sem orientacoes.')
    return j, refs


def _conferir_parametros(args):
    for name in ('max_dp_mg', 'limite_vetorial_mg', 'limite_norma_pct', 'limite_angular_deg'):
        value = getattr(args, name)
        if not np.isfinite(value) or value <= 0: raise ValueError(f'{name}: informe um limite positivo finito.')
    if args.min_repeticoes < 1: raise ValueError('--min-repeticoes deve ser positivo.')


def _ler_medias(args, files, refs, calibracao=None):
    """Cada captura contribui com uma media, independentemente de sua duracao."""
    rows, fontes, sensores, montagens, configs = [], [], set(), set(), set()
    vistos, hashes = set(), set()
    for p in files:
        h = sha256(p)
        if h in hashes: raise ValueError('Duas entradas possuem o mesmo CSV; nao conte copias como repeticoes.')
        hashes.add(h)
        d = ler(p, args.descartar)
        exigir_continuidade(d)
        if diagnostico(d)['perto_limite_digital']: raise ValueError(f'Saturacao/proximidade do limite digital: {p}')
        m = d.attrs['metadados']; c = m['configuracao']
        pos = normalizar_posicao(m.get('posicao', ''))
        if pos not in refs: raise ValueError(f'Posicao {pos!r} ausente no arquivo de referencias: {p}')
        if m.get('referencial_posicao') != 'conjunto':
            raise ValueError(f'Captura sem referencial conjunto: {p}. Refaca as poses usando --referencial conjunto.')
        montagem = str(m.get('montagem', '')).strip()
        if not montagem: raise ValueError('Falta --montagem nas novas capturas de calibracao/validacao.')
        rep = int(m.get('repeticao', 0))
        if rep < 1 or (pos, rep) in vistos: raise ValueError(f'Repeticao ausente ou repetida na posicao {pos}.')
        vistos.add((pos, rep)); sensores.add(m['sensor']); montagens.add(montagem)
        configs.add((int(c['faixa_g']), float(c['fs_nominal_hz']), float(c['lpf_hz']), float(c['hpf'])))
        nominal = float(c['sensibilidade_lsb_g'])
        r = dict(arquivo=str(p),posicao=pos,repeticao=rep,n=len(d),csv_sha256=h,montagem=montagem)
        for e in EIXOS:
            r[f'media_a{e}_raw'] = float(d[f'a{e}_raw'].mean())
            r[f'dp_a{e}_raw'] = float(d[f'a{e}_raw'].std(ddof=1))
            if r[f'dp_a{e}_raw'] / nominal * 1000 > args.max_dp_mg:
                raise ValueError(f'{p}: dispersao elevada no eixo {e}. Confira movimento/deriva; --max-dp-mg e triagem pratica.')
        temp = d.loc[d.temp_raw >= 0, 'temp_raw']
        r['temperatura_media_c'] = 25 + (float(temp.mean())-1885)/-9.05 if len(temp) else None
        if calibracao:
            d = converter(d, args.calibracao, getattr(args, 'confirmar_montagem', None))
            for e in EIXOS:
                r[f'media_a{e}_corr_g'] = float(d[f'a{e}_g'].mean())
                r[f'dp_a{e}_corr_g'] = float(d[f'a{e}_g'].std(ddof=1))
        rows.append(r)
        fontes.append(dict(arquivo=str(p),csv_sha256=h,json_sha256=sha256(p.with_suffix('.json')),
                           posicao=pos,repeticao=rep))
    if len(sensores)!=1 or len(montagens)!=1 or len(configs)!=1:
        raise ValueError('Nao misture exemplares, montagens, faixas, taxas ou filtros.')
    df = pd.DataFrame(rows)
    sizes = df.groupby('posicao').size()
    missing = set(refs)-set(sizes.index)
    if missing: raise ValueError(f'Faltam orientacoes: {sorted(missing)}')
    if (sizes < args.min_repeticoes).any():
        raise ValueError(f'Use ao menos {args.min_repeticoes} arquivos por orientacao, com repeticoes distintas.')
    sensor, montagem, config = next(iter(sensores)), next(iter(montagens)), next(iter(configs))
    if getattr(args, 'sensor', None) and args.sensor != sensor: raise ValueError('--sensor difere das capturas.')
    return df, fontes, sensor, montagem, dict(faixa_g=config[0],fs_nominal_hz=config[1],lpf_hz=config[2],hpf=config[3])


def _residuos(df, corrected, targets):
    metrics = avaliar_vetores(corrected, targets)
    out = df[['arquivo','posicao','repeticao','n']].copy()
    for j,e in enumerate(EIXOS):
        out[f'a{e}_referencia_g'] = targets[:,j]
        out[f'a{e}_corr_g'] = corrected[:,j]
        out[f'erro_a{e}_mg'] = metrics['erros_g'][:,j] * 1000
    out['norma_g'] = metrics['normas_g']
    for key in ('erro_norma_pct','erro_vetorial_mg','erro_angular_deg'): out[key] = metrics[key]
    return out


def _resumir(res, args):
    cols = ['erro_vetorial_mg','erro_norma_pct','erro_angular_deg']
    finite = np.isfinite(res[cols].to_numpy()).all()
    dentro = bool(finite and (res.erro_vetorial_mg<=args.limite_vetorial_mg).all()
                  and (res.erro_norma_pct.abs()<=args.limite_norma_pct).all()
                  and (res.erro_angular_deg<=args.limite_angular_deg).all())
    return dict(arquivos=len(res),erro_vetorial_rms_mg=float(np.sqrt(np.mean(res.erro_vetorial_mg**2))),
                erro_vetorial_max_mg=float(res.erro_vetorial_mg.max()),
                erro_norma_max_abs_pct=float(res.erro_norma_pct.abs().max()),
                erro_angular_max_deg=float(res.erro_angular_deg.max()),
                atende_metas_exploratorias=dentro,
                metas=dict(vetorial_mg=args.limite_vetorial_mg,norma_pct=args.limite_norma_pct,angular_deg=args.limite_angular_deg),
                nota='Metas escolhidas para triagem do projeto; nao sao tolerancias normativas nem incerteza.')


def _plot_residuos(res, out, name):
    plt = plot_setup(); fig,axes = plt.subplots(2,1,figsize=(11,7),sharex=True)
    labels = [f'{p} r{r}' for p,r in zip(res.posicao,res.repeticao)]
    x = np.arange(len(res))
    for e in EIXOS: axes[0].plot(x,res[f'erro_a{e}_mg'],'o-',label=f'{e.upper()}n',lw=.8,ms=3)
    axes[0].set(ylabel='Erro por componente (mg)',title=name); axes[0].legend()
    axes[1].plot(x,res.erro_angular_deg,'o-',ms=3); axes[1].set(ylabel='Erro de direcao (graus)')
    axes[1].set_xticks(x,labels,rotation=60,ha='right',fontsize=8)
    fig.tight_layout(); fig.savefig(out/(name+'.png')); plt.close(fig)


def calibrar_completa(args, files, out):
    _conferir_parametros(args)
    if args.calibracao: raise ValueError('Ajuste matricial usa os brutos, sem calibracao anterior.')
    if not np.isfinite(args.gravidade_local) or not 9<args.gravidade_local<10:
        raise ValueError('Gravidade de referencia deve estar entre 9 e 10 m/s2.')
    reference, refs = carregar_referencias(args.referencias)
    if len(refs)<6: raise ValueError('Este protocolo requer ao menos seis orientacoes conhecidas e bem distribuidas.')
    df,fontes,sensor,montagem,config = _ler_medias(args,files,refs)
    nominal = 512000/config['faixa_g']; gref = args.gravidade_local/G0
    raw = df[[f'media_a{e}_raw' for e in EIXOS]].to_numpy()
    target = np.vstack([refs[p]*gref for p in df.posicao])
    fit = ajustar_modelo(raw,target,nominal)
    c,b = fit['matriz'],fit['offset']
    corrected = aplicar_matriz(raw,c,b)
    res = _residuos(df,corrected,target); stats = _resumir(res,args)
    before = _residuos(df,raw/nominal,target)
    before = before.rename(columns={k:'nominal_'+k for k in before.columns if k.startswith(('erro_','norma_'))})
    res = res.merge(before[['arquivo']+[k for k in before if k.startswith('nominal_')]],on='arquivo',validate='one_to_one')
    cal = dict(formato=FORMATO_MATRIZ,versao_pacote=VERSAO_PACOTE,criado_em=datetime.now().astimezone().isoformat(),
               status='ajustada_nao_validada',sensor_modelo='ADXL355',identificacao_sensor=sensor,montagem=montagem,
               faixa_g=config['faixa_g'],configuracao_calibracao=config,ordem_eixos=list(EIXOS),
               referencial_saida=dict(nome='conjunto',descricao_eixos=reference['descricao_eixos'],mao_direita=True),
               offset_lsb={e:b[j] for j,e in enumerate(EIXOS)},matriz_correcao_g_lsb=c,
               matriz_resposta_lsb_g=fit['resposta_lsb_g'],sensibilidade_nominal_lsb_g=nominal,
               gravidade_referencia_ms2=args.gravidade_local,referencias=reference,
               referencias_sha256=sha256(args.referencias),repeticoes_por_posicao=df.groupby('posicao').size().to_dict(),
               arquivos_ajuste=fontes,diagnostico_ajuste=stats,
               diagnostico_numerico={k:fit[k] for k in ('posto_referencias','condicao_referencias','condicao_resposta','valores_singulares_relativos')},
               temperatura_media_min_c=df.temperatura_media_c.min(),temperatura_media_max_c=df.temperatura_media_c.max(),
               metodo='Minimos quadrados do modelo direto r/nominal=A*a_ref+beta; C=inv(A)/nominal; b=beta*nominal.',
               observacao='Ajuste estatico do conjunto; nao separa erro intrinseco de pose/montagem. Residuos de ajuste nao sao validacao independente.')
    salvar_json(cal,out/'calibracao.json')
    coef = [dict(tipo='offset',eixo_saida='',eixo_entrada=e.upper(),valor=b[j],unidade='LSB') for j,e in enumerate(EIXOS)]
    coef += [dict(tipo='matriz_C',eixo_saida=eo.upper()+'n',eixo_entrada=ei.upper(),valor=c[j,k],unidade='g/LSB')
             for j,eo in enumerate(EIXOS) for k,ei in enumerate(EIXOS)]
    tabela(pd.DataFrame(coef),out,'calibracao_coeficientes')
    tabela(df,out,'calibracao_medias_brutas'); tabela(res,out,'calibracao_residuos_ajuste')
    rep = df.groupby('posicao')[[f'media_a{e}_raw' for e in EIXOS]].agg(['mean','std','min','max'])
    rep.columns=['_'.join(k) for k in rep.columns]; tabela(rep.reset_index(),out,'calibracao_repeticoes')
    centers=[]
    for e in EIXOS:
        if e+'pos' in refs and e+'neg' in refs and np.allclose(refs[e+'pos'],-refs[e+'neg']):
            pair=(raw[df.posicao==e+'pos'].mean(axis=0)+raw[df.posicao==e+'neg'].mean(axis=0))/2
            delta=aplicar_matriz(pair[None,:],c,b)[0]*1000
            centers.append(dict(par=e.upper()+'+/-',**{f'centro_a{k}_lsb':pair[j] for j,k in enumerate(EIXOS)},
                                desvio_do_bias_vetorial_mg=np.linalg.norm(delta)))
    if centers: tabela(pd.DataFrame(centers),out,'consistencia_pares_opostos')
    _plot_residuos(res,out,'residuos_do_ajuste')
    plt=plot_setup(); fig,ax=plt.subplots(figsize=(6,5)); im=ax.imshow(c*nominal,cmap='coolwarm')
    ax.set_xticks(range(3),['X bruto','Y bruto','Z bruto']); ax.set_yticks(range(3),['Xn','Yn','Zn'])
    for j in range(3):
        for k in range(3): ax.text(k,j,f'{c[j,k]*nominal:.5f}',ha='center',va='center')
    ax.set_title('Matriz C multiplicada pela escala nominal'); fig.colorbar(im,ax=ax); fig.tight_layout()
    fig.savefig(out/'matriz_correcao.png'); plt.close(fig)
    path=out/'analise.json'; j=carregar_json(path); j.update(referencial_saida=cal['referencial_saida'],montagem_calibracao=montagem); salvar_json(j,path)
    (out/'LEIA_ME_RESULTADO.md').write_text('# Calibracao matricial ajustada\n\n'
        'O arquivo calibracao.json ainda precisa de validacao fisica independente. '
        'Leia calibracao_residuos_ajuste.xlsx e consistencia_pares_opostos.xlsx (quando houver). '
        'As componentes ax/ay/az corrigidas agora representam Xn/Yn/Zn do conjunto. '
        'A comparacao nominal usa os eixos originais do sensor e inclui o efeito da rotacao.\n\n'
        'Use 11_validar_calibracao.py em novos CSV/JSON, mantendo a mesma montagem. '
        'Metas de triagem nao constituem incerteza ou certificado.\n',encoding='utf-8')
    print(f'Montagem: {montagem}; referencial de saida: conjunto (Xn, Yn, Zn).')
    print(f'Erro vetorial maximo nos dados ajustados: {stats["erro_vetorial_max_mg"]:.4f} mg.')
    if not stats['atende_metas_exploratorias']: print('AVISO: residuos do ajuste excedem as metas; examine poses, rigidez e condicao termica.')
    print('Calibracao ajustada, ainda nao validada:',(out/'calibracao.json').resolve())


def validar_completa(args, files, out):
    _conferir_parametros(args)
    if not args.calibracao: raise ValueError('Informe --calibracao com o JSON da matriz completa.')
    cal=carregar_json(args.calibracao)
    if cal.get('formato')!=FORMATO_MATRIZ: raise ValueError('Este validador requer a calibracao matricial completa.')
    training={f['csv_sha256'] for f in cal.get('arquivos_ajuste',[])}
    if not training: raise ValueError('Calibracao sem hashes dos arquivos de ajuste; independencia nao verificavel.')
    if any(sha256(p) in training for p in files):
        raise ValueError('Validacao contem CSV usado no ajuste. Adquira registros novos; renomear/copiar nao basta.')
    reference,refs=carregar_referencias(args.referencias)
    if reference['descricao_eixos']!=cal['referencial_saida']['descricao_eixos']:
        raise ValueError('A descricao dos eixos da validacao difere da calibracao. Mantenha o mesmo referencial.')
    df,fontes,sensor,montagem,config=_ler_medias(args,files,refs,cal)
    gref=float(cal['gravidade_referencia_ms2'])/G0
    target=np.vstack([refs[p]*gref for p in df.posicao])
    corr=df[[f'media_a{e}_corr_g' for e in EIXOS]].to_numpy()
    res=_residuos(df,corr,target); stats=_resumir(res,args)
    res['atende_meta_vetorial']=res.erro_vetorial_mg<=args.limite_vetorial_mg
    res['atende_meta_norma']=res.erro_norma_pct.abs()<=args.limite_norma_pct
    res['atende_meta_angular']=res.erro_angular_deg<=args.limite_angular_deg
    tabela(df,out,'validacao_medias'); tabela(res,out,'validacao_residuos')
    grouped=res.groupby('posicao')[['erro_vetorial_mg','erro_norma_pct','erro_angular_deg']].agg(['mean','std','max'])
    grouped.columns=['_'.join(k) for k in grouped.columns]; tabela(grouped.reset_index(),out,'validacao_por_posicao')
    _plot_residuos(res,out,'validacao_independente')
    report=dict(tipo='validacao_estatica_independente',calibracao_arquivo=str(Path(args.calibracao).resolve()),
                calibracao_sha256=sha256(args.calibracao),sensor=sensor,montagem=montagem,referencial='conjunto',
                referencias=reference,referencias_sha256=sha256(args.referencias),arquivos_validacao=fontes,
                independencia='Nenhum CSV de validacao tem o mesmo SHA256 de um CSV usado no ajuste.',
                resumo=stats,limite='Independencia por arquivo nao comprova exatidao do gabarito. Nao valida resposta dinamica, temperatura ou incerteza rastreavel.')
    salvar_json(report,out/'validacao_calibracao.json')
    print(f'Erro vetorial maximo: {stats["erro_vetorial_max_mg"]:.4f} mg; '
          f'erro angular maximo: {stats["erro_angular_max_deg"]:.4f} graus.')
    print('ATENDE as metas exploratorias informadas.' if stats['atende_metas_exploratorias'] else 'NAO ATENDE as metas exploratorias informadas; examine validacao_residuos.xlsx.')
    print('Os coeficientes originais nao foram alterados. Esta verificacao e estatica.')

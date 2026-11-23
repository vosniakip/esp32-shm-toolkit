"""Modelo afim de 12 parametros, sem depender da porta serial ou de arquivos.

O ajuste usa referencias conhecidas: r/nominal = A @ a_referencia + beta.
Depois da inversao: a_conjunto = C @ (r - b), C=inv(A)/nominal.
As linhas de C sao os eixos do conjunto; as colunas sao X/Y/Z brutos.
"""
from __future__ import annotations

import numpy as np

FORMATO_MATRIZ = 'calibracao_adxl355_matriz_v1'


def array_finito(valor, forma, nome):
    a = np.asarray(valor, dtype=float)
    if a.shape != forma or not np.isfinite(a).all():
        raise ValueError(f'{nome}: esperado array finito de dimensao {forma}.')
    return a


def conferir_matriz(c, limite_condicao=100):
    c = array_finito(c, (3, 3), 'Matriz de correcao')
    if np.linalg.det(c) <= 0:
        raise ValueError('Matriz singular ou referencial invertido. Confira sinais e eixos de mao direita.')
    cond = float(np.linalg.cond(c))
    if not np.isfinite(cond) or cond > limite_condicao:
        raise ValueError(f'Matriz mal condicionada: condicao={cond:.6g}. Confira as orientacoes.')
    return c


def aplicar_matriz(brutos, c, b):
    """Cada linha de brutos e uma amostra. Nunca altera o array de entrada."""
    r = np.asarray(brutos, dtype=float)
    if r.ndim != 2 or r.shape[1] != 3 or not np.isfinite(r).all():
        raise ValueError('Leituras brutas devem formar um array N x 3 finito.')
    b = array_finito(b, (3,), 'Offsets')
    c = conferir_matriz(c)
    return (r - b) @ c.T


def ajustar_modelo(medias_brutas, referencias_g, nominal, limite_condicao=100):
    """Minimos quadrados no modelo direto; peso igual por media de arquivo.

    As referencias devem ser medidas/conhecidas externamente. O algoritmo
    nao deduz a direcao da gravidade pelo proprio sensor a ser calibrado.
    """
    r = np.asarray(medias_brutas, dtype=float)
    t = np.asarray(referencias_g, dtype=float)
    if r.ndim != 2 or r.shape[1] != 3 or t.shape != r.shape:
        raise ValueError('Medias e referencias devem ter a mesma dimensao N x 3.')
    if not np.isfinite(r).all() or not np.isfinite(t).all() or not np.isfinite(nominal) or nominal <= 0:
        raise ValueError('Medias/referencias/escala invalidas.')
    design = np.column_stack((t, np.ones(len(t))))
    rank = int(np.linalg.matrix_rank(design))
    if rank != 4:
        raise ValueError('Orientacoes insuficientes: matriz de referencias deve ter posto 4.')
    cond_ref = float(np.linalg.cond(design))
    if cond_ref > limite_condicao:
        raise ValueError('Referencias quase dependentes; distribua as orientacoes em tres dimensoes.')
    params = np.linalg.lstsq(design, r / nominal, rcond=None)[0]
    a = params[:3].T
    if np.linalg.det(a) <= 0:
        raise ValueError('Referencias invertidas ou resposta singular. Confira os sinais do gabarito.')
    singular = np.linalg.svd(a, compute_uv=False)
    if np.any(singular < .5) or np.any(singular > 1.5):
        raise ValueError('Ganho global fora da triagem numerica de 50-150% da nominal; revise faixa/poses.')
    c = conferir_matriz(np.linalg.inv(a) / nominal, limite_condicao)
    b = params[3] * nominal
    return dict(matriz=c, offset=b, resposta_lsb_g=a * nominal,
                posto_referencias=rank, condicao_referencias=cond_ref,
                condicao_resposta=float(np.linalg.cond(a)),
                valores_singulares_relativos=singular)


def avaliar_vetores(vetores_g, referencias_g):
    v = np.asarray(vetores_g, dtype=float)
    t = np.asarray(referencias_g, dtype=float)
    if v.ndim != 2 or v.shape[1] != 3 or v.shape != t.shape:
        raise ValueError('Vetores e referencias devem ter dimensao N x 3.')
    nv = np.linalg.norm(v, axis=1)
    nt = np.linalg.norm(t, axis=1)
    if not np.isfinite(v).all() or not np.isfinite(t).all() or np.any(nt <= 0):
        raise ValueError('Vetor/referencia invalido.')
    dot = np.sum(v * t, axis=1)
    cosine = np.divide(dot, nv * nt, out=np.full(len(v), np.nan), where=nv > 0)
    angular = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
    return dict(normas_g=nv, erro_norma_pct=(nv / nt - 1) * 100,
                erros_g=v - t, erro_vetorial_mg=np.linalg.norm(v - t, axis=1) * 1000,
                erro_angular_deg=angular)

"""Funcoes compartilhadas pelos programas de processamento do GY-9250.

Os scripts foram escritos para preservar os dados brutos. Nenhuma funcao deste
arquivo altera o CSV recebido: conversoes e correcoes existem apenas em memoria
e os resultados sao gravados em uma pasta de processamento separada.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


G0 = 9.80665
SENSIBILIDADE_NOMINAL_LSB_G = 16384.0
FS_NOMINAL_HZ = 250.0
DT_NOMINAL_US = 1_000_000.0 / FS_NOMINAL_HZ
COLUNAS_OBRIGATORIAS = {
    "indice",
    "t_us",
    "ax_raw",
    "ay_raw",
    "az_raw",
    "temp_raw",
}
EIXOS = ("x", "y", "z")


@dataclass(frozen=True)
class Calibracao:
    offset_lsb: dict[str, float]
    sensibilidade_lsb_g: dict[str, float]
    identificacao_sensor: str = "desconhecido"
    caminho: str | None = None


def preparar_matplotlib(pasta_cache: Path | None = None) -> None:
    """Configura Matplotlib para gerar PNG sem abrir janelas."""
    if pasta_cache is None:
        pasta_cache = Path(__file__).resolve().parents[1] / "dados" / ".matplotlib"
    pasta_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(pasta_cache))
    import matplotlib

    matplotlib.use("Agg")


def garantir_pasta(caminho: str | Path) -> Path:
    pasta = Path(caminho)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def nome_seguro(texto: str) -> str:
    texto = texto.strip().lower()
    texto = re.sub(r"[^a-zA-Z0-9_-]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto or "sem_nome"


def _json_padrao(objeto):
    if isinstance(objeto, (np.integer,)):
        return int(objeto)
    if isinstance(objeto, (np.floating,)):
        valor = float(objeto)
        return None if not math.isfinite(valor) else valor
    if isinstance(objeto, np.ndarray):
        return objeto.tolist()
    if isinstance(objeto, Path):
        return str(objeto)
    raise TypeError(f"Tipo nao serializavel: {type(objeto)!r}")


def salvar_json(dados: dict, caminho: str | Path) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2, default=_json_padrao)
        arquivo.write("\n")
    return caminho


def carregar_json(caminho: str | Path) -> dict:
    with Path(caminho).open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def carregar_calibracao(caminho: str | Path | None) -> Calibracao:
    if caminho is None:
        return Calibracao(
            offset_lsb={eixo: 0.0 for eixo in EIXOS},
            sensibilidade_lsb_g={eixo: SENSIBILIDADE_NOMINAL_LSB_G for eixo in EIXOS},
            identificacao_sensor="nominal_sem_calibracao",
            caminho=None,
        )
    dados = carregar_json(caminho)
    return Calibracao(
        offset_lsb={eixo: float(dados["offset_lsb"][eixo]) for eixo in EIXOS},
        sensibilidade_lsb_g={
            eixo: float(dados["sensibilidade_lsb_g"][eixo]) for eixo in EIXOS
        },
        identificacao_sensor=dados.get("identificacao_sensor", "desconhecido"),
        caminho=str(Path(caminho).resolve()),
    )


def ler_csv(caminho: str | Path) -> pd.DataFrame:
    caminho = Path(caminho)
    dados = pd.read_csv(caminho)
    faltantes = COLUNAS_OBRIGATORIAS.difference(dados.columns)
    if faltantes:
        raise ValueError(
            f"{caminho}: colunas obrigatorias ausentes: {sorted(faltantes)}"
        )
    if dados.empty:
        raise ValueError(f"{caminho}: arquivo sem amostras")
    dados = dados.copy()
    for coluna in COLUNAS_OBRIGATORIAS:
        dados[coluna] = pd.to_numeric(dados[coluna], errors="raise")
    dados.attrs["caminho"] = str(caminho.resolve())
    return dados


def converter_para_g(dados: pd.DataFrame, calibracao: Calibracao) -> pd.DataFrame:
    convertido = dados.copy()
    for eixo in EIXOS:
        bruto = convertido[f"a{eixo}_raw"].to_numpy(dtype=float)
        convertido[f"a{eixo}_g"] = (
            bruto - calibracao.offset_lsb[eixo]
        ) / calibracao.sensibilidade_lsb_g[eixo]
        convertido[f"a{eixo}_ms2"] = convertido[f"a{eixo}_g"] * G0
    convertido["temp_c"] = convertido["temp_raw"].to_numpy(dtype=float) / 333.87 + 21.0
    convertido.attrs.update(dados.attrs)
    convertido.attrs["calibracao"] = calibracao.caminho or "nominal"
    return convertido


def tempo_relativo_s(dados: pd.DataFrame) -> np.ndarray:
    tempos = dados["t_us"].to_numpy(dtype=np.float64)
    return (tempos - tempos[0]) / 1_000_000.0


def frequencia_efetiva(dados: pd.DataFrame) -> float:
    if len(dados) < 2:
        return float("nan")
    duracao_s = (float(dados["t_us"].iloc[-1]) - float(dados["t_us"].iloc[0])) / 1e6
    if duracao_s <= 0:
        return float("nan")
    return (len(dados) - 1) / duracao_s


def descartar_inicio(dados: pd.DataFrame, segundos: float) -> pd.DataFrame:
    if segundos <= 0:
        return dados.copy()
    t = tempo_relativo_s(dados)
    recorte = dados.loc[t >= segundos].copy()
    if recorte.empty:
        raise ValueError("O descarte solicitado removeu todas as amostras")
    recorte.attrs.update(dados.attrs)
    return recorte


def localizar_csvs(entradas: Sequence[str | Path]) -> list[Path]:
    encontrados: list[Path] = []
    for entrada in entradas:
        caminho = Path(entrada)
        if caminho.is_dir():
            encontrados.extend(sorted(caminho.rglob("*.csv")))
        elif caminho.is_file() and caminho.suffix.lower() == ".csv":
            encontrados.append(caminho)
        else:
            raise FileNotFoundError(f"Entrada inexistente ou nao CSV: {caminho}")
    unicos = sorted({p.resolve() for p in encontrados})
    if not unicos:
        raise FileNotFoundError("Nenhum arquivo CSV foi encontrado")
    return unicos


def metadados_laterais(caminho_csv: str | Path) -> dict:
    caminho_csv = Path(caminho_csv)
    candidato = caminho_csv.with_suffix(".json")
    return carregar_json(candidato) if candidato.exists() else {}


def rms_centralizado(valores: np.ndarray) -> float:
    valores = np.asarray(valores, dtype=float)
    return float(np.sqrt(np.mean((valores - np.mean(valores)) ** 2)))


def integrar_psd(frequencias: np.ndarray, psd: np.ndarray, fmin: float, fmax: float) -> float:
    mascara = (frequencias >= fmin) & (frequencias <= fmax)
    if np.count_nonzero(mascara) < 2:
        return float("nan")
    variancia = np.trapezoid(psd[mascara], frequencias[mascara])
    return float(np.sqrt(max(variancia, 0.0)))


def valor_cv(media: float, desvio: float, limite_zero: float = 1e-9) -> float:
    if abs(media) <= limite_zero:
        return float("nan")
    return abs(desvio / media) * 100.0


def resumo_estatistico(valores: Iterable[float]) -> dict[str, float]:
    vetor = np.asarray(list(valores), dtype=float)
    return {
        "n": int(vetor.size),
        "media": float(np.mean(vetor)),
        "desvio_padrao": float(np.std(vetor, ddof=1)) if vetor.size > 1 else 0.0,
        "minimo": float(np.min(vetor)),
        "maximo": float(np.max(vetor)),
        "p01": float(np.percentile(vetor, 1)),
        "p50": float(np.percentile(vetor, 50)),
        "p99": float(np.percentile(vetor, 99)),
    }


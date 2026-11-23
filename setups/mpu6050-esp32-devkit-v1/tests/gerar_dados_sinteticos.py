"""Gera dados artificiais somente para testar os scripts, nunca para o TCC."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


FS = 250.0
OFFSET = np.array([300.0, -180.0, 500.0])
SENS = np.array([16200.0, 16500.0, 16050.0])
RNG = np.random.default_rng(20260821)


def gravar(pasta: Path, nome: str, aceleracao_g: np.ndarray, temp_c: np.ndarray, meta: dict) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    n = len(aceleracao_g)
    dt = RNG.normal(4000.0, 8.0, n)
    t_us = np.cumsum(dt).astype(np.int64)
    t_us -= t_us[0]
    bruto = np.rint(OFFSET + aceleracao_g * SENS).astype(np.int16)
    temp_raw = np.rint((temp_c - 36.53) * 340.0).astype(np.int16)
    tabela = pd.DataFrame(
        {
            "indice": np.arange(n),
            "t_us": t_us,
            "ax_raw": bruto[:, 0],
            "ay_raw": bruto[:, 1],
            "az_raw": bruto[:, 2],
            "temp_raw": temp_raw,
            "perdidas_acum": np.zeros(n, dtype=int),
            "erros_i2c": np.zeros(n, dtype=int),
        }
    )
    caminho = pasta / f"{nome}.csv"
    tabela.to_csv(caminho, index=False)
    (pasta / f"{nome}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return caminho


def ruido(n: int, sigma_g: float = 0.002) -> np.ndarray:
    return RNG.normal(0.0, sigma_g, (n, 3))


def main() -> None:
    raiz = Path(__file__).resolve().parent / "dados_sinteticos"
    cal = raiz / "calibracao"
    repouso = raiz / "repouso"
    dinamico = raiz / "dinamico"
    outros = raiz / "outros"

    posicoes = {
        "Xpos": np.array([1.0, 0.0, 0.0]),
        "Xneg": np.array([-1.0, 0.0, 0.0]),
        "Ypos": np.array([0.0, 1.0, 0.0]),
        "Yneg": np.array([0.0, -1.0, 0.0]),
        "Zpos": np.array([0.0, 0.0, 1.0]),
        "Zneg": np.array([0.0, 0.0, -1.0]),
    }
    n_cal = int(10 * FS)
    for pos, vetor in posicoes.items():
        for repeticao in (1, 2):
            sinal = np.tile(vetor, (n_cal, 1)) + ruido(n_cal)
            gravar(
                cal,
                f"teste_calibracao_{pos}_r{repeticao:02d}",
                sinal,
                np.full(n_cal, 27.0),
                {"ensaio": "calibracao", "posicao": pos, "repeticao": repeticao},
            )

    n_rep = int(30 * FS)
    for repeticao in range(1, 6):
        sinal = np.tile([0.0, 0.0, 1.0], (n_rep, 1)) + ruido(n_rep)
        gravar(
            repouso,
            f"teste_repouso_Zpos_r{repeticao:02d}",
            sinal,
            np.full(n_rep, 28.0 + repeticao * 0.02),
            {"ensaio": "repouso", "posicao": "Zpos", "repeticao": repeticao},
        )

    n_dyn = int(30 * FS)
    tempo = np.arange(n_dyn) / FS
    for repeticao in range(1, 6):
        sinal = ruido(n_dyn, 0.001)
        sinal[:, 0] += 0.03 * np.sin(2 * np.pi * (7.5 + 0.01 * repeticao) * tempo)
        sinal[:, 2] += 1.0
        gravar(
            dinamico,
            f"teste_dinamico_r{repeticao:02d}",
            sinal,
            np.full(n_dyn, 28.0),
            {"ensaio": "dinamico", "posicao": "cantilever", "repeticao": repeticao},
        )

    n_term = int(600 * FS)
    tempo_term = np.arange(n_term) / FS
    temperatura = 24.0 + 7.0 * (1.0 - np.exp(-tempo_term / 180.0))
    sinal_term = ruido(n_term, 0.002)
    sinal_term[:, 0] += 0.0008 * (temperatura - temperatura[-1])
    sinal_term[:, 1] -= 0.0005 * (temperatura - temperatura[-1])
    sinal_term[:, 2] += 1.0 + 0.0010 * (temperatura - temperatura[-1])
    gravar(
        outros,
        "teste_aquecimento",
        sinal_term,
        temperatura,
        {"ensaio": "aquecimento", "posicao": "Zpos", "repeticao": 1},
    )
    print(f"Dados sinteticos criados em: {raiz}")


if __name__ == "__main__":
    main()

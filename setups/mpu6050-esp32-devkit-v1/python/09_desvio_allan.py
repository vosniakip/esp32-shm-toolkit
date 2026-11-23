"""Calcula desvio de Allan sobreposto para registros estaticos longos."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from comum import (
    EIXOS,
    carregar_calibracao,
    converter_para_g,
    frequencia_efetiva,
    garantir_pasta,
    ler_csv,
    preparar_matplotlib,
    salvar_json,
)


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Desvio de Allan sobreposto.")
    parser.add_argument("arquivo")
    parser.add_argument("--calibracao")
    parser.add_argument("--eixos", default="xyz", help="Combinacao de x, y e z")
    parser.add_argument("--pontos", type=int, default=60)
    parser.add_argument("--saida", default="dados/processados/allan")
    return parser.parse_args()


def allan_sobreposto(valores: np.ndarray, fs: float, pontos: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Retorna tau, desvio de Allan e numero de diferencas usadas.

    Para um fator de agrupamento m, calcula todas as medias de m amostras que
    podem ser formadas com sobreposicao. Em seguida compara medias separadas por
    m amostras: sigma_A^2 = 0,5 * media[(media[k+m]-media[k])^2].
    """
    x = np.asarray(valores, dtype=np.float64)
    n = len(x)
    max_m = n // 10
    if max_m < 2:
        raise ValueError("Registro curto demais para desvio de Allan")
    fatores = np.unique(
        np.maximum(1, np.logspace(0, np.log10(max_m), pontos).astype(int))
    )
    soma = np.concatenate(([0.0], np.cumsum(x)))
    taus: list[float] = []
    desvios: list[float] = []
    quantidades: list[int] = []
    for m in fatores:
        medias = (soma[m:] - soma[:-m]) / m
        if len(medias) <= m:
            continue
        diferencas = medias[m:] - medias[:-m]
        variancia = 0.5 * np.mean(diferencas ** 2)
        taus.append(m / fs)
        desvios.append(np.sqrt(max(variancia, 0.0)))
        quantidades.append(len(diferencas))
    return np.asarray(taus), np.asarray(desvios), np.asarray(quantidades)


def main() -> None:
    args = argumentos()
    preparar_matplotlib()
    import matplotlib.pyplot as plt

    eixos = tuple(e for e in EIXOS if e in args.eixos.lower())
    if not eixos:
        raise ValueError("--eixos deve conter x, y e/ou z")

    caminho = Path(args.arquivo)
    calibracao = carregar_calibracao(args.calibracao)
    dados = converter_para_g(ler_csv(caminho), calibracao)
    fs = frequencia_efetiva(dados)
    pasta = garantir_pasta(args.saida)
    tabelas: list[pd.DataFrame] = []
    resumo: dict[str, dict] = {}

    fig, ax = plt.subplots(figsize=(9, 6.5))
    for eixo, cor in zip(eixos, ("tab:red", "tab:green", "tab:blue")):
        valores = dados[f"a{eixo}_g"].to_numpy(dtype=float)
        tau, adev, quantidade = allan_sobreposto(valores, fs, args.pontos)
        tabelas.append(
            pd.DataFrame(
                {
                    "eixo": eixo.upper(),
                    "tau_s": tau,
                    "desvio_allan_g": adev,
                    "pares_utilizados": quantidade,
                }
            )
        )
        indice_min = int(np.argmin(adev))
        resumo[eixo] = {
            "desvio_allan_minimo_g": float(adev[indice_min]),
            "tau_no_minimo_s": float(tau[indice_min]),
            "tau_min_s": float(tau[0]),
            "tau_max_s": float(tau[-1]),
        }
        ax.loglog(tau, adev, label=eixo.upper(), color=cor)

    pd.concat(tabelas, ignore_index=True).to_csv(
        pasta / f"{caminho.stem}_desvio_allan.csv", index=False
    )
    salvar_json(
        {
            "arquivo": str(caminho.resolve()),
            "calibracao": calibracao.caminho or "nominal",
            "fs_efetiva_hz": fs,
            "metodo": "desvio de Allan sobreposto de medias agrupadas",
            "resumo": resumo,
            "nota": (
                "Nao foi aplicado passa-altas. A interpretacao de coeficientes "
                "de ruido exige analisar as inclinacoes da curva em escala log-log."
            ),
        },
        pasta / f"{caminho.stem}_desvio_allan_resumo.json",
    )

    ax.set(
        title="Desvio de Allan sobreposto",
        xlabel="Tempo de integracao tau (s)",
        ylabel="Desvio de Allan (g)",
    )
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(pasta / f"{caminho.stem}_desvio_allan.png", dpi=180)
    plt.close(fig)

    print("Desvio de Allan concluido")
    for eixo in eixos:
        print(
            f"{eixo.upper()}: minimo={resumo[eixo]['desvio_allan_minimo_g']:.6g} g "
            f"em tau={resumo[eixo]['tau_no_minimo_s']:.3f} s"
        )
    print(f"Resultados salvos em: {pasta.resolve()}")


if __name__ == "__main__":
    main()


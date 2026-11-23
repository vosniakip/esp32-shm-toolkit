"""Analisa aquecimento, deriva de offset e associacao com temperatura interna."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import linregress

from comum import (
    EIXOS,
    carregar_calibracao,
    converter_para_g,
    garantir_pasta,
    ler_csv,
    preparar_matplotlib,
    salvar_json,
    tempo_relativo_s,
)


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deriva durante aquecimento do sensor.")
    parser.add_argument("arquivo")
    parser.add_argument("--calibracao")
    parser.add_argument("--janela", type=float, default=60.0, help="Janela de medias em segundos")
    parser.add_argument("--saida", default="dados/processados/deriva_termica")
    return parser.parse_args()


def main() -> None:
    args = argumentos()
    preparar_matplotlib()
    import matplotlib.pyplot as plt

    caminho = Path(args.arquivo)
    calibracao = carregar_calibracao(args.calibracao)
    dados = converter_para_g(ler_csv(caminho), calibracao)
    t = tempo_relativo_s(dados)
    dados = dados.copy()
    dados["tempo_s"] = t
    dados["janela"] = np.floor(t / args.janela).astype(int)

    linhas: list[dict] = []
    for numero, grupo in dados.groupby("janela"):
        linha: dict[str, float | int] = {
            "janela": int(numero),
            "tempo_central_s": float(grupo["tempo_s"].mean()),
            "n": len(grupo),
            "temp_media_c": float(grupo["temp_c"].mean()),
            "temp_dp_c": float(grupo["temp_c"].std(ddof=1)),
        }
        for eixo in EIXOS:
            valores = grupo[f"a{eixo}_g"].to_numpy(dtype=float)
            linha[f"media_a{eixo}_g"] = float(np.mean(valores))
            linha[f"dp_a{eixo}_g"] = float(np.std(valores, ddof=1))
        linhas.append(linha)
    tabela = pd.DataFrame(linhas)
    if len(tabela) < 3:
        raise ValueError("Sao necessarias pelo menos tres janelas para avaliar deriva")

    referencia_final = tabela.tail(min(10, len(tabela)))
    regressao: dict[str, dict] = {}
    for eixo in EIXOS:
        coluna = f"media_a{eixo}_g"
        ref = float(referencia_final[coluna].mean())
        tabela[f"deriva_a{eixo}_mg"] = (tabela[coluna] - ref) * 1000.0
        reg = linregress(tabela["temp_media_c"], tabela[coluna] * 1000.0)
        regressao[eixo] = {
            "inclinacao_mg_por_c": reg.slope,
            "intercepto_mg": reg.intercept,
            "r2": reg.rvalue ** 2,
            "p_valor": reg.pvalue,
            "erro_padrao_inclinacao": reg.stderr,
            "referencia_final_g": ref,
            "amplitude_deriva_mg": float(np.ptp(tabela[f"deriva_a{eixo}_mg"])),
        }

    pasta = garantir_pasta(args.saida)
    tabela.to_csv(pasta / f"{caminho.stem}_deriva_por_janela.csv", index=False)
    salvar_json(
        {
            "arquivo": str(caminho.resolve()),
            "calibracao": calibracao.caminho or "nominal",
            "janela_s": args.janela,
            "temperatura_inicial_c": float(tabela["temp_media_c"].iloc[0]),
            "temperatura_final_c": float(tabela["temp_media_c"].iloc[-1]),
            "regressao": regressao,
            "nota": (
                "A temperatura do MPU-9250 e temperatura interna aproximada, nao "
                "uma medicao calibrada da temperatura ambiente. Correlacao nao "
                "prova causalidade se temperatura e tempo variarem juntos."
            ),
        },
        pasta / f"{caminho.stem}_deriva_resumo.json",
    )

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    tempo_min = tabela["tempo_central_s"] / 60.0
    axes[0].plot(tempo_min, tabela["temp_media_c"], color="tab:orange")
    axes[0].set(ylabel="Temperatura interna (graus C)", title="Aquecimento e deriva")
    for eixo, cor in zip(EIXOS, ("tab:red", "tab:green", "tab:blue")):
        axes[1].plot(
            tempo_min, tabela[f"media_a{eixo}_g"],
            label=eixo.upper(), color=cor,
        )
        axes[2].plot(
            tempo_min, tabela[f"deriva_a{eixo}_mg"],
            label=eixo.upper(), color=cor,
        )
    axes[1].set(ylabel="Media (g)")
    axes[2].set(xlabel="Tempo (min)", ylabel="Deriva relativa ao final (mg)")
    for ax in axes:
        ax.grid(True, alpha=0.3)
    axes[1].legend()
    axes[2].legend()
    fig.tight_layout()
    fig.savefig(pasta / f"{caminho.stem}_deriva.png", dpi=180)
    plt.close(fig)

    print("Deriva termica analisada")
    for eixo in EIXOS:
        print(
            f"{eixo.upper()}: {regressao[eixo]['inclinacao_mg_por_c']:.4f} mg/grau C; "
            f"R2={regressao[eixo]['r2']:.3f}; "
            f"amplitude={regressao[eixo]['amplitude_deriva_mg']:.3f} mg"
        )
    print(f"Resultados salvos em: {pasta.resolve()}")


if __name__ == "__main__":
    main()


"""Compara medias e ruido entre repeticoes de um mesmo ensaio."""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from scipy.signal import welch

from comum import (
    EIXOS,
    carregar_calibracao,
    converter_para_g,
    descartar_inicio,
    frequencia_efetiva,
    garantir_pasta,
    integrar_psd,
    ler_csv,
    localizar_csvs,
    preparar_matplotlib,
    rms_centralizado,
    valor_cv,
)


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repetibilidade entre aquisicoes.")
    parser.add_argument("entradas", nargs="+")
    parser.add_argument("--calibracao")
    parser.add_argument("--descartar", type=float, default=2.0)
    parser.add_argument("--fmin", type=float, default=0.5)
    parser.add_argument("--fmax", type=float, default=50.0)
    parser.add_argument("--saida", default="dados/processados/repetibilidade")
    return parser.parse_args()


def main() -> None:
    args = argumentos()
    preparar_matplotlib()
    import matplotlib.pyplot as plt

    calibracao = carregar_calibracao(args.calibracao)
    arquivos = localizar_csvs(args.entradas)
    pasta = garantir_pasta(args.saida)
    por_arquivo: list[dict] = []

    for repeticao, caminho in enumerate(arquivos, start=1):
        completos = converter_para_g(ler_csv(caminho), calibracao)
        fs = frequencia_efetiva(completos)
        dados = descartar_inicio(completos, args.descartar)
        for eixo in EIXOS:
            valores = dados[f"a{eixo}_g"].to_numpy(dtype=float)
            ruido = valores - np.mean(valores)
            nperseg = min(4096, len(ruido))
            freq, psd = welch(
                ruido,
                fs=fs,
                window="hann",
                nperseg=nperseg,
                noverlap=nperseg // 2,
                detrend="constant",
                scaling="density",
            )
            por_arquivo.append(
                {
                    "repeticao": repeticao,
                    "arquivo": str(caminho),
                    "eixo": eixo.upper(),
                    "media_g": float(np.mean(valores)),
                    "rms_ruido_g": rms_centralizado(valores),
                    "rms_banda_g": integrar_psd(freq, psd, args.fmin, args.fmax),
                    "fs_efetiva_hz": fs,
                }
            )

    tabela = pd.DataFrame(por_arquivo)
    tabela.to_csv(pasta / "repetibilidade_por_arquivo.csv", index=False)

    agregados: list[dict] = []
    for eixo, grupo in tabela.groupby("eixo"):
        linha: dict[str, float | int | str] = {"eixo": eixo, "repeticoes": len(grupo)}
        for metrica in ("media_g", "rms_ruido_g", "rms_banda_g", "fs_efetiva_hz"):
            valores = grupo[metrica].to_numpy(dtype=float)
            media = float(np.mean(valores))
            dp = float(np.std(valores, ddof=1)) if len(valores) > 1 else 0.0
            linha[f"{metrica}_media"] = media
            linha[f"{metrica}_dp"] = dp
            linha[f"{metrica}_cv_pct"] = valor_cv(media, dp)
        agregados.append(linha)
    tabela_agregada = pd.DataFrame(agregados)
    tabela_agregada.to_csv(pasta / "repetibilidade_agregada.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for eixo, cor in zip(("X", "Y", "Z"), ("tab:red", "tab:green", "tab:blue")):
        grupo = tabela[tabela["eixo"] == eixo]
        axes[0].plot(
            grupo["repeticao"], grupo["rms_ruido_g"] * 1000,
            marker="o", label=eixo, color=cor,
        )
        axes[1].plot(
            grupo["repeticao"], grupo["rms_banda_g"] * 1000,
            marker="o", label=eixo, color=cor,
        )
    axes[0].set(title="RMS do ruido", xlabel="Repeticao", ylabel="RMS (mg)")
    axes[1].set(
        title=f"RMS por PSD: {args.fmin:g}-{args.fmax:g} Hz",
        xlabel="Repeticao",
        ylabel="RMS (mg)",
    )
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig(pasta / "repetibilidade.png", dpi=180)
    plt.close(fig)

    print(tabela_agregada.to_string(index=False))
    print("CV de medias proximas de zero pode ser indefinido; use o desvio absoluto.")
    print(f"Resultados salvos em: {pasta.resolve()}")


if __name__ == "__main__":
    main()


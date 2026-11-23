"""Analisa ruido em repouso, RMS, PSD/ASD de Welch e saturacao."""

from __future__ import annotations

import argparse
from pathlib import Path

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
    salvar_json,
)


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ruido RMS e PSD de Welch em repouso.")
    parser.add_argument("entradas", nargs="+")
    parser.add_argument("--calibracao")
    parser.add_argument("--descartar", type=float, default=2.0)
    parser.add_argument("--fmin", type=float, default=0.5)
    parser.add_argument("--fmax", type=float, default=50.0)
    parser.add_argument("--nperseg", type=int, default=4096)
    parser.add_argument("--saida", default="dados/processados/ruido_psd")
    return parser.parse_args()


def main() -> None:
    args = argumentos()
    preparar_matplotlib()
    import matplotlib.pyplot as plt

    calibracao = carregar_calibracao(args.calibracao)
    arquivos = localizar_csvs(args.entradas)
    pasta = garantir_pasta(args.saida)
    resultados: list[dict] = []
    psds_por_eixo: dict[str, list[tuple[np.ndarray, np.ndarray, str]]] = {
        eixo: [] for eixo in EIXOS
    }

    for caminho in arquivos:
        dados_completos = converter_para_g(ler_csv(caminho), calibracao)
        fs = frequencia_efetiva(dados_completos)
        if not np.isfinite(fs) or fs <= 0:
            raise ValueError(f"Frequencia efetiva invalida em {caminho}")
        dados = descartar_inicio(dados_completos, args.descartar)
        saturou = bool(
            np.any(np.abs(dados[["ax_raw", "ay_raw", "az_raw"]].to_numpy()) >= 32760)
        )

        for eixo in EIXOS:
            valores = dados[f"a{eixo}_g"].to_numpy(dtype=float)
            ruido = valores - np.mean(valores)
            nperseg = min(args.nperseg, len(ruido))
            if nperseg < 16:
                raise ValueError(f"Poucas amostras em {caminho}")
            frequencias, psd = welch(
                ruido,
                fs=fs,
                window="hann",
                nperseg=nperseg,
                noverlap=nperseg // 2,
                detrend="constant",
                scaling="density",
            )
            psds_por_eixo[eixo].append((frequencias, psd, caminho.stem))
            resultados.append(
                {
                    "arquivo": str(caminho),
                    "eixo": eixo.upper(),
                    "n": len(valores),
                    "fs_efetiva_hz": fs,
                    "media_g": float(np.mean(valores)),
                    "desvio_padrao_g": float(np.std(valores, ddof=1)),
                    "rms_ruido_g": rms_centralizado(valores),
                    "pico_a_pico_g": float(np.ptp(valores)),
                    "minimo_g": float(np.min(valores)),
                    "maximo_g": float(np.max(valores)),
                    "rms_psd_total_g": integrar_psd(
                        frequencias, psd, frequencias[0], frequencias[-1]
                    ),
                    "rms_psd_banda_g": integrar_psd(
                        frequencias, psd, args.fmin, args.fmax
                    ),
                    "banda_fmin_hz": args.fmin,
                    "banda_fmax_hz": args.fmax,
                    "saturacao": saturou,
                }
            )

    tabela = pd.DataFrame(resultados)
    tabela.to_csv(pasta / "metricas_ruido_por_arquivo.csv", index=False)

    agregados = (
        tabela.groupby("eixo")
        .agg(
            repeticoes=("arquivo", "count"),
            rms_ruido_media_g=("rms_ruido_g", "mean"),
            rms_ruido_dp_g=("rms_ruido_g", "std"),
            rms_banda_media_g=("rms_psd_banda_g", "mean"),
            rms_banda_dp_g=("rms_psd_banda_g", "std"),
            pico_a_pico_medio_g=("pico_a_pico_g", "mean"),
            fs_media_hz=("fs_efetiva_hz", "mean"),
        )
        .reset_index()
    )
    agregados.to_csv(pasta / "metricas_ruido_agregadas.csv", index=False)

    psd_media_linhas: list[pd.DataFrame] = []
    fig, ax = plt.subplots(figsize=(10.5, 6))
    cores = {"x": "tab:red", "y": "tab:green", "z": "tab:blue"}
    for eixo in EIXOS:
        conjuntos = psds_por_eixo[eixo]
        frequencia_base = conjuntos[0][0]
        psds_interp = []
        for freq, psd, _ in conjuntos:
            psds_interp.append(np.interp(frequencia_base, freq, psd))
        psd_media = np.mean(psds_interp, axis=0)
        asd = np.sqrt(psd_media)
        psd_media_linhas.append(
            pd.DataFrame(
                {
                    "frequencia_hz": frequencia_base,
                    "eixo": eixo.upper(),
                    "psd_g2_hz": psd_media,
                    "asd_g_raiz_hz": asd,
                }
            )
        )
        mascara = (frequencia_base > 0) & (frequencia_base <= min(125, frequencia_base[-1]))
        ax.semilogy(
            frequencia_base[mascara],
            asd[mascara],
            label=eixo.upper(),
            color=cores[eixo],
        )

    pd.concat(psd_media_linhas, ignore_index=True).to_csv(
        pasta / "psd_media.csv", index=False
    )
    ax.axvspan(args.fmin, args.fmax, color="gray", alpha=0.12, label="Banda analisada")
    ax.set(
        title="Densidade espectral de amplitude do ruido",
        xlabel="Frequencia (Hz)",
        ylabel="ASD (g/raiz(Hz))",
        xlim=(0, min(125, max(item[0][-1] for itens in psds_por_eixo.values() for item in itens))),
    )
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(pasta / "asd_media.png", dpi=180)
    plt.close(fig)

    resumo = {
        "arquivos": [str(p) for p in arquivos],
        "calibracao": calibracao.caminho or "nominal",
        "metodo_psd": "Welch; janela Hann; 50% sobreposicao; detrend constant",
        "nperseg_solicitado": args.nperseg,
        "banda_hz": [args.fmin, args.fmax],
        "observacao": (
            "O RMS de ruido e calculado apos retirada da media. O RMS da banda "
            "e a raiz da integral da PSD entre fmin e fmax."
        ),
    }
    salvar_json(resumo, pasta / "parametros_analise_ruido.json")
    print(agregados.to_string(index=False))
    print(f"Resultados salvos em: {pasta.resolve()}")


if __name__ == "__main__":
    main()


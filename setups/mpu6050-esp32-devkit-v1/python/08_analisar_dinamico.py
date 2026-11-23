"""Analisa vibracao livre: filtragem, RMS, pico e frequencia dominante."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt, welch

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
    nome_seguro,
    preparar_matplotlib,
    salvar_json,
    tempo_relativo_s,
    valor_cv,
)


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analise de ensaio dinamico simples.")
    parser.add_argument("entradas", nargs="+")
    parser.add_argument("--calibracao")
    parser.add_argument("--eixo", choices=["x", "y", "z", "auto"], default="auto")
    parser.add_argument("--fmin", type=float, default=0.5)
    parser.add_argument("--fmax", type=float, default=50.0)
    parser.add_argument("--ordem", type=int, default=4)
    parser.add_argument("--descartar", type=float, default=0.0)
    parser.add_argument("--freq-referencia", type=float)
    parser.add_argument(
        "--saida",
        default="dados/processados/dinamico",
        help="Pasta raiz; cada execucao recebe uma subpasta exclusiva.",
    )
    return parser.parse_args()


def criar_pasta_da_execucao(raiz: str, arquivos: list[Path]) -> tuple[Path, datetime]:
    """Cria destino unico com data, hora e identificacao da entrada."""
    instante = datetime.now().astimezone()
    carimbo = instante.strftime("%Y-%m-%d_%H-%M-%S")
    if len(arquivos) == 1:
        identificador = nome_seguro(arquivos[0].stem)
    else:
        identificador = f"{nome_seguro(arquivos[0].stem)}_mais_{len(arquivos) - 1}"

    pasta_raiz = garantir_pasta(raiz)
    base = pasta_raiz / f"{carimbo}_{identificador}"
    candidata = base
    numero = 2
    while candidata.exists():
        candidata = Path(f"{base}_{numero:02d}")
        numero += 1
    candidata.mkdir(parents=True, exist_ok=False)
    return candidata, instante


def filtrar_banda(valores: np.ndarray, fs: float, fmin: float, fmax: float, ordem: int) -> np.ndarray:
    nyquist = fs / 2.0
    if not 0 < fmin < fmax < nyquist:
        raise ValueError(
            f"Banda invalida: {fmin}-{fmax} Hz para Nyquist={nyquist:.3f} Hz"
        )
    sos = butter(ordem, [fmin, fmax], btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, valores)


def main() -> None:
    args = argumentos()
    preparar_matplotlib()
    import matplotlib.pyplot as plt

    calibracao = carregar_calibracao(args.calibracao)
    arquivos = localizar_csvs(args.entradas)
    pasta, instante_analise = criar_pasta_da_execucao(args.saida, arquivos)
    linhas: list[dict] = []

    fig_tempo, ax_tempo = plt.subplots(figsize=(11, 5.5))
    fig_psd, ax_psd = plt.subplots(figsize=(10.5, 6))

    for repeticao, caminho in enumerate(arquivos, start=1):
        completos = converter_para_g(ler_csv(caminho), calibracao)
        fs = frequencia_efetiva(completos)
        dados = descartar_inicio(completos, args.descartar)
        sinais_filtrados: dict[str, np.ndarray] = {}
        for eixo in EIXOS:
            valores = dados[f"a{eixo}_g"].to_numpy(dtype=float)
            sinais_filtrados[eixo] = filtrar_banda(
                valores, fs, args.fmin, args.fmax, args.ordem
            )

        if args.eixo == "auto":
            eixo_escolhido = max(
                EIXOS, key=lambda e: float(np.sqrt(np.mean(sinais_filtrados[e] ** 2)))
            )
        else:
            eixo_escolhido = args.eixo

        sinal = sinais_filtrados[eixo_escolhido]
        nperseg = min(4096, len(sinal))
        freq, psd = welch(
            sinal,
            fs=fs,
            window="hann",
            nperseg=nperseg,
            noverlap=nperseg // 2,
            detrend="constant",
            scaling="density",
        )
        mascara = (freq >= args.fmin) & (freq <= args.fmax)
        if not np.any(mascara):
            raise ValueError("Nenhum ponto espectral dentro da banda")
        indices_banda = np.flatnonzero(mascara)
        indice_pico = indices_banda[np.argmax(psd[mascara])]
        freq_dominante = float(freq[indice_pico])
        rms = float(np.sqrt(np.mean(sinal ** 2)))
        pico = float(np.max(np.abs(sinal)))
        bruto = dados[["ax_raw", "ay_raw", "az_raw"]].to_numpy()
        saturacao = bool(np.any(np.abs(bruto) >= 32760))
        erro_freq_pct = (
            (freq_dominante - args.freq_referencia) / args.freq_referencia * 100.0
            if args.freq_referencia
            else float("nan")
        )
        linhas.append(
            {
                "repeticao": repeticao,
                "arquivo": str(caminho),
                "eixo": eixo_escolhido.upper(),
                "fs_efetiva_hz": fs,
                "frequencia_dominante_hz": freq_dominante,
                "amplitude_rms_filtrada_g": rms,
                "pico_absoluto_filtrado_g": pico,
                "rms_integral_psd_g": integrar_psd(freq, psd, args.fmin, args.fmax),
                "saturacao": saturacao,
                "frequencia_referencia_hz": args.freq_referencia,
                "erro_frequencia_pct": erro_freq_pct,
            }
        )

        t = tempo_relativo_s(dados)
        ax_tempo.plot(t, sinal, linewidth=0.8, label=f"R{repeticao} {eixo_escolhido.upper()}")
        ax_psd.semilogy(
            freq[mascara],
            np.sqrt(psd[mascara]),
            linewidth=1.0,
            label=f"R{repeticao}: {freq_dominante:.3f} Hz",
        )

    tabela = pd.DataFrame(linhas)
    tabela.to_csv(pasta / "metricas_dinamicas.csv", index=False)
    frequencias = tabela["frequencia_dominante_hz"].to_numpy(dtype=float)
    amplitudes = tabela["amplitude_rms_filtrada_g"].to_numpy(dtype=float)
    resumo = pd.DataFrame(
        [
            {
                "repeticoes": len(tabela),
                "frequencia_media_hz": np.mean(frequencias),
                "frequencia_dp_hz": np.std(frequencias, ddof=1) if len(frequencias) > 1 else 0,
                "frequencia_cv_pct": valor_cv(
                    float(np.mean(frequencias)),
                    float(np.std(frequencias, ddof=1)) if len(frequencias) > 1 else 0,
                ),
                "amplitude_rms_media_g": np.mean(amplitudes),
                "amplitude_rms_dp_g": np.std(amplitudes, ddof=1) if len(amplitudes) > 1 else 0,
                "amplitude_rms_cv_pct": valor_cv(
                    float(np.mean(amplitudes)),
                    float(np.std(amplitudes, ddof=1)) if len(amplitudes) > 1 else 0,
                ),
                "alguma_saturacao": bool(tabela["saturacao"].any()),
                "filtro": f"Butterworth ordem {args.ordem}, zero-phase, {args.fmin}-{args.fmax} Hz",
            }
        ]
    )
    resumo.to_csv(pasta / "resumo_dinamico.csv", index=False)

    salvar_json(
        {
            "criado_em": instante_analise.isoformat(),
            "arquivos_entrada": [str(caminho.resolve()) for caminho in arquivos],
            "calibracao": str(Path(args.calibracao).resolve()) if args.calibracao else "nominal",
            "eixo_solicitado": args.eixo,
            "fmin_hz": args.fmin,
            "fmax_hz": args.fmax,
            "ordem_filtro": args.ordem,
            "segundos_descartados": args.descartar,
            "frequencia_referencia_hz": args.freq_referencia,
            "pasta_saida": str(pasta.resolve()),
        },
        pasta / "analise.json",
    )

    ax_tempo.set(
        title="Resposta dinamica filtrada",
        xlabel="Tempo (s)",
        ylabel="Aceleracao (g)",
    )
    ax_tempo.grid(True, alpha=0.3)
    ax_tempo.legend(fontsize=8)
    fig_tempo.tight_layout()
    fig_tempo.savefig(pasta / "sinais_dinamicos.png", dpi=180)
    plt.close(fig_tempo)

    ax_psd.set(
        title="Espectros dos ensaios dinamicos",
        xlabel="Frequencia (Hz)",
        ylabel="ASD (g/raiz(Hz))",
    )
    ax_psd.grid(True, which="both", alpha=0.3)
    ax_psd.legend(fontsize=8)
    fig_psd.tight_layout()
    fig_psd.savefig(pasta / "espectros_dinamicos.png", dpi=180)
    plt.close(fig_psd)

    print(tabela.to_string(index=False))
    print("\nResumo:")
    print(resumo.to_string(index=False))
    if args.freq_referencia is None:
        print(
            "ATENCAO: sem frequencia de referencia, o resultado demonstra repetibilidade, "
            "nao exatidao metrologica."
        )
    print(f"Resultados salvos em: {pasta.resolve()}")


if __name__ == "__main__":
    main()

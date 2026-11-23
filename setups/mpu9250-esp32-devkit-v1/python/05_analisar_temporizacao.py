"""Avalia taxa efetiva, jitter, lacunas, indices e perdas de amostras."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from comum import (
    DT_NOMINAL_US,
    FS_NOMINAL_HZ,
    frequencia_efetiva,
    garantir_pasta,
    ler_csv,
    localizar_csvs,
    preparar_matplotlib,
    salvar_json,
)


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analise temporal da aquisicao.")
    parser.add_argument("entradas", nargs="+")
    parser.add_argument("--fs-nominal", type=float, default=FS_NOMINAL_HZ)
    parser.add_argument("--saida", default="dados/processados/temporizacao")
    return parser.parse_args()


def main() -> None:
    args = argumentos()
    preparar_matplotlib()
    import matplotlib.pyplot as plt

    arquivos = localizar_csvs(args.entradas)
    pasta = garantir_pasta(args.saida)
    dt_nominal = 1e6 / args.fs_nominal
    linhas: list[dict] = []

    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    for caminho in arquivos:
        dados = ler_csv(caminho)
        indices = dados["indice"].to_numpy(dtype=np.int64)
        tempos = dados["t_us"].to_numpy(dtype=np.float64)
        dt = np.diff(tempos)
        dindice = np.diff(indices)

        indices_ausentes = int(np.sum(np.clip(dindice - 1, 0, None)))
        indices_repetidos = int(np.sum(dindice == 0))
        indices_fora_ordem = int(np.sum(dindice < 0))
        timestamps_nao_crescentes = int(np.sum(dt <= 0))
        lacunas_15 = int(np.sum(dt > 1.5 * dt_nominal))
        perdas_por_dt = int(np.sum(np.clip(np.rint(dt / dt_nominal).astype(int) - 1, 0, None)))
        perdas_firmware = (
            int(dados["perdidas_acum"].max()) if "perdidas_acum" in dados.columns else 0
        )
        denominador = len(dados) + max(indices_ausentes, perdas_firmware)
        perda_pct = (
            max(indices_ausentes, perdas_firmware) / denominador * 100.0
            if denominador > 0
            else float("nan")
        )
        fs = frequencia_efetiva(dados)
        erro_fs_pct = (fs - args.fs_nominal) / args.fs_nominal * 100.0
        dp_dt = float(np.std(dt, ddof=1)) if len(dt) > 1 else float("nan")

        aprovado = bool(
            abs(erro_fs_pct) <= 1.0
            and dp_dt <= 0.01 * dt_nominal
            and float(np.max(dt)) <= 1.5 * dt_nominal
            and perda_pct <= 0.1
            and indices_repetidos == 0
            and indices_fora_ordem == 0
            and timestamps_nao_crescentes == 0
        )
        linhas.append(
            {
                "arquivo": str(caminho),
                "n": len(dados),
                "fs_nominal_hz": args.fs_nominal,
                "fs_efetiva_hz": fs,
                "erro_fs_pct": erro_fs_pct,
                "dt_nominal_us": dt_nominal,
                "dt_media_us": float(np.mean(dt)),
                "dt_dp_us": dp_dt,
                "dt_dp_pct_nominal": dp_dt / dt_nominal * 100.0,
                "dt_min_us": float(np.min(dt)),
                "dt_max_us": float(np.max(dt)),
                "dt_p99_us": float(np.percentile(dt, 99)),
                "dt_p999_us": float(np.percentile(dt, 99.9)),
                "lacunas_acima_1_5dt": lacunas_15,
                "perdas_estimadas_por_dt": perdas_por_dt,
                "indices_ausentes": indices_ausentes,
                "indices_repetidos": indices_repetidos,
                "indices_fora_de_ordem": indices_fora_ordem,
                "timestamps_nao_crescentes": timestamps_nao_crescentes,
                "perdas_informadas_firmware": perdas_firmware,
                "perda_pct": perda_pct,
                "aprovado_criterios_operacionais": aprovado,
            }
        )
        ax.hist(
            dt,
            bins=100,
            histtype="step",
            linewidth=1.1,
            label=caminho.stem[:35],
        )

    tabela = pd.DataFrame(linhas)
    tabela.to_csv(pasta / "metricas_temporizacao.csv", index=False)
    ax.axvline(dt_nominal, color="black", linestyle="--", label="dt nominal")
    ax.set(
        title="Distribuicao dos intervalos entre amostras",
        xlabel="Delta t (microssegundos)",
        ylabel="Contagem",
    )
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(pasta / "histograma_delta_t.png", dpi=180)
    plt.close(fig)

    salvar_json(
        {
            "criterios_operacionais_do_projeto": {
                "erro_taxa_pct_max_abs": 1.0,
                "desvio_padrao_dt_pct_nominal_max": 1.0,
                "dt_max_multiplo_nominal": 1.5,
                "perda_pct_max": 0.1,
                "indices_repetidos": 0,
                "timestamps_nao_crescentes": 0,
            },
            "nota": (
                "Estes limites sao decisoes operacionais do projeto, nao limites "
                "universais impostos por uma norma de acelerometros."
            ),
        },
        pasta / "criterios_temporizacao.json",
    )
    print(tabela.to_string(index=False))
    print(f"Resultados salvos em: {pasta.resolve()}")


if __name__ == "__main__":
    main()


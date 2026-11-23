"""Calcula offset e sensibilidade diagonal usando seis posicoes estaticas."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from comum import (
    EIXOS,
    G0,
    SENSIBILIDADE_NOMINAL_LSB_G,
    descartar_inicio,
    garantir_pasta,
    ler_csv,
    localizar_csvs,
    metadados_laterais,
    preparar_matplotlib,
    salvar_json,
)


POSICOES = {
    "xpos": ("x", +1, np.array([+1.0, 0.0, 0.0])),
    "xneg": ("x", -1, np.array([-1.0, 0.0, 0.0])),
    "ypos": ("y", +1, np.array([0.0, +1.0, 0.0])),
    "yneg": ("y", -1, np.array([0.0, -1.0, 0.0])),
    "zpos": ("z", +1, np.array([0.0, 0.0, +1.0])),
    "zneg": ("z", -1, np.array([0.0, 0.0, -1.0])),
}


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibracao estatica diagonal por X+/X-/Y+/Y-/Z+/Z-."
    )
    parser.add_argument("entradas", nargs="+", help="CSV(s) ou pasta contendo as aquisicoes")
    parser.add_argument("--sensor", default="MPU6050-01")
    parser.add_argument("--descartar", type=float, default=2.0)
    parser.add_argument("--saida", default="dados/calibracao")
    return parser.parse_args()


def normalizar_posicao(texto: str) -> str | None:
    limpo = texto.lower().replace("+", "pos").replace("-", "neg")
    limpo = "".join(c for c in limpo if c.isalnum())
    aliases = {
        "xpositivo": "xpos", "xpos": "xpos",
        "xnegativo": "xneg", "xneg": "xneg",
        "ypositivo": "ypos", "ypos": "ypos",
        "ynegativo": "yneg", "yneg": "yneg",
        "zpositivo": "zpos", "zpos": "zpos",
        "znegativo": "zneg", "zneg": "zneg",
    }
    for chave, valor in aliases.items():
        if chave in limpo:
            return valor
    return None


def descobrir_posicao(caminho: Path) -> str:
    meta = metadados_laterais(caminho)
    posicao = normalizar_posicao(str(meta.get("posicao", "")))
    if posicao:
        return posicao
    posicao = normalizar_posicao(caminho.stem)
    if posicao:
        return posicao
    raise ValueError(
        f"Nao foi possivel identificar a posicao de {caminho}. "
        "Use Xpos, Xneg, Ypos, Yneg, Zpos ou Zneg no nome/metadado."
    )


def main() -> None:
    args = argumentos()
    preparar_matplotlib()
    import matplotlib.pyplot as plt

    arquivos = localizar_csvs(args.entradas)
    grupos: dict[str, list[dict]] = defaultdict(list)
    linhas_resumo: list[dict] = []

    for caminho in arquivos:
        posicao = descobrir_posicao(caminho)
        dados = descartar_inicio(ler_csv(caminho), args.descartar)
        medias = {
            eixo: float(dados[f"a{eixo}_raw"].mean())
            for eixo in EIXOS
        }
        desvios = {
            eixo: float(dados[f"a{eixo}_raw"].std(ddof=1))
            for eixo in EIXOS
        }
        item = {"arquivo": str(caminho), "medias": medias, "desvios": desvios}
        grupos[posicao].append(item)
        linhas_resumo.append(
            {
                "arquivo": str(caminho),
                "posicao": posicao,
                "n": len(dados),
                **{f"media_a{e}_raw": medias[e] for e in EIXOS},
                **{f"dp_a{e}_raw": desvios[e] for e in EIXOS},
            }
        )

    ausentes = sorted(set(POSICOES).difference(grupos))
    if ausentes:
        raise ValueError(f"Faltam aquisicoes das posicoes: {ausentes}")

    media_posicao = {
        pos: {
            eixo: float(np.mean([item["medias"][eixo] for item in itens]))
            for eixo in EIXOS
        }
        for pos, itens in grupos.items()
    }

    offsets: dict[str, float] = {}
    sensibilidades: dict[str, float] = {}
    for eixo in EIXOS:
        positivo = media_posicao[f"{eixo}pos"][eixo]
        negativo = media_posicao[f"{eixo}neg"][eixo]
        offsets[eixo] = (positivo + negativo) / 2.0
        sensibilidades[eixo] = (positivo - negativo) / 2.0
        if abs(sensibilidades[eixo]) < 1000:
            raise ValueError(
                f"Sensibilidade calculada muito baixa no eixo {eixo.upper()}. "
                "Confira a identificacao das posicoes."
            )

    residuos: list[dict] = []
    for posicao, itens in grupos.items():
        alvo = POSICOES[posicao][2]
        for item in itens:
            medido = np.array(
                [
                    (item["medias"][e] - offsets[e]) / sensibilidades[e]
                    for e in EIXOS
                ]
            )
            residuos.append(
                {
                    "arquivo": item["arquivo"],
                    "posicao": posicao,
                    "ax_corr_g": medido[0],
                    "ay_corr_g": medido[1],
                    "az_corr_g": medido[2],
                    "modulo_g": float(np.linalg.norm(medido)),
                    "erro_modulo_pct": abs(float(np.linalg.norm(medido)) - 1.0) * 100,
                    "erro_vetorial_g": float(np.linalg.norm(medido - alvo)),
                }
            )

    erros_escala = {
        eixo: (abs(sensibilidades[eixo]) - SENSIBILIDADE_NOMINAL_LSB_G)
        / SENSIBILIDADE_NOMINAL_LSB_G
        * 100.0
        for eixo in EIXOS
    }
    offsets_mg = {
        eixo: offsets[eixo] / abs(sensibilidades[eixo]) * 1000.0
        for eixo in EIXOS
    }

    pasta = garantir_pasta(args.saida)
    caminho_cal = pasta / f"calibracao_{args.sensor.lower()}.json"
    resultado = {
        "formato": "calibracao_diagonal_seis_posicoes_v1",
        "data_utc": datetime.now(timezone.utc).isoformat(),
        "identificacao_sensor": args.sensor,
        "metodo": "seis_posicoes_estaticas_gravidade",
        "gravidade_convencional_ms2": G0,
        "descartar_inicio_s": args.descartar,
        "offset_lsb": offsets,
        "offset_mg": offsets_mg,
        "sensibilidade_lsb_g": sensibilidades,
        "sensibilidade_nominal_lsb_g": SENSIBILIDADE_NOMINAL_LSB_G,
        "erro_escala_pct": erros_escala,
        "media_por_posicao_raw": media_posicao,
        "numero_arquivos_por_posicao": {p: len(v) for p, v in grupos.items()},
        "arquivos": [str(p) for p in arquivos],
        "observacao": (
            "Modelo diagonal: corrige offset e escala de cada eixo; nao estima "
            "a matriz completa de desalinhamento/sensibilidade transversal."
        ),
    }
    salvar_json(resultado, caminho_cal)
    pd.DataFrame(linhas_resumo).to_csv(pasta / "calibracao_medias_brutas.csv", index=False)
    pd.DataFrame(residuos).to_csv(pasta / "calibracao_residuos.csv", index=False)

    fig, eixos_fig = plt.subplots(1, 2, figsize=(11, 4.8))
    eixos_fig[0].bar([e.upper() for e in EIXOS], [offsets_mg[e] for e in EIXOS])
    eixos_fig[0].axhline(0, color="black", linewidth=0.8)
    eixos_fig[0].set(title="Offset estimado", ylabel="Offset (mg)")
    eixos_fig[0].grid(True, axis="y", alpha=0.3)
    eixos_fig[1].bar([e.upper() for e in EIXOS], [abs(sensibilidades[e]) for e in EIXOS])
    eixos_fig[1].axhline(
        SENSIBILIDADE_NOMINAL_LSB_G,
        color="tab:red",
        linestyle="--",
        label="Nominal",
    )
    eixos_fig[1].set(title="Sensibilidade estimada", ylabel="LSB/g")
    eixos_fig[1].grid(True, axis="y", alpha=0.3)
    eixos_fig[1].legend()
    fig.tight_layout()
    fig.savefig(pasta / "calibracao_parametros.png", dpi=180)
    plt.close(fig)

    print("Calibracao concluida")
    for eixo in EIXOS:
        print(
            f"{eixo.upper()}: offset={offsets[eixo]:.3f} LSB "
            f"({offsets_mg[eixo]:.3f} mg); "
            f"sensibilidade={sensibilidades[eixo]:.3f} LSB/g; "
            f"erro de escala={erros_escala[eixo]:.3f}%"
        )
    print(f"Arquivo de calibracao: {caminho_cal.resolve()}")


if __name__ == "__main__":
    main()


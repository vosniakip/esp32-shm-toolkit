"""Monta um resumo Markdown sem alterar resultados individuais."""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import pandas as pd


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera indice dos resultados processados.")
    parser.add_argument("--raiz", default="dados/processados")
    parser.add_argument("--saida", default="dados/processados/RELATORIO_RESUMO.md")
    parser.add_argument("--max-linhas", type=int, default=20)
    return parser.parse_args()


def tabela_markdown(df: pd.DataFrame, max_linhas: int) -> str:
    amostra = df.head(max_linhas).copy()
    amostra = amostra.fillna("")
    colunas = [str(c) for c in amostra.columns]
    linhas = ["| " + " | ".join(colunas) + " |"]
    linhas.append("| " + " | ".join(["---"] * len(colunas)) + " |")
    for _, registro in amostra.iterrows():
        valores = []
        for valor in registro:
            if isinstance(valor, float):
                texto = f"{valor:.6g}"
            else:
                texto = str(valor)
            valores.append(texto.replace("|", "\\|"))
        linhas.append("| " + " | ".join(valores) + " |")
    if len(df) > max_linhas:
        linhas.append(f"\n_Apenas as primeiras {max_linhas} de {len(df)} linhas são exibidas._")
    return "\n".join(linhas)


def main() -> None:
    args = argumentos()
    raiz = Path(args.raiz)
    if not raiz.exists():
        raise FileNotFoundError(f"Pasta nao encontrada: {raiz}")
    destino = Path(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)

    csvs = sorted(p for p in raiz.rglob("*.csv") if p.resolve() != destino.resolve())
    figuras = sorted([*raiz.rglob("*.png"), *raiz.rglob("*.svg")])
    linhas = [
        "# Resumo dos ensaios GY-9250/ESP32",
        "",
        f"Gerado em: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "> Este arquivo é um índice. Os CSVs e JSONs originais continuam sendo os resultados oficiais.",
        "",
    ]

    for caminho in csvs:
        relativo = caminho.relative_to(raiz)
        linhas.extend([f"## {relativo}", ""])
        try:
            tabela = pd.read_csv(caminho)
            linhas.extend([tabela_markdown(tabela, args.max_linhas), ""])
        except Exception as erro:
            linhas.extend([f"Não foi possível pré-visualizar: `{erro}`", ""])

    if figuras:
        linhas.extend(["# Figuras", ""])
        for figura in figuras:
            relativo = Path(os.path.relpath(figura.resolve(), destino.parent.resolve()))
            linhas.append(f"- [{figura.name}]({relativo.as_posix()})")

    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"Resumo gerado: {destino.resolve()}")


if __name__ == "__main__":
    main()

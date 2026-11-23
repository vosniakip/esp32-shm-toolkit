"""Verificacao funcional de um arquivo estatico pela gravidade."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from comum import (
    carregar_calibracao,
    converter_para_g,
    descartar_inicio,
    frequencia_efetiva,
    garantir_pasta,
    ler_csv,
    preparar_matplotlib,
    salvar_json,
)


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verifica resposta estatica dos tres eixos.")
    parser.add_argument("arquivo")
    parser.add_argument("--calibracao")
    parser.add_argument("--descartar", type=float, default=2.0)
    parser.add_argument("--saida", default="dados/processados/verificacao_funcional")
    return parser.parse_args()


def main() -> None:
    args = argumentos()
    preparar_matplotlib()
    import matplotlib.pyplot as plt

    caminho = Path(args.arquivo)
    calibracao = carregar_calibracao(args.calibracao)
    dados = converter_para_g(ler_csv(caminho), calibracao)
    usados = descartar_inicio(dados, args.descartar)

    medias = {e: float(usados[f"a{e}_g"].mean()) for e in "xyz"}
    desvios = {e: float(usados[f"a{e}_g"].std(ddof=1)) for e in "xyz"}
    unicos = {e: int(usados[f"a{e}_raw"].nunique()) for e in "xyz"}
    modulo_medio = float(np.sqrt(sum(medias[e] ** 2 for e in "xyz")))
    eixo_dominante = max("xyz", key=lambda e: abs(medias[e]))
    saturacao = bool(
        np.any(np.abs(usados[["ax_raw", "ay_raw", "az_raw"]].to_numpy()) >= 32760)
    )

    alertas: list[str] = []
    if not 0.8 <= modulo_medio <= 1.2:
        alertas.append("Modulo medio fora da faixa de verificacao pratica 0,8 a 1,2 g.")
    if any(valor < 2 for valor in unicos.values()):
        alertas.append("Ao menos um eixo apresentou menos de dois valores distintos.")
    if saturacao:
        alertas.append("Foi detectada saturacao proxima ao limite de 16 bits.")

    resultado = {
        "arquivo": str(caminho.resolve()),
        "calibracao": calibracao.caminho or "nominal",
        "amostras_total": len(dados),
        "amostras_analisadas": len(usados),
        "fs_efetiva_hz": frequencia_efetiva(dados),
        "media_g": medias,
        "desvio_padrao_g": desvios,
        "valores_brutos_distintos": unicos,
        "modulo_da_media_g": modulo_medio,
        "eixo_dominante": eixo_dominante,
        "saturacao": saturacao,
        "alertas": alertas,
    }

    pasta = garantir_pasta(args.saida)
    base = caminho.stem
    salvar_json(resultado, pasta / f"{base}_verificacao.json")

    t = (dados["t_us"].to_numpy() - dados["t_us"].iloc[0]) / 1e6
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for eixo, cor in zip("xyz", ("tab:red", "tab:green", "tab:blue")):
        ax.plot(
            t,
            dados[f"a{eixo}_g"],
            label=eixo.upper(),
            color=cor,
            linewidth=0.8,
        )
    ax.set(title="Verificacao funcional", xlabel="Tempo (s)", ylabel="Aceleracao (g)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(pasta / f"{base}_sinal.png", dpi=180)
    plt.close(fig)

    print("Verificacao funcional concluida")
    print(f"Medias [g]: X={medias['x']:.6f}, Y={medias['y']:.6f}, Z={medias['z']:.6f}")
    print(f"Modulo da media: {modulo_medio:.6f} g")
    print(f"Eixo dominante: {eixo_dominante.upper()}")
    if alertas:
        print("Alertas:")
        for alerta in alertas:
            print(f"  - {alerta}")
    else:
        print("Nenhum alerta funcional basico.")
    print(f"Resultados: {pasta.resolve()}")


if __name__ == "__main__":
    main()

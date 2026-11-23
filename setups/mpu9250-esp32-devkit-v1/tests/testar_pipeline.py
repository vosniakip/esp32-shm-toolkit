"""Executa os analisadores com dados sinteticos e verifica arquivos principais."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def executar(*argumentos: str) -> None:
    ambiente = os.environ.copy()
    ambiente["PYTHONPATH"] = str(RAIZ / "python")
    ambiente["MPLCONFIGDIR"] = str(RAIZ / "tests" / ".matplotlib")
    comando = [PYTHON, *argumentos]
    print("EXECUTANDO:", " ".join(comando))
    subprocess.run(comando, cwd=RAIZ, env=ambiente, check=True)


def exigir(caminho: Path) -> None:
    if not caminho.exists() or caminho.stat().st_size == 0:
        raise AssertionError(f"Resultado ausente ou vazio: {caminho}")


def main() -> None:
    executar("tests/gerar_dados_sinteticos.py")
    dados = RAIZ / "tests" / "dados_sinteticos"
    saida = RAIZ / "tests" / "saida_pipeline"
    calibracao = saida / "calibracao" / "calibracao_gy9250-teste.json"

    executar(
        "python/03_calibrar_seis_posicoes.py",
        str(dados / "calibracao"),
        "--sensor", "GY9250-TESTE",
        "--descartar", "0",
        "--saida", str(saida / "calibracao"),
    )
    exigir(calibracao)

    funcional = sorted((dados / "repouso").glob("*.csv"))[0]
    executar(
        "python/02_verificar_funcional.py", str(funcional),
        "--calibracao", str(calibracao),
        "--descartar", "0",
        "--saida", str(saida / "funcional"),
    )
    executar(
        "python/04_analisar_ruido_psd.py", str(dados / "repouso"),
        "--calibracao", str(calibracao),
        "--descartar", "0",
        "--saida", str(saida / "ruido"),
    )
    executar(
        "python/05_analisar_temporizacao.py", str(dados / "repouso"),
        "--saida", str(saida / "tempo"),
    )
    executar(
        "python/06_analisar_repetibilidade.py", str(dados / "repouso"),
        "--calibracao", str(calibracao),
        "--descartar", "0",
        "--saida", str(saida / "repetibilidade"),
    )
    executar(
        "python/07_analisar_deriva_termica.py", str(dados / "outros" / "teste_aquecimento.csv"),
        "--calibracao", str(calibracao),
        "--saida", str(saida / "termica"),
    )
    raiz_dinamica = saida / "dinamico"
    anteriores = set(raiz_dinamica.glob("*")) if raiz_dinamica.exists() else set()
    executar(
        "python/08_analisar_dinamico.py", str(dados / "dinamico"),
        "--calibracao", str(calibracao),
        "--saida", str(raiz_dinamica),
    )
    novas = set(raiz_dinamica.glob("*")) - anteriores
    if len(novas) != 1:
        raise AssertionError(f"Esperada uma nova pasta dinamica; obtidas: {novas}")
    pasta_dinamica = novas.pop()
    executar(
        "python/09_desvio_allan.py", str(dados / "outros" / "teste_aquecimento.csv"),
        "--calibracao", str(calibracao),
        "--pontos", "30",
        "--saida", str(saida / "allan"),
    )

    exigir(saida / "ruido" / "metricas_ruido_agregadas.csv")
    exigir(saida / "tempo" / "metricas_temporizacao.csv")
    exigir(saida / "repetibilidade" / "repetibilidade_agregada.csv")
    exigir(saida / "termica" / "teste_aquecimento_deriva_resumo.json")
    exigir(pasta_dinamica / "resumo_dinamico.csv")
    exigir(pasta_dinamica / "analise.json")
    exigir(saida / "allan" / "teste_aquecimento_desvio_allan.csv")
    print("PIPELINE VALIDADO COM DADOS SINTETICOS")


if __name__ == "__main__":
    main()

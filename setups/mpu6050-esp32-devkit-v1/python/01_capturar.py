"""Captura os dados enviados pelo ESP32 e salva CSV bruto + JSON de metadados.

Exemplo:
    python python/01_capturar.py --porta COM5 --duracao 120 \
        --ensaio repouso --posicao Zpos --repeticao 1
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import serial
from serial.tools import list_ports

from comum import garantir_pasta, nome_seguro, salvar_json


COLUNAS = [
    "indice",
    "t_us",
    "ax_raw",
    "ay_raw",
    "az_raw",
    "temp_raw",
    "perdidas_acum",
    "erros_i2c",
]


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Captura dados brutos do firmware MPU-6050/GY-521 com ESP32."
    )
    parser.add_argument("--porta", help="Porta serial, por exemplo COM5 ou /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=460800)
    parser.add_argument("--duracao", type=float, required=True, help="Duracao em segundos")
    parser.add_argument("--ensaio", required=True, help="Ex.: repouso, calibracao, dinamico")
    parser.add_argument("--posicao", default="na", help="Ex.: Xpos, Xneg, Ypos, Zpos")
    parser.add_argument("--repeticao", type=int, default=1)
    parser.add_argument("--sensor", default="MPU6050-01")
    parser.add_argument("--observacao", default="")
    parser.add_argument("--saida-raiz", default="dados/brutos")
    parser.add_argument(
        "--espera-reset",
        type=float,
        default=2.5,
        help="Espera apos abrir a porta; o ESP32 costuma reiniciar",
    )
    return parser.parse_args()


def escolher_porta(porta_informada: str | None) -> str:
    if porta_informada:
        return porta_informada
    portas = list(list_ports.comports())
    if len(portas) == 1:
        print(f"Usando a unica porta encontrada: {portas[0].device}")
        return portas[0].device
    if not portas:
        raise RuntimeError("Nenhuma porta serial encontrada")
    opcoes = ", ".join(p.device for p in portas)
    raise RuntimeError(f"Mais de uma porta encontrada ({opcoes}). Use --porta COMx.")


def hash_firmware() -> str | None:
    caminho = (
        Path(__file__).resolve().parents[1]
        / "firmware"
        / "mpu6050_aquisicao"
        / "mpu6050_aquisicao.ino"
    )
    if not caminho.exists():
        return None
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def construir_caminhos(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    agora = datetime.now()
    pasta_dia = garantir_pasta(
        Path(args.saida_raiz)
        / agora.strftime("%Y-%m-%d")
        / nome_seguro(args.ensaio)
    )
    base = "_".join(
        [
            agora.strftime("%Y%m%d_%H%M%S"),
            nome_seguro(args.sensor),
            nome_seguro(args.ensaio),
            nome_seguro(args.posicao),
            f"r{args.repeticao:02d}",
        ]
    )
    return pasta_dia, pasta_dia / f"{base}.csv", pasta_dia / f"{base}.json"


def interpretar_linha_dados(linha: str) -> list[int] | None:
    partes = linha.split(",")
    if len(partes) != 9 or partes[0] != "D":
        return None
    try:
        return [int(valor) for valor in partes[1:]]
    except ValueError:
        return None


def main() -> int:
    args = argumentos()
    if args.duracao <= 0:
        print("ERRO: --duracao deve ser maior que zero", file=sys.stderr)
        return 2

    try:
        porta = escolher_porta(args.porta)
    except RuntimeError as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 2

    pasta, caminho_csv, caminho_json = construir_caminhos(args)
    caminho_log = caminho_csv.with_suffix(".log.txt")
    inicio_utc = datetime.now(timezone.utc)
    linhas_validas = 0
    linhas_invalidas = 0
    mensagem_info: list[str] = []
    mensagem_final = ""
    captura_interrompida = False

    print(f"Pasta: {pasta.resolve()}")
    print(f"Abrindo {porta} a {args.baud} baud...")

    with serial.Serial(porta, args.baud, timeout=0.25) as conexao, \
            caminho_csv.open("w", newline="", encoding="utf-8") as arquivo_csv, \
            caminho_log.open("w", encoding="utf-8") as arquivo_log:
        escritor = csv.writer(arquivo_csv)
        escritor.writerow(COLUNAS)

        time.sleep(args.espera_reset)
        conexao.reset_input_buffer()
        conexao.write(b"INFO\n")
        conexao.flush()

        instante_limite_info = time.monotonic() + 1.0
        while time.monotonic() < instante_limite_info:
            bruto = conexao.readline()
            if not bruto:
                continue
            linha = bruto.decode("utf-8", errors="replace").strip()
            arquivo_log.write(linha + "\n")
            if linha.startswith("#INFO") or linha.startswith("#READY"):
                mensagem_info.append(linha)

        duracao_ms = int(round(args.duracao * 1000.0))
        conexao.write(f"START,{duracao_ms}\n".encode("ascii"))
        conexao.flush()
        limite_seg = args.duracao + 15.0
        inicio_espera = time.monotonic()

        print("Aquisicao iniciada. Nao movimente a montagem fora do roteiro.")
        try:
            while time.monotonic() - inicio_espera < limite_seg:
                bruto = conexao.readline()
                if not bruto:
                    continue
                linha = bruto.decode("utf-8", errors="replace").strip()
                if not linha:
                    continue
                if linha.startswith("#"):
                    arquivo_log.write(linha + "\n")
                    if linha.startswith("#END"):
                        mensagem_final = linha
                        break
                    if linha.startswith("#FATAL"):
                        raise RuntimeError(linha)
                    continue

                valores = interpretar_linha_dados(linha)
                if valores is None:
                    linhas_invalidas += 1
                    arquivo_log.write("LINHA_INVALIDA: " + linha + "\n")
                    continue
                escritor.writerow(valores)
                linhas_validas += 1

                if linhas_validas % 2500 == 0:
                    print(f"  {linhas_validas} amostras recebidas")
        except KeyboardInterrupt:
            captura_interrompida = True
            print("Interrupcao solicitada; finalizando arquivo parcial...")
            conexao.write(b"STOP\n")
            conexao.flush()

    fim_utc = datetime.now(timezone.utc)
    metadados = {
        "formato": "MPU6050_ESP32_v1",
        "sensor": args.sensor,
        "ensaio": args.ensaio,
        "posicao": args.posicao,
        "repeticao": args.repeticao,
        "observacao": args.observacao,
        "porta": porta,
        "baud": args.baud,
        "duracao_s_solicitada": args.duracao,
        "inicio_utc": inicio_utc.isoformat(),
        "fim_utc": fim_utc.isoformat(),
        "amostras_recebidas": linhas_validas,
        "linhas_invalidas": linhas_invalidas,
        "captura_interrompida": captura_interrompida,
        "mensagens_info": mensagem_info,
        "mensagem_final": mensagem_final,
        "arquivo_csv": str(caminho_csv.resolve()),
        "arquivo_log": str(caminho_log.resolve()),
        "computador": platform.platform(),
        "python": platform.python_version(),
        "firmware_fonte_local_sha256": hash_firmware(),
    }
    salvar_json(metadados, caminho_json)

    if linhas_validas == 0:
        print("ERRO: nenhum dado valido foi recebido. Consulte o arquivo de log.")
        return 1

    print(f"Concluido: {linhas_validas} amostras")
    print(f"CSV bruto: {caminho_csv.resolve()}")
    print(f"Metadados: {caminho_json.resolve()}")
    print(f"Log: {caminho_log.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

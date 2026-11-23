"""Lista portas seriais disponiveis e ajuda a identificar o ESP32."""

from serial.tools import list_ports


def main() -> None:
    portas = list(list_ports.comports())
    if not portas:
        print("Nenhuma porta serial encontrada.")
        print("Confira o cabo USB de dados e o driver CP210x/CH340 da sua placa.")
        return

    print("Portas seriais encontradas:\n")
    for porta in portas:
        print(f"Porta: {porta.device}")
        print(f"  Descricao: {porta.description}")
        print(f"  Fabricante: {porta.manufacturer or 'nao informado'}")
        print(f"  VID:PID: {porta.vid!s}:{porta.pid!s}")
        print()


if __name__ == "__main__":
    main()


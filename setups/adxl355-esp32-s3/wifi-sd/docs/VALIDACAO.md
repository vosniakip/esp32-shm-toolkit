# Como verificar o pacote Wi-Fi/microSD

Instale as dependências em um ambiente Python. Na pasta do pacote, execute:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Os testes de software usam entradas artificiais criadas durante a execução.

O script `ferramentas/verificar_sintaxe_firmware.py` usa o compilador C++ e interfaces simuladas para verificar a sintaxe no computador. A compilação para o ESP32-S3 usa o Arduino-ESP32 e as opções de placa do guia de montagem.

Com o hardware montado, use o roteiro de primeira leitura. Confira a identificação do sensor, a temporização, a continuidade das amostras e a integridade dos arquivos antes de gravar séries longas. Para avaliar o armazenamento, complete uma captura na duração prevista e teste a transferência. A calibração exige capturas de ajuste e uma verificação independente.

# Solução de problemas

## `ModuleNotFoundError: No module named serial`

Ative `.venv` e execute:

```powershell
python -m pip install -r requirements.txt
```

## A porta COM não aparece

1. Feche Arduino IDE, PuTTY e outros terminais.
2. Troque o cabo por um cabo USB de dados.
3. Teste outra porta USB.
4. Verifique no Gerenciador de Dispositivos se a placa usa CP210x ou CH340.
5. Instale apenas o driver correspondente.

## `PermissionError` ou acesso negado à COM

Outro programa está usando a porta. Feche o Monitor Serial e reinicie o script.

## O script recebe zero amostras

1. Leia o `.log.txt`.
2. Confirme a presença de `#READY` e `#INFO`.
3. Confirme `INT -> GPIO27`.
4. Confirme `AD0 -> GND`.
5. Recarregue o firmware.
6. Não troque VCC para 5 V para tentar resolver.

## WHO_AM_I diferente de `0x71`

O módulo pode usar componente diferente, substituto ou clone. Registre o valor.
Não force a conclusão de que é um MPU-9250 autêntico apenas porque responde no
endereço `0x68`.

## Taxa próxima de 250 Hz, mas com lacunas

1. Use baud 460.800.
2. Use cabo USB curto e confiável.
3. Feche programas pesados.
4. Não imprima mensagens adicionais no firmware durante aquisição.
5. Verifique o contato do pino INT.
6. Inspecione `perdidas_acum` e `erros_i2c`.

## O gráfico de PSD tem um pico de 50/60 Hz

Pode haver interferência elétrica ou vibração de rede/motores. Não remova o pico
sem investigar. Registre fonte de alimentação, posição dos cabos e equipamentos
próximos. Repita com notebook alimentado pela bateria, se possível e seguro.

## Resultado estático desaparece depois do filtro

Isso é esperado se foi aplicado passa-altas de 0,5 Hz. Não use esse filtro na
calibração, no ensaio funcional, no aquecimento ou no desvio de Allan.

## Valores saturam

Na faixa ±2 g o limite digital é próximo de ±32.767 LSB. Reduza a excitação.
Somente se necessário mude para ±4 g, ajuste o firmware e documente a nova
sensibilidade nominal de 8.192 LSB/g. Não misture arquivos de faixas diferentes.

## Erro ao usar caminhos com espaços

Coloque o caminho entre aspas:

```powershell
python python/02_verificar_funcional.py "C:\Minha Pasta\arquivo.csv"
```


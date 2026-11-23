# Dicionário de dados

## CSV bruto

| Coluna | Tipo | Unidade | Significado |
|---|---|---|---|
| `indice` | inteiro | amostra | Contador sequencial iniciado em zero |
| `t_us` | inteiro de 64 bits | µs | Tempo relativo medido no ESP32 |
| `ax_raw` | inteiro com sinal de 16 bits | LSB | Saída bruta do eixo X |
| `ay_raw` | inteiro com sinal de 16 bits | LSB | Saída bruta do eixo Y |
| `az_raw` | inteiro com sinal de 16 bits | LSB | Saída bruta do eixo Z |
| `temp_raw` | inteiro com sinal de 16 bits | LSB | Saída bruta do sensor interno de temperatura |
| `perdidas_acum` | inteiro | amostras | Interrupções não recuperadas acumuladas |
| `erros_i2c` | inteiro | ocorrências | Falhas de leitura I²C acumuladas |

## Conversões

Sem calibração individual, para faixa ±2 g:

```text
aceleracao_g = valor_raw / 16384
```

Com calibração:

```text
aceleracao_g = (valor_raw - offset_lsb) / sensibilidade_lsb_g
aceleracao_ms2 = aceleracao_g * 9,80665
temperatura_c = temp_raw / 340 + 36,53
```

## JSON lateral da aquisição

O JSON guarda a identidade do ensaio, duração solicitada, porta, horário,
número de amostras, mensagens de configuração, observações, versão do Python e
hash do arquivo-fonte local do firmware.

O hash do arquivo-fonte não comprova sozinho que o binário correspondente está
gravado no ESP32. A mensagem `#INFO` deve ser preservada juntamente com ele.

## JSON de calibração

Os campos principais são:

- `offset_lsb`: offset de X, Y e Z;
- `offset_mg`: os mesmos offsets expressos em mg;
- `sensibilidade_lsb_g`: sensibilidade individual de cada eixo;
- `erro_escala_pct`: diferença relativa ao valor nominal;
- `media_por_posicao_raw`: médias utilizadas no ajuste;
- `arquivos`: lista das aquisições que originaram a calibração.

## Unidades dos resultados espectrais

- PSD: `g²/Hz`;
- ASD: `g/√Hz`;
- RMS integrado: `g`;
- frequência: `Hz`.

Para converter `g` em `m/s²`, multiplique por 9,80665.

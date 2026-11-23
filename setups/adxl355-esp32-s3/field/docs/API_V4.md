# Firmware v4 e compatibilidade

A v4 preserva o transporte e o formato binário SD V3. Portanto, `A355SD3`, `BLK3`, `END3`, os esquemas de metadados e o registro bruto de 32 bytes continuam iguais. O campo firmware informa 4.0.0 e os conversores desta entrega registram a versão do pacote 4.0.0. O detalhamento estrutural permanece em `API_E_FORMATO_BASE.md`.

## Alterações de controle

- Perfis de treliça, shaker e passarela na interface web.
- Endpoint `POST /api/mark`, com campo rotulo de até 24 caracteres ASCII, números, `_` e `-`.
- GPIO4 opcional para marcas físicas, desativado por padrão.
- Até 128 marcas por aquisição, compartilhadas entre HTTP e entrada externa.
- `start_boot_us` e `agora_boot_us` no status, além das contagens de marcas.
- Metadados finais com marcas_evento, marcas_descartadas e marcas_externas_habilitadas.
- Namespace NVS a355v4, separado do agendamento de partida a frio da v3. Um agendamento antigo não é disparado pela v4.

## Log

O cabeçalho continua `boot_us,event,value`.

Para `pulso_externo`, value contém a diferença, em microssegundos, entre a marca e start_boot_us. Para uma marca HTTP, o evento começa por `http_` seguido do rótulo, e value tem o mesmo significado temporal. Marcas anteriores ao início útil podem ser negativas; elas devem ser interpretadas com a duração e o domínio da campanha.

As linhas inicio, fim e amostras_gravadas continuam presentes. A linha marcas_descartadas informa estouro da capacidade de eventos. Nenhuma rotina escreve arquivos no cartão a partir de uma interrupção: as marcas ficam em RAM e entram no log durante a finalização. As amostras também usam fila e tarefa de gravação.

## Consistência e interrupções

Os downloads e a listagem do cartão permanecem bloqueados durante a sequência para evitar acesso concorrente com a gravação. STATUS e marcas HTTP são leves e permanecem acessíveis com rádio ativo. Se o rádio for desligado pelo perfil, o comando remoto fica indisponível até o retorno da rede.

O comando START possui request_id, e a repetição do mesmo identificador retorna o estado existente enquanto ele é retido pelo nó. Essa proteção não é uma transação distribuída persistente através de qualquer reinicialização. Depois de um resultado incerto ou reinício, consulte o cartão e os comandos locais, sem reenviar automaticamente um ensaio.

Uma marca de GPIO não é o início da conversão interna do ADXL355. Os tempos das amostras correspondem à chegada de DRDY ao ESP32, incluindo a latência de aquisição/ISR e a resposta do filtro interno. A calibração do relógio por marcas não remove automaticamente esses atrasos.

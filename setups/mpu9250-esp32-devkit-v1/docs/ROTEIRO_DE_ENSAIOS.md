# Roteiro operacional dos ensaios

## 1. Antes de qualquer campanha

1. Confira VCC, GND, SDA, SCL, INT e AD0.
2. Confirme que a montagem não encosta em metal.
3. Abra o Arduino IDE apenas para carregar o firmware.
4. Feche o Monitor Serial.
5. Ative o ambiente Python.
6. Execute `00_listar_portas.py`.
7. Fotografe a montagem e os eixos.
8. Preencha uma cópia de `templates/ficha_ensaio.json`.
9. Confirme faixa ±2 g, taxa 250 Hz e DLPF próximo de 92 Hz no log `#INFO`.
10. Não mexa nos fios com o USB conectado.

## 2. Funcional

1. Aqueça por 10 minutos.
2. Coloque Z+ para cima.
3. Aguarde cinco segundos.
4. Adquira 30 s.
5. Verifique módulo próximo de 1 g.
6. Gire manualmente e confirme que os eixos respondem.
7. Se algum eixo estiver travado ou houver saturação, interrompa a campanha.

## 3. Calibração em seis posições

1. Aqueça por 20 minutos.
2. Use um bloco com faces planas.
3. Faça X+, X−, Y+, Y−, Z+ e Z−.
4. Em cada posição, aguarde cinco segundos.
5. Adquira 60 s.
6. Faça três repetições independentes.
7. Não filtre, não retire média e não aplique 0,5–50 Hz.
8. Processe todos os arquivos simultaneamente.
9. Inspecione resíduos e erro do módulo corrigido.
10. Arquive o JSON de calibração.

## 4. Ruído, temporização e repetibilidade

1. Aqueça pelo tempo definido no ensaio térmico; enquanto ele não for conhecido,
   use 20 minutos.
2. Fixe o sensor em superfície rígida.
3. Prenda os cabos antes do módulo.
4. Afaste o computador da mesma mesa, se possível.
5. Faça cinco aquisições de 120 s.
6. Não toque na mesa.
7. Anote eventos externos: porta fechando, passos, veículo, ventilador.
8. Execute os scripts 04, 05 e 06.
9. Arquivos perturbados não devem ser apagados; marque-os como rejeitados e
   repita a aquisição.

## 5. Aquecimento

1. Deixe o conjunto desligado por 30 minutos.
2. Deixe o comando preparado.
3. Posicione o sensor imóvel.
4. Energize e inicie a aquisição imediatamente.
5. Adquira 3.600 s.
6. Registre temperatura ambiente manualmente a cada 10 minutos, se houver
   termômetro.
7. Não aplique passa-altas.
8. Determine visualmente e numericamente o tempo de estabilização.

## 6. Dinâmico em balanço

1. Use uma régua/lâmina rigidamente engastada.
2. Fixe o módulo rigidamente; não use espuma.
3. Faça alívio de tração nos cabos junto ao engaste.
4. Inicie a aquisição antes de excitar.
5. Aguarde 10 s.
6. Desloque pouco a extremidade e solte sem impacto.
7. Aguarde o decaimento.
8. Repita cinco arquivos com a mesma montagem.
9. Se os valores brutos se aproximarem de ±32.767, reduza a excitação.
10. Interprete frequência e CV como repetibilidade; sem referência não existe
    comprovação de exatidão de amplitude.

## 7. Desvio de Allan

1. Use montagem rígida e termicamente estável.
2. Aqueça por 30 minutos.
3. Adquira de duas a quatro horas, preferencialmente quatro.
4. Evite qualquer movimento.
5. Não aplique passa-altas nem retirada de tendência antes do cálculo.
6. Guarde o registro completo mesmo se houver perturbação; documente-a.

## 8. Comparação profissional posterior

1. Use suporte rígido comum aos dois sensores.
2. Alinhe os eixos sensíveis.
3. Registre modelo, série, sensibilidade e calibração da referência.
4. Sincronize os sinais ou registre evento comum.
5. Aplique a mesma banda aos dois sinais.
6. Compare frequência, amplitude, fase e coerência.
7. Elabore orçamento de incerteza.
8. Baseie o procedimento de comparação na ISO 16063-21.


# Versão 4.1.0 · 11 nov. 2026

- Campanha UFPR com um nó em P01 (meio A-B) e P02 (meio B-C), uma aquisição de 1200 s por ponto.
- Programa 27 cria campanha persistente, fixa o JSON real por SHA-256 e preserva tentativas e resultados.
- Início único por tentativa, retomada de download sem novo START e conferência de P01 antes de iniciar P02.
- Análise separada, persistência em quatro blocos, FDD local, comparação de PSD e consolidação de candidatas.
- Guia de campo ilustrado, ficha e perfis; comprimentos dos vãos a medir, sem presunção de igualdade.
- Atalhos P01/P02 no firmware; aquisição e formato binário preservados e compatíveis com v4.0.
- Oito testes novos, incluindo dois registros sintéticos de 600 mil amostras e falhas de comunicação.

# Histórico

## 4.0.0 - 4 nov. 2026

- Pacote separado derivado do firmware Wi-Fi/SD v3 recuperado.
- Perfis e controle de campanha para treliça, shaker e passarela.
- Importação explícita de referência profissional para SI, com hashes e preservação da exportação.
- Ajuste de deslocamento e escala de relógios por marcas, com domínio de validade e diagnóstico.
- Marcas HTTP e entrada física opcional GPIO4, desativada por padrão.
- Comparação senoidal por ajuste independente, com frequência efetiva e amplitude RMS.
- Comparação de impactos com métricas temporais condicionadas ao alinhamento.
- PP/Welch com persistência por blocos, FDD local e consolidação entre aquisições.
- FRF H1 opcional com força medida e médias de impactos distintos.
- Proteção de continuidade, saturação, integridade, identificadores e saídas sem sobreposição.
- Guia ilustrado, fichas, parâmetros explícitos, fontes verificadas e demonstração sintética.
- Formato SD V3 preservado; versão de firmware e processamento atualizada para 4.0.0.

A compilação real com o core Espressif e os ensaios físicos não foram realizados nesta entrega.

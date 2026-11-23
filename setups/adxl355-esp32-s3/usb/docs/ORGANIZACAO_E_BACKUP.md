# Organização e Excel

| Pasta | Conteúdo |
|---|---|
| firmware/adxl355_aquisicao | Firmware e configuração |
| python | Captura e análises |
| dados/brutos/data/ensaio/pasta_exclusiva | CSV, JSON e log |
| dados/calibracao/pasta_exclusiva | Coeficientes e avaliação das seis posições |
| dados/processados/tipo/pasta_exclusiva | Tabelas, PNG e manifesto |
| fichas | Modelo de ficha e planejamento |
| tests | Testes reproduzíveis de software |

Toda pasta exclusiva contém data, hora, microssegundos e sufixo aleatório. Os nomes internos das tabelas podem repetir porque cada execução tem sua própria pasta. Figuras ficam junto às tabelas correspondentes.

Identifique fisicamente cada módulo e use o mesmo nome em `--sensor`. Registre montagem, firmware, aquecimento e alterações. Copie brutos para um segundo local após a aquisição; preserve juntos CSV, JSON e log. Mantenha os dados excluídos com uma justificativa, sem apagar os originais.

Um caminho curto, como `C:\Ensaios\ADXL355_ESP32S3_Ensaios`, simplifica comandos. Caminhos com espaços e acentos funcionam entre aspas. Evite mover arquivos enquanto são gravados; sincronize ou copie depois.

Abra preferencialmente os **XLSX de resumo**, com valores numéricos nativos. A aparência com vírgula ou ponto decimal depende do Excel, sem mudar o número. Para importar CSV processado, use delimitador vírgula e interpretação decimal com ponto. Se uma etapa automática já removeu o ponto, volte ao texto original antes da conversão de tipo; mudar só a formatação não restaura os dígitos.

Não salve por cima do CSV bruto no Excel: o hash identificará a alteração. Uma planilha tem limite de 1.048.576 linhas; campanhas longas excedem esse limite. Use gráficos e resumos gerados pelo Python.

## Calibração e validação do conjunto

Mantenha campanhas `calibracao_completa` e `validacao_calibracao` separadas nos brutos. Conserve todos os pares CSV/JSON e logs. A matriz, as referências geométricas, as fotos e a ficha da montagem devem acompanhar o relatório de validação. Este relatório registra o SHA256 do calibracao.json, ligando a validação ao ajuste específico.

As análises continuam criando pastas exclusivas com data, hora, microssegundos e identificador. Os arquivos de resultado nunca devem substituir os brutos. Abra os resumos XLSX para evitar conversões automáticas de localidade no Excel. A nova coluna de coeficientes `valor` contém unidades distintas identificadas em `unidade`.

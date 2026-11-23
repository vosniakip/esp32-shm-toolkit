# Pastas de trabalho

Ao rodar os scripts na raiz do pacote, as capturas ficam em `dados/brutos/` e os resultados em `dados/calibracao/` e `dados/processados/`. Guarde juntos o CSV, o JSON e o log de cada aquisição. Cada execução cria uma pasta com data, hora e identificador.

Mantenha as capturas de `calibracao_completa` e `validacao_calibracao` separadas: a primeira campanha ajusta a matriz, e a segunda verifica o ajuste com novos dados. O pacote vem sem medições físicas ou coeficientes de calibração. Os testes geram e removem seus próprios sinais sintéticos.

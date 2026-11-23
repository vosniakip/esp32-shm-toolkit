# Teste sem o nó

Os testes de software criam seus próprios sinais e arquivos em diretórios temporários. Na pasta do pacote, depois de instalar as dependências, execute:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

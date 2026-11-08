# Guia de Contribuição para o urze

Obrigado pelo interesse em contribuir para o **urze**. O objetivo do projeto é manter um gerador leve, robusto e perfeitamente integrado no ecossistema Debian/GTK3.

---

## Princípios do Projeto

1. **Apenas Biblioteca Padrão (*Stdlib-Only*):**  
   O script `urze.py` não pode ter dependências externas. Qualquer funcionalidade adicionada ao gerador tem de recorrer exclusivamente à biblioteca padrão do Python.
2. **Compatibilidade:**  
   O código deve ser compatível com Python 3.9 ou superior.
3. **Consistência de Cabeçalhos:**  
   Todos os ficheiros de modelo (*templates*) gerados pelo `urze` devem manter o padrão de cabeçalho unificado com o papel do ficheiro, autor, data e ligação ao GitHub.
4. **Normas Debian:**  
   Os ficheiros de empacotamento gerados devem respeitar os padrões `debhelper` (nível de compatibilidade 13) e `pybuild`.

---

## Fluxo de Trabalho

1. Faz um **fork** deste repositório no GitHub.
2. Cria um novo ramo com a tua melhoria:
   ```bash
   git checkout -b feature/nome-da-melhoria
   ```
3. Testa a geração de um projeto completo e os respetivos testes de fumo:
   ```bash
   python3 urze.py teste-app -y
   cd teste-app
   ./scripts/install.py --check
   PYTHONPATH=src python3 -m pytest -q
   ```
4. Assegura-te de que os ficheiros gerados mantêm as permissões corretas (ex.: `run`, `install.py`, `build_packages.sh`, `build_appimage.sh`, `build_windows.sh` e `build_macos.sh` com permissão de execução `0o755`).
5. Cria commits com mensagens descritivas.
6. Submete um **Pull Request** detalhando as alterações efetuadas.
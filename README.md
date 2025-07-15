# Ollama GUI - Interface gráfica para o Ollama

![GitHub License](https://img.shields.io/github/license/chyok/ollama-gui)
![PyPI - Version](https://img.shields.io/pypi/v/ollama-gui)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ollama-gui)

**Ollama GUI** é uma aplicação desktop para Windows, Linux e macOS, desenvolvida em Python com Qt (PySide6), que fornece uma interface gráfica moderna para conversar com modelos de IA locais via [Ollama](https://ollama.com). Permite gerenciar modelos, baixar, excluir e interagir facilmente com LLMs sem depender de linha de comando.

---

## Funcionalidades Principais

- **Chat com modelos Ollama:** Interface de conversação com histórico.
- **Seleção e gerenciamento de modelos:** Baixe, exclua e atualize modelos facilmente.
- **Detecção automática dos modelos disponíveis.**
- **Configuração do host e teste de conexão:** Suporte a servidores remotos ou locais.
- **Barra de progresso e logs detalhados de download/exclusão.**
- **Formatação de respostas em Markdown (negrito, cabeçalhos).**
- **Menu de ajuda, atalhos e solução de problemas.**
- **Tema escuro, responsivo e compatível com diferentes sistemas operacionais.**

---

## Captura de tela

*(Adicione aqui uma imagem da interface após rodar o programa!)*

---

## Instalação

1. **Clone o repositório ou baixe o arquivo principal.**

2. **Instale as dependências** (recomenda-se uso de ambiente virtual):

```bash
pip install PySide6
```

3. **Instale e rode o Ollama no seu sistema**  
Veja instruções: [Documentação do Ollama](https://ollama.com/docs)

4. **Execute o programa:**

```bash
python seu_arquivo.py
```

---

## Como Usar

- **Certifique-se de que o Ollama está rodando** (`ollama serve`).
- **Abra o Ollama GUI**.
- **Selecione o modelo desejado** ou baixe modelos novos via menu "Gerenciar Modelos".
- **Digite sua mensagem** na caixa inferior e pressione `Enter` (ou clique em "Enviar").
- **Acompanhe a resposta, histórico e logs na interface**.
- **Exporte/copie o histórico se desejar**.
- **Use o menu de ajuda para informações rápidas e solução de problemas**.

---

## Principais Componentes

- `InterfaceOllama`: Janela principal de chat e gerenciamento.
- `JanelaGerenciamento`: Modal para baixar e excluir modelos.
- `EntradaUsuario`: Caixa de texto personalizada com suporte a atalhos.
- **Comunicação por sinais/threads** para não travar a interface durante operações.
- **Formatação Markdown simplificada** para respostas do modelo.

---

## Recursos Suportados

- Modelos Ollama locais e remotos.
- Compatível com Windows, Linux e macOS (incluindo macOS Sonoma, com aviso para travamentos conhecidos).
- Tema escuro por padrão.
- Suporte a atalhos (`Enter` para enviar, `Shift+Enter` para nova linha).

---

## Solução de Problemas

- **Erro de conexão:** Verifique se o Ollama está rodando, host e porta corretos, e firewall.
- **MacOS Sonoma:** Pode apresentar travamento de interface após inicialização. Basta mover o cursor para fora da janela e retornar.
- **Problemas ao baixar/excluir modelos:** Veja os logs detalhados na área específica.

---

## Licença

Este projeto é distribuído sob a licença MIT.

---

## Autor

Wendell Moura
GitHub: [https://github.com/chyok/ollama-gui](https://github.com/chyok/ollama-gui)

## Fork
chyok  
GitHub: [https://github.com/chyok/ollama-gui](https://github.com/chyok/ollama-gui)

---

*Contribuições e sugestões são bem-vindas!*

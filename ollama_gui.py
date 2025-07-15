import sys
import json
import time
import pprint
import platform
import webbrowser
import queue
import urllib.error
import urllib.parse
import urllib.request
import socket
import traceback
import html
import re
from threading import Thread
from typing import Optional, List, Generator, Tuple, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTextEdit, QLineEdit, QComboBox, QPushButton, QProgressBar, QLabel,
    QMessageBox, QListWidget, QScrollArea, QMenu, QDialog, QListWidgetItem,
    QFrame, QSizePolicy, QMenuBar, QScrollBar, QStyleFactory
)
from PySide6.QtGui import (QTextCursor, QFont, QAction, QKeyEvent, QTextCharFormat, 
                          QColor, QPalette, QFontMetrics, QIcon, QTextDocument)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QObject, QSize, QEvent, QUrl

__version__ = "1.2.2"

# Função simplificada para formatação Markdown
def formatar_markdown(texto: str) -> str:
    """Converte apenas **negrito** e ### cabeçalhos"""
    # Negrito: **texto**
    texto = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', texto)
    
    # Cabeçalhos: ### Texto
    texto = re.sub(r'^###\s+(.*)$', r'<h3>\1</h3>', texto, flags=re.MULTILINE)
    
    return texto

# Classe personalizada para entrada de texto
class EntradaUsuario(QTextEdit):
    enterPressed = Signal()
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            self.enterPressed.emit()
            event.accept()
        elif event.key() == Qt.Key_Return and event.modifiers() & Qt.ShiftModifier:
            self.insertPlainText("\n")
        else:
            super().keyPressEvent(event)

# Tempos de timeout configuráveis
TIMEOUT_CONEXAO = 15
TIMEOUT_CONVERSA = 300
TIMEOUT_DOWNLOAD = 0

class ModeloNaoEncontradoError(Exception):
    pass

class ErroConexaoError(Exception):
    pass

class ErroServidorError(Exception):
    pass

class WorkerSignals(QObject):
    update_chat = Signal(str, str)  # (texto, tipo)
    update_log = Signal(str, bool)
    show_progress = Signal()
    hide_progress = Signal()
    enable_button = Signal(str, bool)
    update_model_combo = Signal(list)
    show_error = Signal(str)
    update_model_list = Signal(list)

class InterfaceOllama(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_url = "http://127.0.0.1:11434"
        self.historico_chat = []
        self.fonte_padrao = QFont().family()
        self.fila_atualizacoes = queue.Queue()
        self.signals = WorkerSignals()
        self.caixa_log = None
        self.lista_modelos = None
        self.ultima_resposta = ""  # Para acumular a resposta do modelo
        
        self.setWindowTitle("Ollama GUI")
        self.resize(800, 600)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout_principal = QVBoxLayout(central_widget)
        self.layout_principal.setContentsMargins(20, 20, 20, 20)
        
        self.iniciar_layout()
        self.conectar_sinais()
        
        # Verificar sistema
        self.verificar_sistema()
        self.atualizar_modelos()

    def iniciar_layout(self):
        # Frame cabeçalho
        frame_cabecalho = QWidget()
        layout_cabecalho = QHBoxLayout(frame_cabecalho)
        layout_cabecalho.setContentsMargins(0, 0, 0, 0)
        
        self.seletor_modelo = QComboBox()
        self.seletor_modelo.setMinimumWidth(200)
        layout_cabecalho.addWidget(self.seletor_modelo)
        
        self.botao_config = QPushButton("⚙️")
        self.botao_config.setFixedWidth(30)
        layout_cabecalho.addWidget(self.botao_config)
        self.botao_config.clicked.connect(self.mostrar_janela_gerenciamento)
        
        self.botao_atualizar = QPushButton("Atualizar")
        layout_cabecalho.addWidget(self.botao_atualizar)
        self.botao_atualizar.clicked.connect(self.atualizar_modelos)
        
        layout_cabecalho.addWidget(QLabel("Host:"))
        
        self.entrada_host = QLineEdit(self.api_url)
        self.entrada_host.setMinimumWidth(150)
        layout_cabecalho.addWidget(self.entrada_host)
        
        self.botao_testar = QPushButton("Testar Conexão")
        layout_cabecalho.addWidget(self.botao_testar)
        self.botao_testar.clicked.connect(self.testar_conexao)
        
        self.botao_reiniciar = QPushButton("Reiniciar Conexão")
        layout_cabecalho.addWidget(self.botao_reiniciar)
        self.botao_reiniciar.clicked.connect(self.reiniciar_conexao)
        
        layout_cabecalho.addStretch(1)
        self.layout_principal.addWidget(frame_cabecalho)
        
        # Área de chat
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        self.caixa_chat = QTextEdit()
        self.caixa_chat.setReadOnly(True)
        self.caixa_chat.setFont(QFont(self.fonte_padrao, 12))
        
        # Configurar estilos CSS
        self.caixa_chat.document().setDefaultStyleSheet("""
            h3 {
                color: #ffcc80;
                font-weight: bold;
                margin-top: 10px;
                margin-bottom: 5px;
            }
            b {
                color: #ffffff;
                font-weight: bold;
            }
        """)
        
        scroll_area.setWidget(self.caixa_chat)
        self.layout_principal.addWidget(scroll_area, 1)
        
        # Barra de progresso
        frame_progresso = QWidget()
        layout_progresso = QHBoxLayout(frame_progresso)
        layout_progresso.setContentsMargins(0, 0, 0, 0)
        
        self.progresso = QProgressBar()
        self.progresso.setRange(0, 0)  # Indeterminado
        self.progresso.setVisible(False)
        layout_progresso.addWidget(self.progresso)
        
        self.botao_parar = QPushButton("Parar")
        self.botao_parar.setVisible(False)
        layout_progresso.addWidget(self.botao_parar)
        self.botao_parar.clicked.connect(lambda: self.botao_parar.setEnabled(False))
        
        self.layout_principal.addWidget(frame_progresso)
        
        # Entrada de texto
        frame_entrada = QWidget()
        layout_entrada = QVBoxLayout(frame_entrada)
        layout_entrada.setContentsMargins(0, 0, 0, 0)
        
        # Usando nossa classe personalizada
        self.entrada_usuario = EntradaUsuario()
        self.entrada_usuario.setFont(QFont(self.fonte_padrao, 12))
        self.entrada_usuario.setMinimumHeight(100)
        self.entrada_usuario.enterPressed.connect(self.ao_clicar_enviar)
        layout_entrada.addWidget(self.entrada_usuario)
        
        frame_botoes = QWidget()
        layout_botoes = QHBoxLayout(frame_botoes)
        layout_botoes.setContentsMargins(0, 10, 0, 0)
        
        self.botao_enviar = QPushButton("Enviar")
        layout_botoes.addWidget(self.botao_enviar)
        self.botao_enviar.clicked.connect(self.ao_clicar_enviar)
        self.botao_enviar.setEnabled(False)
        
        layout_entrada.addWidget(frame_botoes)
        self.layout_principal.addWidget(frame_entrada)
        
        # Menu
        self.criar_menu()

    def criar_menu(self):
        menu_bar = self.menuBar()
        
        # Menu Arquivo
        menu_arquivo = menu_bar.addMenu("Arquivo")
        acao_gerenciar = QAction("Gerenciar Modelos", self)
        acao_gerenciar.triggered.connect(self.mostrar_janela_gerenciamento)
        menu_arquivo.addAction(acao_gerenciar)
        
        acao_sair = QAction("Sair", self)
        acao_sair.triggered.connect(self.close)
        menu_arquivo.addAction(acao_sair)
        
        # Menu Editar
        menu_editar = menu_bar.addMenu("Editar")
        acao_copiar_tudo = QAction("Copiar Tudo", self)
        acao_copiar_tudo.triggered.connect(self.copiar_tudo)
        menu_editar.addAction(acao_copiar_tudo)
        
        acao_limpar_chat = QAction("Limpar Chat", self)
        acao_limpar_chat.triggered.connect(self.limpar_chat)
        menu_editar.addAction(acao_limpar_chat)
        
        # Menu Ajuda
        menu_ajuda = menu_bar.addMenu("Ajuda")
        acao_codigo = QAction("Código Fonte", self)
        acao_codigo.triggered.connect(self.abrir_pagina_inicial)
        menu_ajuda.addAction(acao_codigo)
        
        acao_ajuda = QAction("Ajuda", self)
        acao_ajuda.triggered.connect(self.mostrar_ajuda)
        menu_ajuda.addAction(acao_ajuda)
        
        acao_solucionar = QAction("Solucionar Problemas", self)
        acao_solucionar.triggered.connect(self.mostrar_ajuda_conexao)
        menu_ajuda.addAction(acao_solucionar)

    def conectar_sinais(self):
        self.signals.update_chat.connect(self.adicionar_texto_chat)
        self.signals.update_log.connect(self.adicionar_log)
        self.signals.show_progress.connect(self.mostrar_barra_progresso)
        self.signals.hide_progress.connect(self.ocultar_barra_progresso)
        self.signals.enable_button.connect(self.habilitar_botao)
        self.signals.update_model_combo.connect(self.atualizar_seletor_modelos_ui)
        self.signals.show_error.connect(self.mostrar_erro)
        self.signals.update_model_list.connect(self.atualizar_lista_modelos_ui)

    # Métodos principais (comunicação entre threads via signals)
    @Slot(str, str)
    def adicionar_texto_chat(self, texto: str, tipo: str):
        try:
            self.caixa_chat.setReadOnly(False)
            cursor = self.caixa_chat.textCursor()
            cursor.movePosition(QTextCursor.End)
            
            if tipo == "usuario":
                # Texto do usuário
                self.caixa_chat.setTextColor(QColor("#e0e0e0"))
                self.caixa_chat.insertPlainText("Você: " + texto + "\n\n")
            elif tipo == "modelo":
                # Texto do modelo - apenas adiciona texto puro
                self.caixa_chat.setTextColor(QColor("#e0e0e0"))
                self.caixa_chat.insertPlainText(texto)
            elif tipo == "nome_modelo":
                # Nome do modelo
                self.caixa_chat.setTextColor(QColor("#ffcc80"))
                self.caixa_chat.insertPlainText("Modelo: " + texto + "\n")
            elif tipo == "erro":
                # Mensagens de erro
                self.caixa_chat.setTextColor(QColor("#ff6666"))
                self.caixa_chat.insertPlainText(texto + "\n\n")
            elif tipo == "texto":
                self.caixa_chat.insertPlainText("\n")
            
            cursor.movePosition(QTextCursor.End)
            self.caixa_chat.setTextCursor(cursor)
            self.caixa_chat.ensureCursorVisible()
        except Exception as e:
            self.adicionar_log(f"Erro ao adicionar texto: {str(e)}")
        finally:
            self.caixa_chat.setReadOnly(True)

    @Slot(str, bool)
    def adicionar_log(self, mensagem: Optional[str] = None, limpar: bool = False):
        if self.caixa_log is None:
            return
            
        try:
            self.caixa_log.setReadOnly(False)
            if limpar:
                self.caixa_log.clear()
            elif mensagem:
                self.caixa_log.append(mensagem)
            
            cursor = self.caixa_log.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.caixa_log.setTextCursor(cursor)
        except Exception as e:
            print(f"Erro fatal no log: {str(e)}")
        finally:
            self.caixa_log.setReadOnly(True)

    @Slot()
    def mostrar_barra_progresso(self):
        self.progresso.setVisible(True)
        self.botao_parar.setVisible(True)
        self.botao_parar.setEnabled(True)

    @Slot()
    def ocultar_barra_progresso(self):
        self.progresso.setVisible(False)
        self.botao_parar.setVisible(False)

    @Slot(str, bool)
    def habilitar_botao(self, nome: str, estado: bool):
        if nome == "enviar":
            self.botao_enviar.setEnabled(estado)
        elif nome == "atualizar":
            self.botao_atualizar.setEnabled(estado)
        elif nome == "parar":
            self.botao_parar.setEnabled(estado)

    @Slot(list)
    def atualizar_seletor_modelos_ui(self, modelos):
        self.seletor_modelo.clear()
        self.seletor_modelo.addItems(modelos)
        if modelos:
            self.seletor_modelo.setCurrentIndex(0)
            self.signals.enable_button.emit("enviar", True)
        else:
            self.mostrar_erro("Baixe um modelo primeiro!")

    @Slot(str)
    def mostrar_erro(self, texto):
        self.seletor_modelo.clear()
        self.seletor_modelo.addItem(texto)
        self.seletor_modelo.setStyleSheet("color: #ff6666;")
        self.signals.enable_button.emit("enviar", False)

    @Slot(list)
    def atualizar_lista_modelos_ui(self, modelos):
        if self.lista_modelos is None:
            return
            
        try:
            self.lista_modelos.clear()
            self.lista_modelos.addItems(modelos)
        except Exception as e:
            self.adicionar_log(f"Erro na lista: {str(e)}")

    # Métodos de funcionalidade
    def atualizar_modelos(self):
        self.atualizar_host()
        self.seletor_modelo.setStyleSheet("")
        self.signals.enable_button.emit("enviar", False)
        self.signals.enable_button.emit("atualizar", False)
        Thread(target=self.atualizar_seletor_modelos, daemon=True).start()

    def atualizar_host(self):
        url = self.entrada_host.text().strip()
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        self.api_url = url

    def atualizar_seletor_modelos(self):
        try:
            modelos = self.buscar_modelos()
            self.signals.update_model_combo.emit(modelos)
        except ModeloNaoEncontradoError:
            self.signals.show_error.emit("Nenhum modelo encontrado!")
        except ErroConexaoError as e:
            self.signals.show_error.emit(f"Erro de conexão: {str(e)}")
        except ErroServidorError as e:
            self.signals.show_error.emit(f"Erro no servidor: {str(e)}")
        except Exception as e:
            self.signals.show_error.emit(f"Erro inesperado: {type(e).__name__}")
        finally:
            self.signals.enable_button.emit("atualizar", True)

    def ao_clicar_enviar(self):
        try:
            mensagem = self.entrada_usuario.toPlainText().strip()
            if not mensagem:
                return
                
            self.signals.update_chat.emit(mensagem, "usuario")
            self.entrada_usuario.clear()
            self.historico_chat.append({"role": "user", "content": mensagem})

            Thread(target=self.gerar_resposta_ia, daemon=True).start()
        except Exception as e:
            self.adicionar_log(f"Erro ao enviar: {str(e)}")

    def gerar_resposta_ia(self):
        self.signals.show_progress.emit()
        self.signals.enable_button.emit("enviar", False)
        self.signals.enable_button.emit("atualizar", False)
        self.signals.enable_button.emit("parar", True)

        try:
            modelo = self.seletor_modelo.currentText()
            self.signals.update_chat.emit(modelo, "nome_modelo")
            
            mensagem_ia = ""
            for parte in self.buscar_resposta_chat_stream():
                if not self.botao_parar.isEnabled():
                    break
                    
                # Adicionar parte normalmente
                self.signals.update_chat.emit(parte, "modelo")
                mensagem_ia += parte
                
            self.historico_chat.append({"role": "assistant", "content": mensagem_ia})
            self.signals.update_chat.emit("\n", "texto")
            
            # Aplicar formatação apenas na resposta completa
            cursor = self.caixa_chat.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.select(QTextCursor.BlockUnderCursor)
            texto_formatado = formatar_markdown(mensagem_ia)
            cursor.insertHtml(texto_formatado)
            
        except socket.timeout:
            erro = "Tempo esgotado: A resposta demorou muito"
            self.signals.update_chat.emit(erro, "erro")
            self.signals.update_chat.emit("\n", "texto")
        except urllib.error.URLError as e:
            erro = f"Erro de conexão: {e.reason}"
            self.signals.update_chat.emit(erro, "erro")
            self.signals.update_chat.emit("\n", "texto")
        except urllib.error.HTTPError as e:
            if e.code == 500:
                erro = "Erro interno no servidor Ollama (500)\n"
                erro += "Possíveis causas:\n"
                erro += "• O modelo pode estar corrompido\n"
                erro += "• Falta de memória no servidor\n"
                erro += "• Bug no servidor Ollama\n\n"
                erro += "Soluções sugeridas:\n"
                erro += "1. Reinicie o servidor Ollama\n"
                erro += "2. Tente outro modelo\n"
                erro += "3. Verifique os logs do servidor"
            else:
                erro = f"Erro HTTP {e.code}: {e.reason}"
            self.signals.update_chat.emit(erro, "erro")
            self.signals.update_chat.emit("\n", "texto")
        except json.JSONDecodeError:
            erro = "Resposta inválida do servidor"
            self.signals.update_chat.emit(erro, "erro")
            self.signals.update_chat.emit("\n", "texto")
        except ModeloNaoEncontradoError:
            erro = "Modelo não encontrado"
            self.signals.update_chat.emit(erro, "erro")
            self.signals.update_chat.emit("\n", "texto")
        except ErroConexaoError as e:
            erro = f"Falha na conexão: {str(e)}"
            self.signals.update_chat.emit(erro, "erro")
            self.signals.update_chat.emit("\n", "texto")
        except ErroServidorError as e:
            erro = f"Erro no servidor: {str(e)}"
            self.signals.update_chat.emit(erro, "erro")
            self.signals.update_chat.emit("\n", "texto")
        except Exception as e:
            erro = f"Erro inesperado: {type(e).__name__}"
            self.signals.update_chat.emit(erro, "erro")
            self.signals.update_chat.emit("\n", "texto")
        finally:
            self.signals.hide_progress.emit()
            self.signals.enable_button.emit("enviar", True)
            self.signals.enable_button.emit("atualizar", True)
            self.signals.enable_button.emit("parar", True)

    def buscar_modelos(self) -> List[str]:
        url = urllib.parse.urljoin(self.api_url, "/api/tags")
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_CONEXAO) as resposta:
                if resposta.status != 200:
                    raise ErroServidorError(f"Status HTTP inesperado: {resposta.status}")
                
                dados = json.load(resposta)
                if "models" not in dados:
                    raise ModeloNaoEncontradoError("Nenhum modelo disponível")
                    
                modelos = [modelo["name"] for modelo in dados["models"]]
                return modelos
        except urllib.error.HTTPError as e:
            if e.code == 500:
                raise ErroServidorError("Erro interno no servidor Ollama (500)") from e
            else:
                raise ErroConexaoError(f"Erro HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise ErroConexaoError(f"Falha ao conectar com o servidor: {e.reason}") from e
        except socket.timeout:
            raise ErroConexaoError("Tempo de conexão esgotado") from None
        except json.JSONDecodeError:
            raise ErroServidorError("Resposta inválida do servidor") from None
        except Exception as e:
            raise ErroConexaoError(f"Erro inesperado: {str(e)}") from e

    def buscar_resposta_chat_stream(self) -> Generator:
        url = urllib.parse.urljoin(self.api_url, "/api/chat")
        dados = json.dumps(
            {
                "model": self.seletor_modelo.currentText(),
                "messages": self.historico_chat,
                "stream": True,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        req = urllib.request.Request(url, data=dados, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_CONVERSA) as resp:
                if resp.status != 200:
                    raise ErroServidorError(f"Status HTTP inesperado: {resp.status}")
                
                for linha in resp:
                    if not self.botao_parar.isEnabled():  # parar
                        break
                    dados = json.loads(linha.decode("utf-8"))
                    if "message" in dados:
                        time.sleep(0.01)
                        yield dados["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 500:
                raise ErroServidorError("Erro interno no servidor durante a conversa") from e
            else:
                raise ErroConexaoError(f"Erro HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise ErroConexaoError(f"Erro durante a conversa: {e.reason}") from e
        except socket.timeout:
            raise ErroConexaoError("Tempo de resposta esgotado") from None
        except json.JSONDecodeError:
            raise ErroServidorError("Resposta inválida do servidor") from None
        except Exception as e:
            raise ErroConexaoError(f"Erro inesperado: {str(e)}") from e

    # Outros métodos
    def copiar_texto(self, texto: str):
        clipboard = QApplication.clipboard()
        clipboard.setText(texto)

    def copiar_tudo(self):
        self.copiar_texto(pprint.pformat(self.historico_chat))

    def abrir_pagina_inicial(self):
        webbrowser.open("https://github.com/wendellmoura/ollama-gui")

    def mostrar_ajuda(self):
        info = ("Projeto: Ollama GUI\n"
                f"Versão: {__version__}\n"
                "Autor: Wendell Moura\n"
                "Github: https://github.com/wendellmoura/ollama-gui\n\n"
                "<Enter>: enviar\n"
                "<Shift+Enter>: nova linha")
        QMessageBox.information(self, "Sobre", info)

    def verificar_sistema(self):
        # Implementação simplificada para PySide
        if platform.system().lower() == "darwin":
            versao = platform.mac_ver()[0]
            if versao and 14 <= float(versao) < 15:
                QMessageBox.warning(
                    self, 
                    "Aviso",
                    "Aviso: Problema de Responsividade Detectado\n\n"
                    "Você pode experimentar elementos de interface congelados quando "
                    "o cursor está dentro da janela durante a inicialização. "
                    "Este é um problema conhecido com versões do macOS Sonoma.\n\n"
                    "Solução temporária: Mova o cursor para fora da "
                    "janela e retorne se os elementos travarem."
                )

    def limpar_chat(self):
        try:
            self.caixa_chat.clear()
            self.historico_chat.clear()
            self.ultima_resposta = ""
        except Exception as e:
            self.adicionar_log(f"Erro ao limpar chat: {str(e)}")

    def testar_conexao(self):
        self.atualizar_host()
        if self.verificar_conexao():
            QMessageBox.information(
                self,
                "Conexão",
                f"Conexão com o servidor Ollama bem-sucedida!\nHost: {self.api_url}"
            )
        else:
            QMessageBox.critical(
                self,
                "Erro de Conexão",
                "Não foi possível conectar ao servidor Ollama.\n\n"
                f"Host: {self.api_url}\n\n"
                "Verifique:\n"
                "1. Se o servidor Ollama está rodando\n"
                "2. Se o host e porta estão corretos\n"
                "3. Sua conexão de rede"
            )

    def verificar_conexao(self) -> bool:
        try:
            with urllib.request.urlopen(
                urllib.parse.urljoin(self.api_url, "/api/tags"), 
                timeout=5
            ) as resposta:
                return resposta.status == 200
        except:
            return False

    def reiniciar_conexao(self):
        self.atualizar_host()
        self.atualizar_modelos()
        self.adicionar_log("Conexão reiniciada com o servidor Ollama")

    def mostrar_ajuda_conexao(self):
        ajuda = (
            "Solução de Problemas de Conexão\n\n"
            "1. Verifique se o servidor Ollama está rodando:\n"
            "   • Execute 'ollama serve' no terminal\n\n"
            "2. Confira o host e porta:\n"
            "   • Padrão: http://127.0.0.1:11434\n\n"
            "3. Teste a conexão usando o botão 'Testar Conexão'\n\n"
            "4. Se estiver usando Docker, verifique as portas expostas\n\n"
            "5. Reinicie o servidor Ollama e a aplicação"
        )
        QMessageBox.information(self, "Ajuda de Conexão", ajuda)

    def mostrar_janela_gerenciamento(self):
        if hasattr(self, 'janela_gerenciamento') and self.janela_gerenciamento.isVisible():
            self.janela_gerenciamento.activateWindow()
            return

        self.janela_gerenciamento = JanelaGerenciamento(self)
        self.janela_gerenciamento.show()

    # Métodos para gerenciamento de modelos
    def baixar_modelo(self, nome_modelo: str, insecure: bool = False):
        self.signals.update_log.emit("", True)  # Limpar log
        if not nome_modelo:
            return

        try:
            url = urllib.parse.urljoin(self.api_url, "/api/pull")
            dados = json.dumps({"name": nome_modelo, "insecure": insecure, "stream": True}).encode("utf-8")
            req = urllib.request.Request(url, data=dados, method="POST")
            
            with urllib.request.urlopen(req, timeout=TIMEOUT_DOWNLOAD) as resposta:
                for linha in resposta:
                    dados = json.loads(linha.decode("utf-8"))
                    log = dados.get("error") or dados.get("status") or "Sem resposta"
                    if "status" in dados:
                        total = dados.get("total")
                        completado = dados.get("completed", 0)
                        if total:
                            log += f" [{completado}/{total}]"
                    self.signals.update_log.emit(log, False)
        except Exception as e:
            self.signals.update_log.emit(f"Falha no download: {str(e)}", False)
        finally:
            self.signals.update_model_list.emit(self.buscar_modelos())
            self.signals.update_model_combo.emit(self.buscar_modelos())
            self.signals.enable_button.emit("baixar", True)

    def excluir_modelo(self, nome_modelo: str):
        self.signals.update_log.emit("", True)  # Limpar log
        if not nome_modelo:
            return

        try:
            url = urllib.parse.urljoin(self.api_url, "/api/delete")
            dados = json.dumps({"name": nome_modelo}).encode("utf-8")
            req = urllib.request.Request(url, data=dados, method="DELETE")
            
            with urllib.request.urlopen(req, timeout=TIMEOUT_CONEXAO) as resposta:
                if resposta.status == 200:
                    self.signals.update_log.emit("Modelo excluído com sucesso.", False)
                elif resposta.status == 404:
                    self.signals.update_log.emit("Modelo não encontrado.", False)
                else:
                    self.signals.update_log.emit(f"Resposta inesperada do servidor: {resposta.status}", False)
        except Exception as e:
            self.signals.update_log.emit(f"Falha ao excluir modelo: {str(e)}", False)
        finally:
            self.signals.update_model_list.emit(self.buscar_modelos())
            self.signals.update_model_combo.emit(self.buscar_modelos())


class JanelaGerenciamento(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Gerenciamento de Modelos")
        self.resize(400, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Entrada para nome do modelo
        frame_entrada = QWidget()
        layout_entrada = QHBoxLayout(frame_entrada)
        layout_entrada.setContentsMargins(0, 0, 0, 0)
        
        self.entrada_nome_modelo = QLineEdit()
        layout_entrada.addWidget(self.entrada_nome_modelo)
        
        self.botao_baixar = QPushButton("Baixar")
        layout_entrada.addWidget(self.botao_baixar)
        self.botao_baixar.clicked.connect(self.baixar_modelo)
        
        layout.addWidget(frame_entrada)
        
        # Link para biblioteca
        link = QLabel(
            '<a href="https://ollama.com/library" style="color: #80cbc4; text-decoration: underline;">'
            'encontrar modelos: https://ollama.com/library</a>'
        )
        link.setOpenExternalLinks(True)
        layout.addWidget(link)
        
        # Lista de modelos
        frame_lista = QWidget()
        layout_lista = QHBoxLayout(frame_lista)
        layout_lista.setContentsMargins(0, 0, 0, 0)
        
        self.lista_modelos = QListWidget()
        layout_lista.addWidget(self.lista_modelos, 1)
        
        self.botao_excluir = QPushButton("Excluir")
        self.botao_excluir.setFixedWidth(80)
        layout_lista.addWidget(self.botao_excluir)
        self.botao_excluir.clicked.connect(self.excluir_modelo)
        
        layout.addWidget(frame_lista, 1)
        
        # Área de log
        self.caixa_log = QTextEdit()
        self.caixa_log.setReadOnly(True)
        layout.addWidget(self.caixa_log)
        
        # Conectar sinais do pai
        self.parent.signals.update_log.connect(self.adicionar_log)
        self.parent.signals.update_model_list.connect(self.atualizar_lista_modelos_ui)
        
        # Carregar modelos iniciais
        Thread(target=self.carregar_modelos_iniciais, daemon=True).start()

    def carregar_modelos_iniciais(self):
        try:
            modelos = self.parent.buscar_modelos()
            self.parent.signals.update_model_list.emit(modelos)
        except Exception as e:
            self.parent.adicionar_log(f"Erro ao carregar modelos: {str(e)}")

    @Slot(str, bool)
    def adicionar_log(self, mensagem: Optional[str] = None, limpar: bool = False):
        if limpar:
            self.caixa_log.clear()
        if mensagem:
            self.caixa_log.append(mensagem)

    @Slot(list)
    def atualizar_lista_modelos_ui(self, modelos):
        self.lista_modelos.clear()
        self.lista_modelos.addItems(modelos)

    def baixar_modelo(self):
        modelo = self.entrada_nome_modelo.text().strip()
        if modelo.startswith("ollama run "):
            modelo = modelo[11:]
            
        self.parent.signals.update_log.emit("", True)  # Limpar log
        self.botao_baixar.setEnabled(False)
        Thread(
            target=self.parent.baixar_modelo,
            daemon=True,
            args=(modelo,)
        ).start()

    def excluir_modelo(self):
        item = self.lista_modelos.currentItem()
        if not item:
            return
            
        modelo = item.text()
        Thread(
            target=self.parent.excluir_modelo,
            daemon=True,
            args=(modelo,)
        ).start()


def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    # Configurar paleta de cores - tema escuro
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(18, 18, 18))
    palette.setColor(QPalette.AlternateBase, QColor(30, 30, 30))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(50, 50, 50))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(142, 45, 197).lighter())
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    window = InterfaceOllama()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

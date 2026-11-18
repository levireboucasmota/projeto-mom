"""Cliente.

Solicita as palavras-chave e o arquivo, esvazia a fila de linhas e instancia
duas execuções do Leitor (uma para as linhas pares e outra para as ímpares).

Uso:
    python cliente.py
"""
import os
import re
import sys

import pika
from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from config import HOST, FILA_LINHAS

TIPOS = {"pares": "Leitor de linhas pares", "impares": "Leitor de linhas ímpares"}

ESTILO = """
QMainWindow, QWidget { background: #f4f6fb; font-family: 'Segoe UI'; font-size: 13px; color: #1f2937; }
QLabel { background: transparent; }
#titulo { font-size: 22px; font-weight: 700; }
#subtitulo { color: #6b7280; }
#rotulo { font-weight: 600; }
#card { background: white; border-radius: 10px; border: 1px solid #e5e7eb; }
#cardTitulo { color: #6b7280; font-size: 12px; }
#cardStatus { font-size: 15px; font-weight: 700; }
QLineEdit { background: white; border: 1px solid #d1d5db; border-radius: 6px; padding: 8px; }
QLineEdit:focus { border: 1px solid #2563eb; }
QSpinBox { background: white; border: 1px solid #d1d5db; border-radius: 6px; padding: 6px; min-width: 60px; }
QPlainTextEdit { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 6px;
                 font-family: Consolas, monospace; font-size: 12px; }
QPushButton { background: #2563eb; color: white; border: none; border-radius: 6px;
              padding: 9px 18px; font-weight: 600; }
QPushButton:hover { background: #1d4ed8; }
QPushButton:disabled { background: #9ca3af; }
#secundario { background: white; color: #1f2937; border: 1px solid #d1d5db; }
#secundario:hover { background: #f3f4f6; }
#secundario:disabled { color: #9ca3af; }
QProgressBar { background: #e5e7eb; border: none; border-radius: 4px; max-height: 8px; }
QProgressBar::chunk { background: #2563eb; border-radius: 4px; }
"""


def pasta_base():
    """Pasta onde estão os scripts (ou os .exe, quando empacotado com PyInstaller)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def comando_leitor(tipo, arquivo, palavras):
    """Devolve (programa, argumentos) para executar o leitor."""
    args = ["--tipo", tipo, "--arquivo", arquivo, "--palavras", palavras]
    if getattr(sys, "frozen", False):
        return os.path.join(pasta_base(), "leitor.exe"), args
    return sys.executable, [os.path.join(pasta_base(), "leitor.py")] + args


def comando_consumidor():
    """Devolve (programa, argumentos) para executar um consumidor."""
    if getattr(sys, "frozen", False):
        return os.path.join(pasta_base(), "consumidor.exe"), []
    return sys.executable, [os.path.join(pasta_base(), "consumidor.py")]


def esvaziar_fila():
    """Remove mensagens sobrando de execuções anteriores."""
    conexao = pika.BlockingConnection(pika.ConnectionParameters(HOST))
    canal = conexao.channel()
    canal.queue_declare(queue=FILA_LINHAS, durable=True)
    canal.queue_purge(queue=FILA_LINHAS)
    conexao.close()


class Cliente(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cliente: Contagem de Palavras-Chave")
        self.resize(640, 720)

        self.processos = {}
        self.consumidores = []
        self.parando_consumidores = False
        self.saidas = {}
        self.cancelando = False
        self.lbl_status = {}

        self._montar_interface()

    # ---------- Interface ----------
    def _montar_interface(self):
        central = QWidget()
        self.setCentralWidget(central)
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(24, 20, 24, 20)
        raiz.setSpacing(12)

        titulo = QLabel("Cliente")
        titulo.setObjectName("titulo")
        subtitulo = QLabel("Informe as palavras-chave e o arquivo para iniciar a busca paralela")
        subtitulo.setObjectName("subtitulo")
        raiz.addWidget(titulo)
        raiz.addWidget(subtitulo)

        # Palavras-chave
        rotulo = QLabel("Palavras-chave (separadas por vírgula)")
        rotulo.setObjectName("rotulo")
        self.campo_palavras = QLineEdit()
        self.campo_palavras.setPlaceholderText("ex.: python, fila, broker")
        raiz.addSpacing(6)
        raiz.addWidget(rotulo)
        raiz.addWidget(self.campo_palavras)

        # Arquivo
        rotulo2 = QLabel("Arquivo de texto")
        rotulo2.setObjectName("rotulo")
        linha_arquivo = QHBoxLayout()
        self.campo_arquivo = QLineEdit()
        self.campo_arquivo.setReadOnly(True)
        self.campo_arquivo.setPlaceholderText("Nenhum arquivo selecionado")
        botao_arquivo = QPushButton("Escolher...")
        botao_arquivo.setObjectName("secundario")
        botao_arquivo.clicked.connect(self.escolher_arquivo)
        linha_arquivo.addWidget(self.campo_arquivo)
        linha_arquivo.addWidget(botao_arquivo)
        raiz.addWidget(rotulo2)
        raiz.addLayout(linha_arquivo)

        # Consumidores (workers): cada um é um processo independente
        rotulo3 = QLabel("Consumidores (workers)")
        rotulo3.setObjectName("rotulo")
        linha_cons = QHBoxLayout()
        self.spin_consumidores = QSpinBox()
        self.spin_consumidores.setRange(1, 16)
        self.spin_consumidores.setValue(2)
        self.btn_add_cons = QPushButton("Iniciar consumidores")
        self.btn_add_cons.setObjectName("secundario")
        self.btn_add_cons.clicked.connect(self.iniciar_consumidores)
        self.btn_parar_cons = QPushButton("Parar todos")
        self.btn_parar_cons.setObjectName("secundario")
        self.btn_parar_cons.setEnabled(False)
        self.btn_parar_cons.clicked.connect(self.parar_consumidores)
        self.lbl_consumidores = QLabel("0 ativos")
        self.lbl_consumidores.setStyleSheet("color: #6b7280; font-weight: 600;")
        linha_cons.addWidget(self.spin_consumidores)
        linha_cons.addWidget(self.btn_add_cons)
        linha_cons.addWidget(self.btn_parar_cons)
        linha_cons.addWidget(self.lbl_consumidores)
        linha_cons.addStretch()
        raiz.addWidget(rotulo3)
        raiz.addLayout(linha_cons)

        # Botões de ação
        acoes = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar busca")
        self.btn_iniciar.clicked.connect(self.iniciar)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("secundario")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self.cancelar)
        acoes.addWidget(self.btn_iniciar)
        acoes.addWidget(self.btn_cancelar)
        acoes.addStretch()
        raiz.addSpacing(6)
        raiz.addLayout(acoes)

        # Barra de atividade
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setRange(0, 1)
        self.barra.setValue(0)
        raiz.addWidget(self.barra)

        # Cartões dos leitores
        cartoes = QHBoxLayout()
        cartoes.setSpacing(12)
        for tipo, nome in TIPOS.items():
            quadro = QFrame()
            quadro.setObjectName("card")
            layout = QVBoxLayout(quadro)
            titulo_cartao = QLabel(nome)
            titulo_cartao.setObjectName("cardTitulo")
            status = QLabel("Aguardando")
            status.setObjectName("cardStatus")
            status.setStyleSheet("color: #6b7280;")
            layout.addWidget(titulo_cartao)
            layout.addWidget(status)
            self.lbl_status[tipo] = status
            cartoes.addWidget(quadro)
        raiz.addLayout(cartoes)

        # Log
        rotulo_log = QLabel("Registro")
        rotulo_log.setObjectName("rotulo")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        raiz.addWidget(rotulo_log)
        raiz.addWidget(self.log, stretch=1)

        self.setStyleSheet(ESTILO)

    def _definir_status(self, tipo, texto, cor):
        self.lbl_status[tipo].setText(texto)
        self.lbl_status[tipo].setStyleSheet(f"color: {cor};")

    def _registrar(self, texto):
        self.log.appendPlainText(texto)

    # ---------- Ações ----------
    def escolher_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Escolher arquivo de texto", "",
            "Arquivos de texto (*.txt);;Todos os arquivos (*)")
        if caminho:
            self.campo_arquivo.setText(caminho)

    def _ler_palavras(self):
        """Converte o campo de texto em uma lista de palavras únicas, em minúsculas."""
        palavras = []
        for p in self.campo_palavras.text().split(","):
            p = p.strip().lower()
            if p and p not in palavras:
                palavras.append(p)
        return palavras

    def iniciar(self):
        palavras = self._ler_palavras()
        arquivo = self.campo_arquivo.text()

        if not palavras:
            QMessageBox.warning(self, "Atenção", "Informe ao menos uma palavra-chave.")
            return
        invalidas = [p for p in palavras if re.search(r"\W", p)]
        if invalidas:
            QMessageBox.warning(
                self, "Atenção",
                "Use apenas palavras simples (sem espaços, hífen ou pontuação):\n" + ", ".join(invalidas))
            return
        if not arquivo or not os.path.isfile(arquivo):
            QMessageBox.warning(self, "Atenção", "Escolha um arquivo de texto válido.")
            return

        try:
            esvaziar_fila()
        except pika.exceptions.AMQPError:
            QMessageBox.critical(
                self, "Broker indisponível",
                "Não foi possível conectar ao RabbitMQ. Verifique se ele está em execução.")
            return

        self.log.clear()
        self.cancelando = False
        self.saidas = {}
        self._registrar(f"Palavras-chave: {', '.join(palavras)}")
        self._registrar(f"Arquivo: {arquivo}")
        self._registrar("Fila esvaziada. Iniciando os leitores...")

        # Instancia as duas execuções do leitor (pares e ímpares)
        for tipo in TIPOS:
            programa, args = comando_leitor(tipo, arquivo, ",".join(palavras))
            processo = QProcess(self)
            processo.setWorkingDirectory(pasta_base())
            processo.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            processo.readyReadStandardOutput.connect(lambda t=tipo: self._ler_saida(t))
            processo.finished.connect(lambda codigo, estado, t=tipo: self._ao_finalizar(t, codigo))
            processo.errorOccurred.connect(lambda erro, t=tipo: self._ao_falhar(t, erro))
            self.processos[tipo] = processo
            self.saidas[tipo] = ""
            self._definir_status(tipo, "Executando...", "#2563eb")
            processo.start(programa, args)

        self.btn_iniciar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.barra.setRange(0, 0)  # animação de atividade

    def iniciar_consumidores(self):
        """Inicia N processos de consumidor.py, que passam a dividir a fila entre si."""
        quantidade = self.spin_consumidores.value()
        programa, args = comando_consumidor()
        self.parando_consumidores = False
        self._registrar(f"Executando: {programa}")
        for _ in range(quantidade):
            processo = QProcess(self)
            processo.setWorkingDirectory(pasta_base())
            processo.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            processo.readyReadStandardOutput.connect(lambda p=processo: self._ler_saida_consumidor(p))
            processo.finished.connect(lambda codigo, estado, p=processo: self._ao_encerrar_consumidor(codigo))
            processo.errorOccurred.connect(self._ao_falhar_consumidor)
            self.consumidores.append(processo)
            processo.start(programa, args)
        self._registrar(f"{quantidade} consumidor(es) iniciado(s).")
        self._atualizar_consumidores()

    def parar_consumidores(self):
        self.parando_consumidores = True
        for processo in self.consumidores:
            if processo.state() != QProcess.ProcessState.NotRunning:
                processo.kill()
        self._registrar("Consumidores encerrados.")

    def _ler_saida_consumidor(self, processo):
        texto = bytes(processo.readAllStandardOutput()).decode("utf-8", errors="replace")
        for linha in texto.splitlines():
            if linha.strip():
                self._registrar(f"[consumidor] {linha}")

    def _ao_encerrar_consumidor(self, codigo):
        if not self.parando_consumidores:
            self._registrar(f"[consumidor] encerrou inesperadamente (código {codigo}).")
        self._atualizar_consumidores()

    def _ao_falhar_consumidor(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self._registrar("Não foi possível iniciar um consumidor.")
        self._atualizar_consumidores()

    def _atualizar_consumidores(self):
        self.consumidores = [p for p in self.consumidores
                             if p.state() != QProcess.ProcessState.NotRunning]
        ativos = len(self.consumidores)
        self.lbl_consumidores.setText(f"{ativos} ativo(s)")
        self.lbl_consumidores.setStyleSheet(
            f"color: {'#16a34a' if ativos else '#6b7280'}; font-weight: 600;")
        self.btn_parar_cons.setEnabled(ativos > 0)

    def _ler_saida(self, tipo):
        texto = bytes(self.processos[tipo].readAllStandardOutput()).decode("utf-8", errors="replace")
        self.saidas[tipo] += texto
        for linha in texto.splitlines():
            if linha.strip():
                self._registrar(linha)

    def _ao_finalizar(self, tipo, codigo):
        if self.cancelando:
            self._definir_status(tipo, "Cancelado", "#d97706")
        elif codigo == 0:
            achou = re.search(r"(\d+) linhas enviadas", self.saidas.get(tipo, ""))
            detalhe = f"Concluído ({achou.group(1)} linhas)" if achou else "Concluído"
            self._definir_status(tipo, detalhe, "#16a34a")
        else:
            self._definir_status(tipo, "Erro", "#dc2626")
            self._registrar(f"[{tipo}] terminou com erro (código {codigo}).")

        if all(p.state() == QProcess.ProcessState.NotRunning for p in self.processos.values()):
            self._fim_da_execucao()

    def _ao_falhar(self, tipo, erro):
        # Só trata a falha de inicialização (o encerramento normal vai por _ao_finalizar)
        if erro != QProcess.ProcessError.FailedToStart:
            return
        self._definir_status(tipo, "Erro ao iniciar", "#dc2626")
        self._registrar(f"[{tipo}] não foi possível iniciar o processo do leitor.")
        if all(p.state() == QProcess.ProcessState.NotRunning for p in self.processos.values()):
            self._fim_da_execucao()

    def _fim_da_execucao(self):
        self.btn_iniciar.setEnabled(True)
        self.btn_cancelar.setEnabled(False)
        self.barra.setRange(0, 1)
        self.barra.setValue(0)
        if not self.cancelando:
            self._registrar("Leitura concluída. Acompanhe as contagens no Dashboard.")

    def cancelar(self):
        self.cancelando = True
        for processo in self.processos.values():
            if processo.state() != QProcess.ProcessState.NotRunning:
                processo.kill()
        self._registrar("Busca cancelada pelo usuário.")

    def closeEvent(self, evento):
        self.cancelando = True
        self.parando_consumidores = True
        for processo in list(self.processos.values()) + self.consumidores:
            if processo.state() != QProcess.ProcessState.NotRunning:
                processo.kill()
                processo.waitForFinished(1000)
        super().closeEvent(evento)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = Cliente()
    janela.show()
    sys.exit(app.exec())
"""Dashboard (Subscriber).

Assina o tópico de contagens do broker e atualiza a interface em tempo real.
A conexão com o broker roda em uma thread separada (QThread) para não travar
a janela; os dados chegam à interface por sinais do Qt, em lotes de ~100 ms.

Uso:
    python dashboard.py
"""
import json
import sys
import time
from collections import Counter

import pika
from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from config import HOST, EXCHANGE_CONTAGENS

ESTILO = """
QMainWindow, QWidget { background: #f4f6fb; font-family: 'Segoe UI'; font-size: 13px; color: #1f2937; }
QLabel { background: transparent; }
#titulo { font-size: 22px; font-weight: 700; }
#subtitulo { color: #6b7280; }
#card { background: white; border-radius: 10px; border: 1px solid #e5e7eb; }
#cardTitulo { color: #6b7280; font-size: 12px; }
#cardValor { font-size: 26px; font-weight: 700; color: #2563eb; }
#secao { font-size: 14px; font-weight: 600; }
QTableWidget { background: white; border: 1px solid #e5e7eb; border-radius: 8px;
               gridline-color: #f1f5f9; alternate-background-color: #f8fafc; }
QHeaderView::section { background: #eef2ff; border: none; padding: 6px; font-weight: 600; }
QProgressBar { background: #e5e7eb; border: none; border-radius: 5px; max-height: 10px; margin: 0 8px; }
QProgressBar::chunk { background: #2563eb; border-radius: 5px; }
QPushButton { background: #2563eb; color: white; border: none; border-radius: 6px;
              padding: 8px 18px; font-weight: 600; }
QPushButton:hover { background: #1d4ed8; }
"""


def fmt(n):
    """Formata número no padrão brasileiro (1.234)."""
    return f"{n:,}".replace(",", ".")


class Assinante(QThread):
    """Thread que assina o tópico e envia os dados à interface em lotes."""

    lote = Signal(object, int, object)   # contagens, linhas, linhas por consumidor
    status = Signal(str, bool)           # texto, conectado?

    def __init__(self):
        super().__init__()
        self._parar = False

    def parar(self):
        self._parar = True

    def run(self):
        try:
            conexao = pika.BlockingConnection(pika.ConnectionParameters(HOST))
        except pika.exceptions.AMQPError:
            self.status.emit("Broker indisponível", False)
            return

        try:
            canal = conexao.channel()
            canal.exchange_declare(exchange=EXCHANGE_CONTAGENS, exchange_type="fanout")
            # Fila temporária e exclusiva deste assinante, ligada ao tópico
            fila = canal.queue_declare(queue="", exclusive=True).method.queue
            canal.queue_bind(exchange=EXCHANGE_CONTAGENS, queue=fila)
            self.status.emit("Conectado ao broker", True)

            contagens, por_consumidor, linhas = Counter(), Counter(), 0
            ultimo_envio = time.monotonic()

            # inactivity_timeout: devolve (None, None, None) após 100 ms sem mensagens,
            # o que permite descarregar o lote pendente e checar o pedido de parada
            for _, _, corpo in canal.consume(fila, auto_ack=True, inactivity_timeout=0.1):
                if self._parar:
                    break
                if corpo is not None:
                    mensagem = json.loads(corpo)
                    for palavra, qtd in mensagem["contagens"].items():
                        contagens[palavra] += qtd
                    por_consumidor[mensagem["consumidor"]] += 1
                    linhas += 1

                agora = time.monotonic()
                if linhas and (corpo is None or agora - ultimo_envio >= 0.1):
                    self.lote.emit(dict(contagens), linhas, dict(por_consumidor))
                    contagens, por_consumidor, linhas = Counter(), Counter(), 0
                    ultimo_envio = agora
        except pika.exceptions.AMQPError:
            self.status.emit("Conexão com o broker perdida", False)
        finally:
            try:
                conexao.close()
            except Exception:
                pass


class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dashboard: Contagem de Palavras-Chave")
        self.resize(780, 700)

        self.totais = {}
        self.consumidores = {}
        self.linhas = 0
        self.linha_da_palavra = {}
        self._linhas_anterior = 0

        self._montar_interface()

        self.worker = Assinante()
        self.worker.lote.connect(self.ao_receber_lote)
        self.worker.status.connect(self.ao_mudar_status)
        self.worker.start()

        # Calcula a velocidade (linhas/s) uma vez por segundo
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._atualizar_velocidade)
        self.timer.start(1000)

    # ---------- Interface ----------
    def _montar_interface(self):
        central = QWidget()
        self.setCentralWidget(central)
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(24, 20, 24, 20)
        raiz.setSpacing(14)

        # Cabeçalho
        cabecalho = QHBoxLayout()
        textos = QVBoxLayout()
        titulo = QLabel("Dashboard")
        titulo.setObjectName("titulo")
        subtitulo = QLabel("Contagem de palavras-chave em tempo real via MOM")
        subtitulo.setObjectName("subtitulo")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        cabecalho.addLayout(textos)
        cabecalho.addStretch()
        self.lbl_status = QLabel("Conectando...")
        cabecalho.addWidget(self.lbl_status, alignment=Qt.AlignmentFlag.AlignTop)
        raiz.addLayout(cabecalho)

        # Cartões de resumo
        cartoes = QHBoxLayout()
        cartoes.setSpacing(12)
        c1, self.val_linhas = self._cartao("Linhas processadas")
        c2, self.val_total = self._cartao("Ocorrências encontradas")
        c3, self.val_vel = self._cartao("Linhas por segundo")
        for c in (c1, c2, c3):
            cartoes.addWidget(c)
        raiz.addLayout(cartoes)

        # Tabela de palavras
        raiz.addWidget(self._secao("Palavras-chave"))
        self.tab_palavras = self._tabela(["Palavra", "Ocorrências", "Participação"])
        self.tab_palavras.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        raiz.addWidget(self.tab_palavras, stretch=3)

        # Tabela de consumidores
        raiz.addWidget(self._secao("Consumidores ativos (linhas processadas por cada um)"))
        self.tab_consumidores = self._tabela(["Consumidor", "Linhas"])
        self.tab_consumidores.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        raiz.addWidget(self.tab_consumidores, stretch=2)

        # Botão
        botao = QPushButton("Zerar contadores")
        botao.clicked.connect(self.zerar)
        raiz.addWidget(botao, alignment=Qt.AlignmentFlag.AlignRight)

        self.setStyleSheet(ESTILO)

    def _cartao(self, titulo):
        quadro = QFrame()
        quadro.setObjectName("card")
        layout = QVBoxLayout(quadro)
        rotulo = QLabel(titulo)
        rotulo.setObjectName("cardTitulo")
        valor = QLabel("0")
        valor.setObjectName("cardValor")
        layout.addWidget(rotulo)
        layout.addWidget(valor)
        return quadro, valor

    def _secao(self, texto):
        rotulo = QLabel(texto)
        rotulo.setObjectName("secao")
        return rotulo

    def _tabela(self, colunas):
        tabela = QTableWidget(0, len(colunas))
        tabela.setHorizontalHeaderLabels(colunas)
        tabela.verticalHeader().setVisible(False)
        tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabela.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        tabela.setAlternatingRowColors(True)
        tabela.setShowGrid(False)
        return tabela

    # ---------- Dados ----------
    def ao_receber_lote(self, contagens, linhas, por_consumidor):
        self.linhas += linhas
        for palavra, qtd in contagens.items():
            self.totais[palavra] = self.totais.get(palavra, 0) + qtd
        for consumidor, qtd in por_consumidor.items():
            self.consumidores[consumidor] = self.consumidores.get(consumidor, 0) + qtd
        self._atualizar_tela()

    def _atualizar_tela(self):
        soma = sum(self.totais.values())
        self.val_linhas.setText(fmt(self.linhas))
        self.val_total.setText(fmt(soma))

        # Tabela de palavras (cria a linha na primeira vez que a palavra aparece)
        for palavra, qtd in self.totais.items():
            if palavra not in self.linha_da_palavra:
                linha = self.tab_palavras.rowCount()
                self.tab_palavras.insertRow(linha)
                self.tab_palavras.setItem(linha, 0, QTableWidgetItem(palavra))
                item = QTableWidgetItem("0")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tab_palavras.setItem(linha, 1, item)
                barra = QProgressBar()
                barra.setRange(0, 100)
                barra.setTextVisible(False)
                self.tab_palavras.setCellWidget(linha, 2, barra)
                self.linha_da_palavra[palavra] = linha

            linha = self.linha_da_palavra[palavra]
            self.tab_palavras.item(linha, 1).setText(fmt(qtd))
            self.tab_palavras.cellWidget(linha, 2).setValue(round(100 * qtd / soma) if soma else 0)

        # Tabela de consumidores (poucas linhas, reconstruída a cada lote)
        self.tab_consumidores.setRowCount(len(self.consumidores))
        for i, (consumidor, qtd) in enumerate(sorted(self.consumidores.items())):
            self.tab_consumidores.setItem(i, 0, QTableWidgetItem(consumidor))
            item = QTableWidgetItem(fmt(qtd))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tab_consumidores.setItem(i, 1, item)

    def _atualizar_velocidade(self):
        self.val_vel.setText(fmt(self.linhas - self._linhas_anterior))
        self._linhas_anterior = self.linhas

    def ao_mudar_status(self, texto, conectado):
        cor = "#16a34a" if conectado else "#dc2626"
        self.lbl_status.setText(f"● {texto}")
        self.lbl_status.setStyleSheet(f"color: {cor}; font-weight: 600;")

    def zerar(self):
        self.totais.clear()
        self.consumidores.clear()
        self.linha_da_palavra.clear()
        self.linhas = 0
        self._linhas_anterior = 0
        self.tab_palavras.setRowCount(0)
        self.tab_consumidores.setRowCount(0)
        self.val_linhas.setText("0")
        self.val_total.setText("0")
        self.val_vel.setText("0")

    def closeEvent(self, evento):
        self.worker.parar()
        self.worker.wait(2000)
        super().closeEvent(evento)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = Dashboard()
    janela.show()
    sys.exit(app.exec())
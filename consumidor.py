"""Consumidor da fila de linhas.

Retira a próxima linha da fila, conta as palavras-chave e publica o resultado
no tópico (exchange fanout) para o dashboard. Pode-se executar várias instâncias:
o broker distribui as linhas entre elas.

Uso:
    python consumidor.py
"""
import json
import os
import re
from collections import Counter

import pika

from config import HOST, FILA_LINHAS, EXCHANGE_CONTAGENS

ID = f"consumidor-{os.getpid()}"


def contar(linha, palavras):
    """Conta quantas vezes cada palavra-chave aparece na linha (palavra inteira)."""
    tokens = Counter(re.findall(r"\w+", linha.lower()))
    return {palavra: tokens[palavra] for palavra in palavras}


def ao_receber(canal, metodo, propriedades, corpo):
    """Callback chamado pelo broker a cada linha entregue a este consumidor."""
    mensagem = json.loads(corpo)
    contagens = contar(mensagem["linha"], mensagem["palavras"])

    resultado = {
        "consumidor": ID,
        "numero": mensagem["numero"],
        "contagens": contagens,
    }
    # Publica no tópico (fanout ignora a routing_key)
    canal.basic_publish(
        exchange=EXCHANGE_CONTAGENS,
        routing_key="",
        body=json.dumps(resultado),
    )

    # Confirma o processamento: só agora o broker remove a linha da fila
    canal.basic_ack(delivery_tag=metodo.delivery_tag)


def main():
    conexao = pika.BlockingConnection(pika.ConnectionParameters(HOST))
    canal = conexao.channel()

    canal.queue_declare(queue=FILA_LINHAS, durable=True)
    canal.exchange_declare(exchange=EXCHANGE_CONTAGENS, exchange_type="fanout")

    # Cada consumidor recebe no máximo 20 linhas não confirmadas por vez,
    # o que equilibra a carga entre as instâncias
    canal.basic_qos(prefetch_count=20)
    canal.basic_consume(queue=FILA_LINHAS, on_message_callback=ao_receber)

    print(f"[{ID}] aguardando linhas na fila '{FILA_LINHAS}'. Ctrl+C para sair.")
    try:
        canal.start_consuming()
    except KeyboardInterrupt:
        print(f"\n[{ID}] encerrado.")
    finally:
        conexao.close()


if __name__ == "__main__":
    main()
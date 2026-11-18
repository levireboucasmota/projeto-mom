"""Assinante de teste (substituto temporário do dashboard).

Assina o tópico de contagens e acumula os totais no terminal.
Deve ser iniciado ANTES dos consumidores: um tópico fanout não guarda
mensagens para quem ainda não está assinando.

Uso:
    python assinante_teste.py
"""
import json
from collections import Counter

import pika

from config import HOST, EXCHANGE_CONTAGENS

totais = Counter()
recebidas = 0


def ao_receber(canal, metodo, propriedades, corpo):
    global recebidas
    mensagem = json.loads(corpo)
    for palavra, quantidade in mensagem["contagens"].items():
        totais[palavra] += quantidade
    recebidas += 1
    if recebidas % 1000 == 0:
        print(f"{recebidas} linhas processadas | {dict(totais)}")


def main():
    conexao = pika.BlockingConnection(pika.ConnectionParameters(HOST))
    canal = conexao.channel()

    canal.exchange_declare(exchange=EXCHANGE_CONTAGENS, exchange_type="fanout")

    # Fila temporária e exclusiva deste assinante (some quando ele desconecta)
    fila = canal.queue_declare(queue="", exclusive=True).method.queue
    canal.queue_bind(exchange=EXCHANGE_CONTAGENS, queue=fila)

    canal.basic_consume(queue=fila, on_message_callback=ao_receber, auto_ack=True)

    print("Assinando o tópico. Ctrl+C para ver o total final.")
    try:
        canal.start_consuming()
    except KeyboardInterrupt:
        print(f"\nTOTAL FINAL: {recebidas} linhas | {dict(totais)}")
    finally:
        conexao.close()


if __name__ == "__main__":
    main()
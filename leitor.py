"""Leitor de linhas (Produtor).

Lê o arquivo e insere na fila do broker apenas as linhas pares OU as ímpares,
conforme o parâmetro --tipo. A numeração das linhas começa em 1.

Uso:
    python leitor.py --tipo pares   --arquivo arquivo_grande.txt --palavras "python,fila,broker"
    python leitor.py --tipo impares --arquivo arquivo_grande.txt --palavras "python,fila,broker"
"""
import argparse
import json

import pika

from config import HOST, FILA_LINHAS


def ler_argumentos():
    parser = argparse.ArgumentParser(description="Leitor de linhas pares/ímpares")
    parser.add_argument("--tipo", choices=["pares", "impares"], required=True)
    parser.add_argument("--arquivo", required=True)
    parser.add_argument("--palavras", required=True,
                        help="palavras-chave separadas por vírgula")
    return parser.parse_args()


def main():
    args = ler_argumentos()
    palavras = [p.strip().lower() for p in args.palavras.split(",") if p.strip()]

    # Linha par: numero % 2 == 0 | Linha ímpar: numero % 2 == 1
    resto = 0 if args.tipo == "pares" else 1

    conexao = pika.BlockingConnection(pika.ConnectionParameters(HOST))
    canal = conexao.channel()

    # durable=True: a fila sobrevive a uma reinicialização do broker
    canal.queue_declare(queue=FILA_LINHAS, durable=True)

    enviadas = 0
    # Lê linha a linha (sem carregar o arquivo inteiro na memória)
    with open(args.arquivo, "r", encoding="utf-8", errors="ignore") as arquivo:
        for numero, linha in enumerate(arquivo, start=1):
            if numero % 2 != resto:
                continue

            mensagem = {
                "numero": numero,
                "linha": linha.rstrip("\n"),
                "palavras": palavras,   # os consumidores não precisam guardar estado
                "leitor": args.tipo,
            }
            canal.basic_publish(
                exchange="",                      # exchange padrão: vai direto para a fila
                routing_key=FILA_LINHAS,
                body=json.dumps(mensagem),
                properties=pika.BasicProperties(delivery_mode=2),  # mensagem persistente
            )
            enviadas += 1

    conexao.close()
    print(f"[leitor {args.tipo}] {enviadas} linhas enviadas para a fila '{FILA_LINHAS}'")


if __name__ == "__main__":
    main()
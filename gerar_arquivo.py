"""Gera um arquivo de texto grande para testar o projeto.

Uso:
    python gerar_arquivo.py              (100.000 linhas)
    python gerar_arquivo.py 500000       (500.000 linhas)
"""
import random
import sys

VOCABULARIO = [
    "python", "fila", "broker", "mensagem", "consumidor", "produtor",
    "topico", "dashboard", "paralelo", "distribuido", "sistema", "dados",
    "rede", "servidor", "cliente", "processo", "thread", "evento",
    "casa", "livro", "mesa", "agua", "tempo", "sol", "mar", "cidade",
]


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    random.seed(42)  # mesmo arquivo a cada execução

    with open("arquivo_grande.txt", "w", encoding="utf-8") as f:
        for _ in range(total):
            qtd = random.randint(5, 15)
            f.write(" ".join(random.choices(VOCABULARIO, k=qtd)) + "\n")

    print(f"arquivo_grande.txt gerado com {total} linhas")


if __name__ == "__main__":
    main()
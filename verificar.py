"""Conta as palavras-chave de forma sequencial, sem MOM, para conferir o resultado.

Uso:
    python verificar.py arquivo_grande.txt python,fila,broker
"""
import re
import sys
from collections import Counter


def main():
    arquivo = sys.argv[1]
    palavras = [p.strip().lower() for p in sys.argv[2].split(",") if p.strip()]

    totais = Counter()
    linhas = 0
    with open(arquivo, "r", encoding="utf-8", errors="ignore") as f:
        for linha in f:
            tokens = Counter(re.findall(r"\w+", linha.lower()))
            for palavra in palavras:
                totais[palavra] += tokens[palavra]
            linhas += 1

    print(f"{linhas} linhas | {dict(totais)}")


if __name__ == "__main__":
    main()
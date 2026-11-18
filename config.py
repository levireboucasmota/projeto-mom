"""Configurações compartilhadas por todos os componentes do projeto MOM."""

# Endereço do broker RabbitMQ
HOST = "localhost"

# Fila (ponto a ponto): os leitores inserem as linhas, os consumidores retiram
FILA_LINHAS = "linhas"

# Tópico (publish/subscribe): os consumidores publicam as contagens,
# o dashboard assina. No RabbitMQ, um tópico é uma exchange do tipo fanout.
EXCHANGE_CONTAGENS = "contagens"
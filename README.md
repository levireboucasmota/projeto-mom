# Projeto MOM: Contagem Paralela de Palavras-Chave

Projeto da disciplina **Programação Paralela e Distribuída** (2026.2), do curso de Engenharia de Computação do **Instituto Federal do Ceará (IFCE)**.

- **Professor:** Cidcley T. de Souza
- **Autor:** Levi

## Sobre o projeto

Workflow de computação paralela que conta palavras-chave em um arquivo grande utilizando **MOM (Message-Oriented Middleware)**. O arquivo é lido por dois leitores independentes (linhas pares e ímpares), as linhas são distribuídas por uma **fila** entre vários consumidores, e os resultados parciais são publicados em um **tópico** (publish/subscribe), que alimenta um dashboard em tempo real.

## Arquitetura

```
Cliente ──► Leitor (pares)   ──┐
        └─► Leitor (ímpares) ──┤
                               ▼
                    FILA "linhas" (Broker)
                               │
                  ┌────────────┼────────────┐
                  ▼            ▼            ▼
            Consumidor 1  Consumidor 2  Consumidor N
                  │            │            │
                  └────────────┼────────────┘
                               ▼
                 TÓPICO "contagens" (Broker)
                               │
                               ▼
                       Dashboard (Subscriber)
```

| Componente | Papel | Arquivo |
|---|---|---|
| Cliente | Interface que solicita as palavras-chave e instancia os dois leitores | `cliente.py` |
| Leitor | Produtor: lê as linhas pares ou ímpares e as insere na fila | `leitor.py` |
| Broker | RabbitMQ: mantém a fila de linhas e o tópico de resultados | n/a |
| Consumidor | Obtém a próxima linha, conta as palavras-chave e publica o resultado no tópico | `consumidor.py` |
| Dashboard | Subscriber: acumula as contagens e atualiza a interface | `dashboard.py` |

Os nomes da fila, do tópico e o endereço do broker ficam centralizados em `config.py`.

## Tecnologias

- **Python 3.10+**
- **RabbitMQ**: broker de mensagens
- **pika**: cliente Python para RabbitMQ
- **PySide6**: interfaces gráficas (Cliente e Dashboard)
- **PyInstaller**: geração dos executáveis `.exe`

## Pré-requisitos

1. [Python 3.10 ou superior](https://www.python.org/downloads/)
2. RabbitMQ em execução na porta `5672`, por uma das opções:
   - **Windows (sem Docker):** instalar o [Erlang/OTP](https://www.erlang.org/downloads) e depois o [RabbitMQ Server](https://www.rabbitmq.com/docs/install-windows). Para habilitar o painel web, execute como administrador: `rabbitmq-plugins enable rabbitmq_management`
   - **Docker:**
     ```bash
     docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
     ```

O painel de administração fica em http://localhost:15672 (usuário `guest`, senha `guest`).

## Instalação

```powershell
git clone https://github.com/levireboucasmota/projeto-mom.git
cd projeto-mom
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Como executar

Com o RabbitMQ rodando e o ambiente virtual ativado, abra um terminal para cada componente:

**1. Dashboard**
```powershell
python dashboard.py
```

**2. Consumidores** (execute quantas instâncias quiser; elas dividem a fila entre si)
```powershell
python consumidor.py
```

**3. Cliente**
```powershell
python cliente.py
```

No Cliente:
1. Informe as palavras-chave a pesquisar (separadas por vírgula).
2. Selecione o arquivo de texto.
3. Clique em iniciar. O Cliente instancia os dois leitores (linhas pares e ímpares) e o Dashboard passa a exibir as contagens em tempo real.

## Executáveis

Os executáveis (`.exe`) estão na pasta `release/` do repositório. Para gerá-los novamente:

```powershell
pip install pyinstaller
pyinstaller --onefile --noconsole cliente.py
pyinstaller --onefile --noconsole dashboard.py
pyinstaller --onefile consumidor.py
pyinstaller --onefile leitor.py
```

## Estrutura do repositório

```
projeto-mom/
├── cliente.py
├── leitor.py
├── consumidor.py
├── dashboard.py
├── config.py
├── requirements.txt
├── release/          (executáveis)
└── README.md
```

## Conceitos de MOM aplicados

- **Fila (ponto a ponto):** cada linha é entregue a apenas um consumidor, o que permite o balanceamento da carga entre eles.
- **Tópico (publish/subscribe):** cada resultado publicado é entregue a todos os assinantes, no caso o Dashboard.
- **Desacoplamento:** leitores, consumidores e dashboard não se conhecem; comunicam-se apenas pelo broker e podem ser iniciados e escalados de forma independente.

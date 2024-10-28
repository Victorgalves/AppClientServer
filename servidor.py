import socket
import matplotlib
import hashlib  # Para checksum
matplotlib.use('agg')  # Para salvar o gráfico sem abrir uma janela
from matplotlib import pyplot as plt

host = socket.gethostname()
port = 8001
address = (host, port)
buffer = 1024

x, y = [], []  # Dados para o gráfico
counter = 0  # Contador para o eixo X

def calcular_checksum(mensagem):
    """Calcula o checksum MD5 da mensagem."""
    return hashlib.md5(mensagem.encode()).hexdigest()

def verificar_checksum(mensagem, checksum):
    """Verifica se o checksum da mensagem é válido."""
    return calcular_checksum(mensagem) == checksum

def exibir_menu_protocolo():
    print("Escolha o protocolo de controle:")
    print("1. Go-Back-N")
    print("2. Selective Repeat")
    escolha = input("Escolha uma opcao: ")
    return 'go-back-n' if escolha == '1' else 'selective repeat'

def exibir_menu_transporte():
    print("Escolha o protocolo de transporte:")
    print("1. TCP")
    print("2. UDP")
    escolha = input("Escolha uma opcao: ")
    return 'TCP' if escolha == '1' else 'UDP'

# Escolha dos protocolos
protocolo_negociado = exibir_menu_protocolo()
protocol = exibir_menu_transporte()

# Configuração do socket
if protocol == 'UDP':
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(address)
elif protocol == 'TCP':
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(address)
    sock.listen()

print(f'Servidor pronto. Aguardando conexao... (Protocolo: {protocol}, Controle: {protocolo_negociado})')

while True:
    if protocol == 'TCP':
        connection, client_address = sock.accept()
        print(f"Cliente conectado: {client_address}")

        # Verifica se os protocolos são compatíveis
        client_protocol = connection.recv(buffer).decode('utf-8')
        if client_protocol != protocol:
            print(f"Erro: Protocolo incompatível. Servidor: {protocol}, Cliente: {client_protocol}")
            connection.send(b"Erro: Protocolo incompativel.")
            connection.close()
            break
        else:
            print(f"Protocolo compatível: {protocol}")

        # Continua a comunicação normal após validação do protocolo
        while True:
            data = connection.recv(buffer).decode('utf-8').split('|')
            mensagem, checksum = data[0], data[1]

            if not verificar_checksum(mensagem, checksum):
                connection.send(b'NAK')
                print("Erro de integridade. NAK enviado.")
                continue

            if mensagem == 'dcs':
                print("Desconectando cliente...")
                connection.close()
                break
            elif mensagem == 'grafico':
                if y:  # Verifica se há dados para plotar
                    plt.figure(figsize=(8, 6))
                    barras = plt.bar(range(1, len(y) + 1), y, color='b', width=0.4)
                    plt.xlabel('Quantidade de Pacotes Recebidos', fontsize=14)
                    plt.ylabel('Valores', fontsize=14)
                    plt.title(f'Grafico de Valores Recebidos - {protocol}', fontsize=16)
                    plt.xticks(range(1, len(y) + 1))
                    plt.grid(True, axis='y', linestyle='--', alpha=0.7)
                    plt.ylim(0, max(y) * 1.2)

                    for barra in barras:
                        altura = barra.get_height()
                        plt.text(barra.get_x() + barra.get_width() / 2, altura + 2, f'{int(altura)}',
                                 ha='center', va='bottom', fontsize=12, color='black')

                    plt.savefig(f'grafico_{protocol}.png', dpi=300)
                    print("Grafico salvo com sucesso.")
                    connection.send(b"Grafico gerado com sucesso.")
                else:
                    print("Nenhum dado para gerar o grafico.")
                    connection.send(b"Nenhum dado para gerar o grafico.")
            elif mensagem.isnumeric():
                y.append(int(mensagem))
                counter += 1
                x.append(counter)
                connection.send(b'ACK')
                print(f"Dados para o grafico - X: {x}, Y: {y}")
            else:
                print(f"Mensagem de texto recebida: {mensagem}")

    elif protocol == 'UDP':
        data, client_address = sock.recvfrom(buffer)
        mensagem, checksum = data.decode('utf-8').split('|')

        if not verificar_checksum(mensagem, checksum):
            sock.sendto(b'NAK', client_address)
            print("Erro de integridade. NAK enviado.")
            continue

        if mensagem == 'dcs':
            print("Desconectando servidor...")
            break


import socket
import hashlib  # Para checksum

host = socket.gethostname()
port = 8001
address = (host, port)

def calcular_checksum(mensagem):
    """Calcula o checksum MD5 da mensagem."""
    return hashlib.md5(mensagem.encode()).hexdigest()

def enviar_mensagem(mensagem):
    """Envia a mensagem com checksum para o servidor."""
    checksum = calcular_checksum(mensagem)
    pacote = f"{mensagem}|{checksum}"
    if protocol == 'UDP':
        sock.sendto(pacote.encode(), address)
    else:
        sock.send(pacote.encode())

def exibir_menu_protocolo():
    print("Escolha o protocolo de transporte:")
    print("1. TCP")
    print("2. UDP")
    escolha = input("Escolha uma opcao: ")
    return 'TCP' if escolha == '1' else 'UDP'

# Escolha do protocolo de transporte
protocol = exibir_menu_protocolo()

# Configuração do socket
if protocol == 'UDP':
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
elif protocol == 'TCP':
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(address)

while True:
    print("\nMenu:")
    print("1. Enviar mensagem")
    print("2. Solicitar grafico")
    print("3. Enviar pacote corrompido")
    print("4. Desconectar")

    opcao = input("Escolha uma opcao: ")

    if opcao == '1':
        mensagem = input("Digite a mensagem: ")
        enviar_mensagem(mensagem)

    elif opcao == '2':
        enviar_mensagem('grafico')

    elif opcao == '3':
        enviar_mensagem("mensagem_corrompida|00000000000000000000000000000000")

    elif opcao == '4':
        enviar_mensagem('dcs')
        break

    else:
        print("Opcao invalida. Tente novamente.")

if protocol == 'TCP':
    sock.close()

import socket
import time

# Função para enviar um pacote individual
def enviar_pacote(mensagem, erro=False):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 8081))

    # Simulação de erro de integridade
    if erro:
        mensagem = mensagem + "CORROMPIDO"  # Corrupção no pacote

    client_socket.send(mensagem.encode())
    response = client_socket.recv(1024)
    print(f"Resposta do servidor: {response.decode()}")

    client_socket.close()

# Função para enviar vários pacotes em rajada
def enviar_lote_pacotes(pacotes, erro=False):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 8081))
    for pacote in pacotes:
        # Simula erro de integridade em pacotes específicos
        if erro:
            pacote = pacote + "CORROMPIDO"

        client_socket.send(pacote.encode())
        response = client_socket.recv(1024)
        print(f"Resposta do servidor: {response.decode()}")
        time.sleep(1)  # Simula atraso no envio

    client_socket.close()

if __name__ == "__main__":
    # Teste com pacotes individuais
    enviar_pacote("Pacote 1", erro=False)  # Pacote correto
    enviar_pacote("Pacote 2", erro=True)   # Pacote com erro

    # Teste com lotes de pacotes
    pacotes = ["Pacote 3", "Pacote 4", "Pacote 5"]
    enviar_lote_pacotes(pacotes, erro=False)  # Envio normal de lotes

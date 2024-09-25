import socket
import time

# Função para enviar um pacote individual
def enviar_pacote(client_socket, mensagem, erro=False):
    # Simulação de erro de integridade
    if erro:
        mensagem = mensagem + "CORROMPIDO"  # Corrupção no pacote

    client_socket.send(mensagem.encode()) # Enviar dados do cliente para o servidor
    response = client_socket.recv(1024) # Receber uma resposta do servidor
    print(f"Resposta do servidor: {response.decode()}") # Exibi resposta do servidor

# Função para enviar vários pacotes em rajada
def enviar_lote_pacotes(client_socket, pacotes, erro=False):
    for pacote in pacotes:
        # Simula erro de integridade em pacotes específicos
        if erro:
            pacote = pacote + "CORROMPIDO"

        client_socket.send(pacote.encode()) # Enviar pacode do cliente para o servidor
        response = client_socket.recv(1024) # Receber uma resposta do servidor
        print(f"Resposta do servidor: {response.decode()}") # Exibi resposta do servidor
        time.sleep(1)  # Simula atraso no envio


if __name__ == "__main__":
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Cria uma socket para o cliente
    client_socket.connect(('localhost', 8081)) # Estabelece a conexão entre o cliente e o servidor

    # Teste com pacotes individuais
    enviar_pacote(client_socket, "Pacote 1", erro=False)  # Pacote correto
    enviar_pacote(client_socket, "Pacote 2", erro=True)   # Pacote com erro

    # Teste com lotes de pacotes
    pacotes = ["Pacote 3", "Pacote 4", "Pacote 5"]
    enviar_lote_pacotes(client_socket, pacotes, erro=False)  # Envio normal de lotes

    client_socket.close() # Fecha a conexão do cliente com o seervidor

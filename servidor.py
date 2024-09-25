import socket
import random

# Tamanho da janela de recepção
janela_recepcao = 5
pacotes_recebidos = 0

def iniciar_servidor():
    global pacotes_recebidos
    # Cria um socket TCP/IP
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 8081))
    server_socket.listen(1)
    print("Servidor esperando por conexão...")

    while True:  # Mantém o servidor rodando indefinidamente
        conn, addr = server_socket.accept()
        print(f"Conectado a {addr}")

        while True:
            data = conn.recv(1024)
            if not data:
                print("Conexão encerrada pelo cliente.")
                break  # Sai desse loop e volta para aceitar outra conexão
        
            # Controle de fluxo com janela de recepção
            if pacotes_recebidos < janela_recepcao:
                pacotes_recebidos += 1

                # Simulação de perda de pacotes
                if random.choice([True, False]):  # Simula perda de pacotes aleatoriamente
                    print("Pacote perdido!")
                    conn.sendall(b'Pacote perdido!')  # Envia resposta para o cliente
                else:
                    print(f"Recebido: {data.decode()}")
                    conn.sendall(b'Pacote recebido com sucesso!')
            else:
                print("Janela cheia, não pode receber mais pacotes.")
                conn.sendall(b'Janela cheia!')

            # Reseta a janela se todos os pacotes forem processados
            if pacotes_recebidos >= janela_recepcao:
                pacotes_recebidos = 0

        conn.close()  # Fecha a conexão após o cliente encerrar

if __name__ == "__main__":
    iniciar_servidor()

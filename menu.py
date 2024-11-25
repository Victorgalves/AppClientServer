import os

def menu():
    while True:
        print("\n--- Menu de Execução ---")
        print("1. Iniciar servidor Go-Back-N (GBN)")
        print("2. Iniciar servidor Go-Back-N com simulação de erros em ACKs")
        print("3. Iniciar cliente Go-Back-N (Rajada - Padrão)")
        print("4. Iniciar cliente Go-Back-N (Envio Único)")
        print("5. Iniciar servidor Selective Repeat (SR)")
        print("6. Iniciar servidor Selective Repeat com simulação de erros em ACKs")
        print("7. Iniciar cliente Selective Repeat (Rajada - Padrão)")
        print("8. Iniciar cliente Selective Repeat (Envio Único)")
        print("9. Sair")
        escolha = input("\nEscolha uma opção: ")

        if escolha == "1":
            os.system("python servidor.py")
        elif escolha == "2":
            # Captura o número do pacote para simulação de erro
            error_ack = input("Digite o número do pacote em que deseja simular erro no ACK: ")
            os.system(f"python servidor.py --simulate_ack_error --error_acks {error_ack}")
        elif escolha == "3":
            os.system("python cliente.py")
        elif escolha == "4":
            os.system("python cliente.py --mode single")
        elif escolha == "5":
            os.system("python servidor.py --protocol SR")
        elif escolha == "6":
            # Captura o número do pacote para simulação de erro no SR
            error_ack = input("Digite o número do pacote em que deseja simular erro no ACK (SR): ")
            os.system(f"python servidor.py --protocol SR --simulate_ack_error --error_acks {error_ack}")
        elif escolha == "7":
            os.system("python cliente.py --protocol SR")
        elif escolha == "8":
            os.system("python cliente.py --protocol SR --mode single")
        elif escolha == "9":
            print("Encerrando...")
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    menu()

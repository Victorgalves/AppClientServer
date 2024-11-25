import asyncio
import argparse
import logging
import sys
import datetime
from logging.handlers import RotatingFileHandler
from my_protocol import create_packet, unpack_packet, calculate_checksum

# Configurações do cliente
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5001
DEFAULT_WINDOW_SIZE = 5
DEFAULT_PROTOCOL = 'GBN'
TIMEOUT_INTERVAL = 4  # segundos
MAX_RETRANSMISSIONS = 5  # Número máximo de retransmissões por pacote

# Configurar o logger com RotatingFileHandler e StreamHandler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler(
            'client.log', maxBytes=5 * 1024 * 1024, backupCount=5
        ),
        logging.StreamHandler(sys.stdout)
    ]
)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Cliente de transporte confiável (Asyncio)')
    parser.add_argument('--host', default=DEFAULT_HOST, help='Endereço IP do servidor')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Porta do servidor')
    parser.add_argument('--window', type=int, default=DEFAULT_WINDOW_SIZE, help='Tamanho da janela de envio')
    parser.add_argument('--protocol', choices=['GBN', 'SR'], default=DEFAULT_PROTOCOL, help='Protocolo a ser utilizado')
    parser.add_argument('--simulate_data_error', action='store_true', help='Simular erro de dados')
    parser.add_argument('--error_packets', nargs='*', type=int, default=[], help='Seqs dos pacotes a serem corrompidos')
    parser.add_argument('--mode', choices=['single', 'batch'], default='batch', help='Modo de envio: single ou batch')
    return parser.parse_args()


def show_menu():
    print("Escolha o protocolo:")
    protocol = input("1. Go-Back-N (GBN)\n2. Selective Repeat (SR)\nEscolha (1/2): ")
    if protocol == '1':
        protocol = 'GBN'
    elif protocol == '2':
        protocol = 'SR'
    else:
        print("Escolha inválida, usando o padrão GBN.")
        protocol = 'GBN'
    
    print("\nEscolha o modo de envio:")
    mode = input("1. Único\n2. Rajada\nEscolha (1/2): ")
    if mode == '1':
        mode = 'single'
    elif mode == '2':
        mode = 'batch'
    else:
        print("Escolha inválida, usando o padrão Rajada.")
        mode = 'batch'

    simulate_error = input("\nDeseja simular erro de dados? (S/N): ").strip().lower()
    if simulate_error == 's':
        simulate_error = True
        error_packets = input("Informe os números de sequência dos pacotes a serem corrompidos (separados por espaço): ")
        error_packets = list(map(int, error_packets.split()))
    else:
        simulate_error = False
        error_packets = []

    return protocol, mode, simulate_error, error_packets


async def send_packets(reader, writer, protocol, recv_window_size, args):
    total_packets = 6  # Número total de pacotes a serem enviados
    base = 0
    next_seq_num = 0
    timers = {}
    sent_packets = {}
    acked_packets = set()
    congestion_window = 1
    ssthresh = 16

    retransmissions = {}  # Contador de retransmissões por pacote

    def corrupt_data_if_needed(seq_num, data):
        if args.simulate_data_error and seq_num in args.error_packets:
            logging.info(f'Inserindo erro no pacote {seq_num}.')
            # Corromper os dados invertendo os bytes
            return bytes(~b & 0xFF for b in data)
        return data

    async def send_packet(seq_num, resend=False):
        nonlocal congestion_window, ssthresh
        data_str = f'Pacote {seq_num}'
        data = data_str.encode()
        if not resend:
            data_to_send = corrupt_data_if_needed(seq_num, data)
            sent_packets[seq_num] = {'data': data, 'sent_time': asyncio.get_event_loop().time()}
            retransmissions[seq_num] = 0  # Inicializar contador de retransmissões
            logging.info(f'Enviado pacote Seq={seq_num}, Dados={data_to_send}')
        else:
            data_to_send = data  # Nas retransmissões, enviamos os dados corretos
            retransmissions[seq_num] = retransmissions.get(seq_num, 0) + 1
            logging.info(f'Reenviando pacote Seq={seq_num}, Dados={data_to_send}')

        packet = create_packet(seq_num, data_to_send)
        writer.write(packet)
        await writer.drain()

        # Iniciar temporizador
        timers[seq_num] = asyncio.get_event_loop().time()

    async def process_server_response():
        nonlocal recv_window_size, congestion_window, ssthresh, base

        try:
            response = await asyncio.wait_for(reader.read(4096), timeout=0.1)
            if not response:
                return

            seq_num_resp, ack_flag, nak_flag, recv_checksum, data = unpack_packet(response)
            if ack_flag:
                logging.info(f'Recebido ACK para Seq={seq_num_resp}')
            elif nak_flag:
                logging.info(f'Recebido NAK para Seq={seq_num_resp}')

            # **Verificar o checksum do ACK/NAK**
            ack_data_checksum = calculate_checksum(data)
            if recv_checksum != ack_data_checksum:
                logging.warning(f'Recebido {"ACK" if ack_flag else "NAK"} para Seq={seq_num_resp} com erro de checksum.')
                return

            # Atualizar a janela de recepção, se necessário
            if len(data) >= 4:
                new_recv_window_size = int.from_bytes(data[:4], byteorder='big')
                if new_recv_window_size != recv_window_size:
                    logging.info(f'Atualização da janela de recepção do servidor: {new_recv_window_size}')
                    recv_window_size = new_recv_window_size

            if ack_flag:
                if protocol == 'GBN':
                    if seq_num_resp >= base:
                        for seq in range(base, seq_num_resp + 1):
                            timers.pop(seq, None)
                            sent_packets.pop(seq, None)
                        base = seq_num_resp + 1
                        if congestion_window < ssthresh:
                            congestion_window += 1
                            logging.info(f'Slow Start: congestion_window={congestion_window}')
                        else:
                            congestion_window += 1 / congestion_window
                            logging.info(f'Congestion Avoidance: congestion_window={congestion_window:.2f}')
                elif protocol == 'SR':
                    if seq_num_resp not in acked_packets:
                        acked_packets.add(seq_num_resp)
                        timers.pop(seq_num_resp, None)
                        sent_packets.pop(seq_num_resp, None)
                        if congestion_window < ssthresh:
                            congestion_window += 1
                            logging.info(f'Slow Start: congestion_window={congestion_window}')
                        else:
                            congestion_window += 1 / congestion_window
                            logging.info(f'Congestion Avoidance: congestion_window={congestion_window:.2f}')
                        while base in acked_packets:
                            base += 1
            elif nak_flag:
                logging.info(f'Recebido NAK para Seq={seq_num_resp}. Reenviando...')
                ssthresh = max(int(congestion_window // 2), 1)
                congestion_window = 1
                if retransmissions.get(seq_num_resp, 0) < MAX_RETRANSMISSIONS:
                    await send_packet(seq_num_resp, resend=True)
                else:
                    logging.error(f'Número máximo de retransmissões atingido para pacote {seq_num_resp}. Encerrando conexão.')
                    writer.close()
                    await writer.wait_closed()
        except asyncio.TimeoutError:
            pass

    async def check_timeouts():
        nonlocal congestion_window, ssthresh, base, next_seq_num
        current_time = asyncio.get_event_loop().time()
        if protocol == 'GBN':
            if base in timers and (current_time - timers[base]) > TIMEOUT_INTERVAL:
                logging.warning(f'Temporizador expirado para pacote {base}. Reenviando a partir de {base}')
                ssthresh = max(int(congestion_window // 2), 1)
                congestion_window = 1
                next_seq_num = base
                for seq in range(base, total_packets):  # Remover a limitação pela janela de congestionamento
                    await send_packet(seq, resend=True)

        elif protocol == 'SR':
            for seq in list(timers.keys()):
                if (current_time - timers[seq]) > TIMEOUT_INTERVAL:
                    logging.warning(f'Temporizador expirado para pacote {seq}. Reenviando...')
                    ssthresh = max(int(congestion_window // 2), 1)
                    congestion_window = max(int(congestion_window // 2), 1)

            # Verifica o número de retransmissões
                    if retransmissions.get(seq, 0) < MAX_RETRANSMISSIONS:
                        await send_packet(seq, resend=True)
                    else:
                        # Quando atingir o limite de retransmissões, ignore esse pacote
                        logging.error(f'Número máximo de retransmissões atingido para pacote {seq}. Ignorando e avançando para o próximo pacote.')

                        # Remover o pacote da lista de timers e pacotes enviados
                        timers.pop(seq, None)
                        sent_packets.pop(seq, None)

                        # Avançar o base para o próximo pacote
                        if seq == base:  # Se o pacote que falhou for o 'base', mova o 'base' para frente
                            base += 1

                        continue  # Continue para o próximo pacote


    while base < total_packets:
        window_size = min(congestion_window, recv_window_size, args.window)
        
        if args.mode == 'batch':
            # Envia pacotes de acordo com a janela de congestionamento, aguardando as respostas
            while next_seq_num < total_packets and next_seq_num < base + window_size:
                if next_seq_num not in sent_packets:
                    await send_packet(next_seq_num)
                next_seq_num += 1

            # Aguardar e processar as respostas de ACK/NAK
            while base < next_seq_num:
                await process_server_response()
                await check_timeouts()
                await asyncio.sleep(0.01)

        else:
            if next_seq_num < total_packets and next_seq_num < base + window_size:
                await send_packet(next_seq_num)
                next_seq_num += 1
                while base < next_seq_num:
                    await process_server_response()
                    await check_timeouts()

        await asyncio.sleep(0.01)

        if protocol == 'SR' and len(acked_packets) == total_packets:
            break

    logging.info('Envio concluído.')
    writer.close()
    await writer.wait_closed()


async def start_client():
    args = parse_arguments()
    reader, writer = await asyncio.open_connection(args.host, args.port)

    protocol_str = args.protocol.ljust(3)
    writer.write(protocol_str.encode())
    await writer.drain()
    selected_protocol = (await reader.read(3)).decode().strip()
    logging.info(f'Protocolo selecionado: {selected_protocol}')

    recv_window_size_bytes = await reader.read(4)
    recv_window_size = int.from_bytes(recv_window_size_bytes, byteorder='big')
    logging.info(f'Janela de recepção do servidor: {recv_window_size}')

    await send_packets(reader, writer, selected_protocol, recv_window_size, args)


if __name__ == "__main__":
    asyncio.run(start_client())



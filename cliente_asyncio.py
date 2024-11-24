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

# Configurar o logger com RotatingFileHandler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler(
            'client.log', maxBytes=5*1024*1024, backupCount=5
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

async def send_packets(reader, writer, protocol, recv_window_size, args):
    total_packets = 20  # Número total de pacotes a serem enviados
    base = 0
    next_seq_num = 0
    timers = {}
    sent_packets = {}
    acked_packets = set()
    congestion_window = 1
    ssthresh = 16

    def corrupt_data_if_needed(seq_num, data):
        if args.simulate_data_error and seq_num in args.error_packets:
            logging.info(f'Inserindo erro no pacote {seq_num}.')
            # Corromper os dados simplesmente invertendo os bytes
            return bytes(~b & 0xFF for b in data)
        return data

    async def send_packet(seq_num, resend=False):
        nonlocal congestion_window, ssthresh
        if resend:
            data = sent_packets[seq_num]['data']
            logging.info(f'Reenviando pacote Seq={seq_num}, Dados={data}')
        else:
            data_str = f'Pacote {seq_num}'
            data = data_str.encode()
            data = corrupt_data_if_needed(seq_num, data)
            logging.info(f'Enviado pacote Seq={seq_num}, Dados={data}')
            sent_packets[seq_num] = {'data': data, 'sent_time': asyncio.get_event_loop().time()}

        packet = create_packet(seq_num, data)
        writer.write(packet)
        await writer.drain()

        if not resend:
            # Iniciar temporizador
            timers[seq_num] = asyncio.get_event_loop().time()

    async def process_server_response():
        nonlocal recv_window_size, congestion_window, ssthresh, base

        try:
            response = await asyncio.wait_for(reader.read(4096), timeout=TIMEOUT_INTERVAL)
            if not response:
                return

            seq_num_resp, ack_flag, nak_flag, recv_checksum, data = unpack_packet(response)
            logging.info(f'Recebido {"ACK" if ack_flag else "NAK"} para Seq={seq_num_resp}')

            # **Verificar o checksum do ACK**
            ack_data_checksum = calculate_checksum(data)
            if recv_checksum != ack_data_checksum:
                logging.warning(f'Recebido {"ACK" if ack_flag else "NAK"} para Seq={seq_num_resp} com erro de checksum.')
                # Ignorar o ACK/NAK corrompido
                return

            # Verificar se há uma atualização da janela de recepção
            if len(data) >= 4:
                new_recv_window_size = int.from_bytes(data[:4], byteorder='big')
                if new_recv_window_size != recv_window_size:
                    logging.info(f'Atualização da janela de recepção do servidor: {new_recv_window_size}')
                    recv_window_size = new_recv_window_size

            if ack_flag:
                if protocol == 'GBN':
                    if seq_num_resp >= base:
                        base = seq_num_resp + 1
                        # Resetar temporizador
                        timers.pop(seq_num_resp, None)
                        # Controle de congestionamento
                        if congestion_window < ssthresh:
                            congestion_window += 1
                            logging.info(f'Slow Start: congestion_window={congestion_window}')
                        else:
                            congestion_window += 1 / congestion_window
                            logging.info(f'Congestion Avoidance: congestion_window={congestion_window:.2f}')
                elif protocol == 'SR':
                    if seq_num_resp not in acked_packets:
                        acked_packets.add(seq_num_resp)
                        # Remover temporizador
                        timers.pop(seq_num_resp, None)
                        sent_packets.pop(seq_num_resp, None)
                        # Atualizar congestion_window
                        if congestion_window < ssthresh:
                            congestion_window += 1
                            logging.info(f'Slow Start: congestion_window={congestion_window}')
                        else:
                            congestion_window += 1 / congestion_window
                            logging.info(f'Congestion Avoidance: congestion_window={congestion_window:.2f}')
                        # Atualizar base
                        while base in acked_packets:
                            base += 1
            elif nak_flag:
                logging.info(f'Recebido NAK para Seq={seq_num_resp}. Reenviando...')
                ssthresh = max(int(congestion_window // 2), 1)
                congestion_window = max(int(congestion_window // 2), 1)
                await send_packet(seq_num_resp, resend=True)
                timers[seq_num_resp] = asyncio.get_event_loop().time()

        except asyncio.TimeoutError:
            current_time = asyncio.get_event_loop().time()
            if protocol == 'GBN':
                if (current_time - timers.get(base, 0)) > TIMEOUT_INTERVAL:
                    logging.warning(f'Temporizador expirado para pacote {base}. Reenviando a partir de {base}')
                    ssthresh = max(int(congestion_window // 2), 1)
                    congestion_window = 1
                    next_seq_num = base
                    for seq in range(base, min(base + int(congestion_window), total_packets)):
                        await send_packet(seq, resend=True)
                        timers[seq] = asyncio.get_event_loop().time()
            elif protocol == 'SR':
                for seq in list(timers.keys()):
                    if (current_time - timers[seq]) > TIMEOUT_INTERVAL:
                        logging.warning(f'Temporizador expirado para pacote {seq}. Reenviando...')
                        ssthresh = max(int(congestion_window // 2), 1)
                        congestion_window = max(int(congestion_window // 2), 1)
                        await send_packet(seq, resend=True)
                        timers[seq] = asyncio.get_event_loop().time()

    # Envio de pacotes
    while base < total_packets:
        window_size = min(congestion_window, recv_window_size, args.window)
        if protocol == 'GBN':
            if next_seq_num < base + window_size and next_seq_num < total_packets:
                await send_packet(next_seq_num)
                next_seq_num += 1
        elif protocol == 'SR':
            while next_seq_num < base + window_size and next_seq_num < total_packets:
                if next_seq_num not in sent_packets:
                    await send_packet(next_seq_num)
                next_seq_num += 1

        await process_server_response()

        # Aguardar um breve período antes de verificar novamente
        await asyncio.sleep(0.1)

        # Verificar condição de término para SR
        if protocol == 'SR':
            if len(acked_packets) == total_packets:
                break

    logging.info('Envio concluído.')
    writer.close()
    await writer.wait_closed()


async def start_client():
    args = parse_arguments()
    reader, writer = await asyncio.open_connection(args.host, args.port)

    # Negociar protocolo
    protocol_str = args.protocol.ljust(3)
    writer.write(protocol_str.encode())
    await writer.drain()
    selected_protocol = (await reader.read(3)).decode().strip()
    logging.info(f'Protocolo selecionado: {selected_protocol}')

    # Receber tamanho da janela de recepção
    recv_window_size_bytes = await reader.read(4)
    recv_window_size = int.from_bytes(recv_window_size_bytes, byteorder='big')
    logging.info(f'Janela de recepção do servidor: {recv_window_size}')

    await send_packets(reader, writer, selected_protocol, recv_window_size, args)


if __name__ == '__main__':
    # Adicionar separador no log
    logging.info('\n\n' + '=' * 50)
    logging.info(f'Iniciando nova execução do cliente em {datetime.datetime.now()}')
    logging.info('=' * 50 + '\n')
    asyncio.run(start_client())

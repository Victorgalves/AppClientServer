import asyncio
import argparse
import logging
import sys
import datetime
from logging.handlers import RotatingFileHandler
from my_protocol import create_packet, unpack_packet, calculate_checksum

# Configurações padrão do cliente
HOST = '127.0.0.1'
PORT = 5001
PROTOCOL = 'SR'
MAX_SEND_WINDOW_SIZE = 5
TOTAL_PACKETS = 20
LOG_FILE = 'client.log'
TIMEOUT_INTERVAL = 4  # Segundos

# Configurar o logger com RotatingFileHandler
logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5*1024*1024, backupCount=5
)  # 5 MB por arquivo, mantendo até 5 backups
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def parse_arguments():
    parser = argparse.ArgumentParser(description='Cliente de transporte confiável (Asyncio)')
    parser.add_argument('--host', default=HOST, help='Endereço IP do servidor')
    parser.add_argument('--port', type=int, default=PORT, help='Porta do servidor')
    parser.add_argument('--protocol', choices=['GB', 'SR'], default=PROTOCOL, help='Protocolo a ser utilizado')
    parser.add_argument('--window', type=int, default=MAX_SEND_WINDOW_SIZE, help='Tamanho máximo da janela de envio')
    parser.add_argument('--packets', type=int, default=TOTAL_PACKETS, help='Número total de pacotes a enviar')
    parser.add_argument('--simulate_data_error', action='store_true', help='Simular erros nos dados')
    parser.add_argument('--error_packets', nargs='*', type=int, default=[], help='Pacotes nos quais inserir erros')
    parser.add_argument('--mode', choices=['single', 'batch'], default='batch', help='Modo de envio: single ou batch')
    return parser.parse_args()


async def send_packets(reader, writer, protocol, recv_window_size, args):
    base = 0
    next_seq_num = 0
    congestion_window = 1
    ssthresh = 16
    timers = {}
    MAX_RETRIES = 5
    retry_count = {}
    total_packets = args.packets

    async def send_packet(seq, resend=False):
        try:
            data = f'Pacote {seq}'.encode()
            checksum_error = False

            if not resend and args.simulate_data_error and seq in args.error_packets:
                logging.info(f'Inserindo erro no pacote {seq}.')
                checksum_error = True

            if resend:
                retry_count[seq] = retry_count.get(seq, 0) + 1
                if retry_count[seq] > MAX_RETRIES:
                    logging.error(f'Número máximo de tentativas atingido para o pacote {seq}. Abortando.')
                    sys.exit(1)

            packet = create_packet(seq, data, checksum_error=checksum_error)
            writer.write(packet)
            await writer.drain()
            logging.info(f'Enviado pacote Seq={seq}, Dados={data}')
        except Exception as e:
            logging.error(f'Erro ao enviar pacote {seq}: {e}')
            sys.exit(1)

    async def process_server_response():
        nonlocal recv_window_size, congestion_window, ssthresh, base

        try:
            response = await asyncio.wait_for(reader.read(4096), timeout=TIMEOUT_INTERVAL)
            if not response:
                return

            seq_num_resp, ack_flag, nak_flag, recv_checksum, data = unpack_packet(response)
            logging.info(f'Recebido {"ACK" if ack_flag else "NAK"} para Seq={seq_num_resp}')

            # Verificar se há uma atualização da janela de recepção
            if len(data) >= 4:
                new_recv_window_size = int.from_bytes(data[:4], byteorder='big')
                if new_recv_window_size != recv_window_size:
                    logging.info(f'Atualização da janela de recepção do servidor: {new_recv_window_size}')
                    recv_window_size = new_recv_window_size

            if ack_flag:
                # Atualizar base
                if seq_num_resp >= base:
                    base = seq_num_resp + 1
                    # Resetar temporizador
                    if base in timers:
                        del timers[base]
                    # Controle de congestionamento
                    if congestion_window < ssthresh:
                        # Slow Start
                        congestion_window += 1
                        logging.info(f'Slow Start: congestion_window={congestion_window}')
                    else:
                        # Congestion Avoidance
                        congestion_window += 1 / congestion_window
                        logging.info(f'Congestion Avoidance: congestion_window={congestion_window:.2f}')
            elif nak_flag:
                logging.info(f'Recebido NAK para Seq={seq_num_resp}. Reenviando...')
                ssthresh = max(int(congestion_window // 2), 1)
                congestion_window = max(int(congestion_window // 2), 1)
                await send_packet(seq_num_resp, resend=True)
                timers[seq_num_resp] = asyncio.get_event_loop().time()

        except asyncio.TimeoutError:
            # Verificar timeouts
            current_time = asyncio.get_event_loop().time()
            if (current_time - timers.get(base, 0)) > TIMEOUT_INTERVAL:
                logging.warning(f'Temporizador expirado para pacote {base}. Reenviando todos os pacotes a partir de {base}')
                ssthresh = max(int(congestion_window // 2), 1)
                congestion_window = 1
                next_seq_num = base
                for seq in range(base, min(base + int(congestion_window), total_packets)):
                    await send_packet(seq, resend=True)
                    timers[seq] = asyncio.get_event_loop().time()

    # Envio de pacotes
    while base < total_packets:
        if next_seq_num < base + min(congestion_window, recv_window_size, args.window) and next_seq_num < total_packets:
            await send_packet(next_seq_num)
            if base == next_seq_num:
                timers[base] = asyncio.get_event_loop().time()
            next_seq_num += 1

        await process_server_response()

        # Aguardar um breve período antes de verificar novamente
        await asyncio.sleep(0.1)

    logging.info('Envio concluído.')
    writer.close()
    await writer.wait_closed()


async def start_client():
    args = parse_arguments()
    reader, writer = await asyncio.open_connection(args.host, args.port)

    # Negociar protocolo
    writer.write(args.protocol.encode())
    await writer.drain()
    selected_protocol = (await reader.read(3)).decode()
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

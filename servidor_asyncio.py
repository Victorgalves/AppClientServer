import asyncio
import argparse
import logging
import datetime
import random
from logging.handlers import RotatingFileHandler
from my_protocol import create_packet, unpack_packet, calculate_checksum

# Configurações do servidor
HOST = '0.0.0.0'
PORT = 5001
MAX_RECV_WINDOW_SIZE = 5
LOG_FILE = 'server.log'

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
    parser = argparse.ArgumentParser(description='Servidor de transporte confiável (Asyncio)')
    parser.add_argument('--host', default=HOST, help='Endereço IP do servidor')
    parser.add_argument('--port', type=int, default=PORT, help='Porta do servidor')
    parser.add_argument('--window', type=int, default=MAX_RECV_WINDOW_SIZE, help='Tamanho da janela de recepção')
    parser.add_argument('--protocol', choices=['GBN', 'SR'], default='SR', help='Protocolo a ser utilizado')
    parser.add_argument('--simulate_ack_loss', action='store_true', help='Simular perda de ACKs')
    parser.add_argument('--lost_acks', nargs='*', type=int, default=[], help='Seqs dos ACKs a serem perdidos')
    parser.add_argument('--simulate_ack_error', action='store_true', help='Simular erro em ACKs')
    parser.add_argument('--error_acks', nargs='*', type=int, default=[], help='Seqs dos ACKs com erro')
    parser.add_argument('--simulate_window_update', action='store_true', help='Simular atualização dinâmica da janela')
    return parser.parse_args()


async def handle_client(reader, writer, args):
    addr = writer.get_extra_info('peername')
    logging.info(f'Conexão estabelecida com {addr}')
    try:
        # Negociar protocolo
        protocol = (await reader.read(3)).decode().strip()
        selected_protocol = args.protocol if protocol in ['GBN', 'SR'] else 'SR'
        logging.info(f'Protocolo negociado: {selected_protocol}')
        writer.write(selected_protocol.ljust(3).encode())
        await writer.drain()

        # Enviar tamanho da janela de recepção
        recv_window_size = args.window
        writer.write(recv_window_size.to_bytes(4, byteorder='big'))
        await writer.drain()

        expected_seq_num = 0
        recv_window = {}
        recv_base = 0

        while True:
            packet = await reader.read(4096)
            if not packet:
                break

            seq_num, ack_flag, nak_flag, recv_checksum, data = unpack_packet(packet)
            data_checksum = calculate_checksum(data)

            # Verificar checksum antes de decodificar os dados
            if recv_checksum != data_checksum:
                logging.warning(f'Erro de checksum no pacote {seq_num}.')
                # Enviar NAK apenas se o pacote estiver na janela
                if recv_base <= seq_num < recv_base + recv_window_size:
                    nak_packet = create_packet(seq_num, b'', ack=False, nak=True)
                    # Simular perda de NAK
                    if args.simulate_ack_loss and seq_num in args.lost_acks:
                        logging.info(f'Perdendo NAK para Seq={seq_num}')
                        # Não enviar NAK
                    else:
                        writer.write(nak_packet)
                        await writer.drain()
                        logging.info(f'Enviado NAK para Seq={seq_num}')
                else:
                    logging.info(f'Pacote {seq_num} com erro de checksum fora da janela. Ignorando.')
                continue

            try:
                data_str = data.decode()
            except UnicodeDecodeError as e:
                logging.error(f'Erro ao decodificar os dados do pacote {seq_num}: {e}')
                # Enviar NAK apenas se o pacote estiver na janela
                if recv_base <= seq_num < recv_base + recv_window_size:
                    nak_packet = create_packet(seq_num, b'', ack=False, nak=True)
                    writer.write(nak_packet)
                    await writer.drain()
                    logging.info(f'Enviado NAK para Seq={seq_num}')
                else:
                    logging.info(f'Pacote {seq_num} com erro de decodificação fora da janela. Ignorando.')
                continue

            logging.info(f'Recebido pacote Seq={seq_num}, Dados={data_str}')

            if selected_protocol == 'GBN':
                if seq_num == expected_seq_num:
                    # Processar o pacote e enviar ACK cumulativo
                    logging.info(f'Pacote {seq_num} recebido corretamente (GBN).')
                    expected_seq_num += 1

                    # Simular atualização da janela
                    if args.simulate_window_update and random.random() < 0.3:
                        recv_window_size = random.randint(1, args.window)
                        ack_data = recv_window_size.to_bytes(4, byteorder='big')
                        logging.info(f'Atualizando janela de recepção para {recv_window_size}')
                    else:
                        ack_data = b''

                    ack_packet = create_packet(expected_seq_num - 1, ack_data, ack=True)

                    # Simular perda ou erro de ACK
                    if args.simulate_ack_loss and seq_num in args.lost_acks:
                        logging.info(f'Perdendo ACK para Seq={seq_num}')
                        # Não enviar ACK
                    elif args.simulate_ack_error and seq_num in args.error_acks:
                        logging.info(f'Enviando ACK com erro para Seq={seq_num}')
                        ack_packet = create_packet(expected_seq_num - 1, ack_data, ack=True, checksum_error=True)
                        writer.write(ack_packet)
                        await writer.drain()
                    else:
                        writer.write(ack_packet)
                        await writer.drain()
                        logging.info(f'Enviado ACK cumulativo para Seq={expected_seq_num - 1}')
                else:
                    # Pacote fora de ordem, reenviar ACK para último pacote reconhecido
                    logging.warning(f'Pacote {seq_num} inesperado (GBN). Esperado: {expected_seq_num}')
                    ack_packet = create_packet(expected_seq_num - 1, b'', ack=True)
                    writer.write(ack_packet)
                    await writer.drain()
                    logging.info(f'Reenviado ACK cumulativo para Seq={expected_seq_num - 1}')
            elif selected_protocol == 'SR':
                if recv_base <= seq_num < recv_base + recv_window_size:
                    if seq_num not in recv_window:
                        recv_window[seq_num] = data_str
                        logging.info(f'Pacote {seq_num} armazenado na janela (SR).')

                        # Simular atualização da janela
                        if args.simulate_window_update and random.random() < 0.3:
                            recv_window_size = random.randint(1, args.window)
                            ack_data = recv_window_size.to_bytes(4, byteorder='big')
                            logging.info(f'Atualizando janela de recepção para {recv_window_size}')
                        else:
                            ack_data = b''

                        ack_packet = create_packet(seq_num, ack_data, ack=True)

                        # Simular perda ou erro de ACK
                        if args.simulate_ack_loss and seq_num in args.lost_acks:
                            logging.info(f'Perdendo ACK para Seq={seq_num}')
                            # Não enviar ACK
                        elif args.simulate_ack_error and seq_num in args.error_acks:
                            logging.info(f'Enviando ACK com erro para Seq={seq_num}')
                            ack_packet = create_packet(seq_num, ack_data, ack=True, checksum_error=True)
                            writer.write(ack_packet)
                            await writer.drain()
                        else:
                            writer.write(ack_packet)
                            await writer.drain()
                            logging.info(f'Enviado ACK para Seq={seq_num}')
                    else:
                        logging.info(f'Pacote {seq_num} já recebido. Reenviando ACK.')
                        ack_packet = create_packet(seq_num, b'', ack=True)
                        writer.write(ack_packet)
                        await writer.drain()
                        logging.info(f'Reenviado ACK para Seq={seq_num}')

                    # Atualizar recv_base
                    while recv_base in recv_window:
                        # Processar ou armazenar o dado conforme necessário
                        logging.info(f'Processando pacote {recv_base}')
                        del recv_window[recv_base]
                        recv_base += 1
                elif seq_num < recv_base:
                    logging.info(f'Pacote {seq_num} já processado. Reenviando ACK.')
                    ack_packet = create_packet(seq_num, b'', ack=True)
                    writer.write(ack_packet)
                    await writer.drain()
                    logging.info(f'Reenviado ACK para Seq={seq_num}')
                else:
                    logging.info(f'Pacote {seq_num} fora da janela de recepção futura. Ignorando.')
                    # Não enviar NAK para pacotes futuros
    except Exception as e:
        logging.error(f'Erro ao lidar com o cliente {addr}: {e}')
    finally:
        logging.info(f'Conexão encerrada com {addr}')
        writer.close()
        await writer.wait_closed()


async def start_server():
    args = parse_arguments()
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, args), args.host, args.port)
    addr = server.sockets[0].getsockname()
    logging.info(f'Servidor escutando em {addr}')

    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    # Adicionar separador no log
    logging.info('\n\n' + '=' * 50)
    logging.info(f'Iniciando nova execução do servidor em {datetime.datetime.now()}')
    logging.info('=' * 50 + '\n')
    asyncio.run(start_server())

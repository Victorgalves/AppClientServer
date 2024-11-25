import asyncio
import argparse
import logging
import sys
import datetime
from logging.handlers import RotatingFileHandler
from my_protocol import create_packet, unpack_packet, calculate_checksum

# Configurações do servidor
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5001
DEFAULT_WINDOW_SIZE = 5
DEFAULT_PROTOCOL = 'GBN'

# Configurar o logger com RotatingFileHandler e StreamHandler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler(
            'server.log', maxBytes=5*1024*1024, backupCount=5
        ),
        logging.StreamHandler(sys.stdout)
    ]
)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Servidor de transporte confiável (Asyncio)')
    parser.add_argument('--host', default=DEFAULT_HOST, help='Endereço IP para escutar')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Porta para escutar')
    parser.add_argument('--window', type=int, default=DEFAULT_WINDOW_SIZE, help='Tamanho da janela de recepção')
    parser.add_argument('--protocol', choices=['GBN', 'SR'], default=DEFAULT_PROTOCOL, help='Protocolo a ser utilizado')
    parser.add_argument('--simulate_ack_error', action='store_true', help='Simular erro em ACKs')
    parser.add_argument('--error_acks', nargs='*', type=int, default=[], help='Seqs dos ACKs a serem corrompidos')
    parser.add_argument('--simulate_window_update', action='store_true', help='Simular atualização da janela de recepção')
    parser.add_argument('--no_ack_packets', nargs='*', type=int, default=[], help='Seqs dos pacotes que não serão confirmados')
    parser.add_argument('--window_update_interval', type=int, default=10, help='Intervalo para atualizar a janela de recepção (em segundos)')
    parser.add_argument('--window_sizes', nargs='*', type=int, default=[5, 3, 7], help='Tamanhos da janela de recepção a serem usados em cada atualização')
    parser.add_argument('--ack_mode', choices=['individual', 'cumulative'], default='individual', help='Modo de confirmação: individual ou cumulativo')
    return parser.parse_args()

async def handle_client(reader, writer):
    args = parse_arguments()
    addr = writer.get_extra_info('peername')
    logging.info(f'Conexão estabelecida com {addr}')

    # Negociar protocolo
    protocol = (await reader.read(3)).decode().strip()
    writer.write(protocol.ljust(3).encode())
    await writer.drain()
    logging.info(f'Protocolo negociado: {protocol}')

    # Enviar tamanho da janela de recepção
    recv_window_size = args.window
    writer.write(recv_window_size.to_bytes(4, byteorder='big'))
    await writer.drain()

    expected_seq_num = 0
    received_packets = {}
    window_update_times = [asyncio.get_event_loop().time() + i * args.window_update_interval for i in range(len(args.window_sizes))]
    window_index = 0

    while True:
        try:
            data = await reader.read(4096)
            if not data:
                break

            # Simular atraso (para testar envio em lote)
            await asyncio.sleep(2)  # Atraso de 2 segundos

            seq_num, ack_flag, nak_flag, checksum, payload = unpack_packet(data)

            calc_checksum = calculate_checksum(payload)
            if checksum != calc_checksum:
                logging.warning(f'Erro de checksum no pacote {seq_num}.')
                if args.simulate_ack_error and seq_num in args.error_acks:
                    logging.info(f'Enviando NAK com erro para Seq={seq_num}')
                    nak_packet = create_packet(seq_num, recv_window_size.to_bytes(4, byteorder='big'), nak=True, corrupt_ack=True)
                else:
                    logging.info(f'Enviando NAK para Seq={seq_num}')
                    nak_packet = create_packet(seq_num, recv_window_size.to_bytes(4, byteorder='big'), nak=True)
                writer.write(nak_packet)
                await writer.drain()
                continue

            logging.info(f'Recebido pacote Seq={seq_num}, Dados={payload.decode()}')

            # Verificar se o pacote não deve ser confirmado
            if seq_num in args.no_ack_packets:
                logging.info(f'Não enviando ACK para Seq={seq_num} (simulando perda de ACK)')
                continue

            # Atualizar a janela de recepção dinamicamente
            current_time = asyncio.get_event_loop().time()
            if window_index < len(window_update_times) and current_time >= window_update_times[window_index]:
                recv_window_size = args.window_sizes[window_index]
                logging.info(f'Atualizando janela de recepção para {recv_window_size}')
                window_index += 1

            if protocol == 'GBN':
                if seq_num == expected_seq_num:
                    # Processar pacote
                    logging.info(f'Processando pacote {seq_num}')
                    expected_seq_num += 1
                else:
                    logging.info(f'Pacote fora de ordem. Esperado: {expected_seq_num}')
                    # No GBN, descarta o pacote e envia ACK do último pacote em ordem
                if args.simulate_ack_error and seq_num in args.error_acks:
                    logging.info(f'Enviando ACK com erro para Seq={seq_num}')
                    ack_packet = create_packet(seq_num, recv_window_size.to_bytes(4, byteorder='big'), ack=True, corrupt_ack=True)
                else:
                    if args.ack_mode == 'individual':
                        logging.info(f'Enviando ACK para Seq={seq_num}')
                        ack_packet = create_packet(seq_num, recv_window_size.to_bytes(4, byteorder='big'), ack=True)
                    elif args.ack_mode == 'cumulative':
                        ack_seq_num = expected_seq_num - 1
                        logging.info(f'Enviando ACK cumulativo para Seq={ack_seq_num}')
                        ack_packet = create_packet(ack_seq_num, recv_window_size.to_bytes(4, byteorder='big'), ack=True)
                writer.write(ack_packet)
                await writer.drain()
            elif protocol == 'SR':
                if seq_num not in received_packets:
                    received_packets[seq_num] = payload
                    logging.info(f'Pacote {seq_num} armazenado na janela (SR).')
                    # Processar pacote
                    logging.info(f'Processando pacote {seq_num}')
                if args.simulate_ack_error and seq_num in args.error_acks:
                    logging.info(f'Enviando ACK com erro para Seq={seq_num}')
                    ack_packet = create_packet(seq_num, recv_window_size.to_bytes(4, byteorder='big'), ack=True, corrupt_ack=True)
                else:
                    if args.ack_mode == 'individual':
                        logging.info(f'Enviando ACK para Seq={seq_num}')
                        ack_packet = create_packet(seq_num, recv_window_size.to_bytes(4, byteorder='big'), ack=True)
                    elif args.ack_mode == 'cumulative':
                        ack_seq_num = max(received_packets.keys())
                        logging.info(f'Enviando ACK cumulativo para Seq={ack_seq_num}')
                        ack_packet = create_packet(ack_seq_num, recv_window_size.to_bytes(4, byteorder='big'), ack=True)
                writer.write(ack_packet)
                await writer.drain()
        except Exception as e:
            logging.error(f'Erro ao processar o pacote: {e}')
            break

    logging.info(f'Conexão encerrada com {addr}')
    writer.close()
    await writer.wait_closed()

async def start_server():
    args = parse_arguments()
    server = await asyncio.start_server(handle_client, args.host, args.port)
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
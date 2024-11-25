# my_protocol.py

import struct

# Definição dos flags
FLAG_ACK = 1
FLAG_NAK = 2

def calculate_checksum(data):
    """
    Calcula um checksum simples somando os valores dos bytes.
    """
    checksum = 0
    for byte in data:
        checksum += byte
    return checksum & 0xFFFF  # Retorna os últimos 16 bits

def create_packet(seq_num, data, ack=False, nak=False, corrupt_ack=False):
    """
    Cria um pacote com a seguinte estrutura:
    - Sequência (4 bytes, big endian)
    - Flags (1 byte)
    - Checksum (2 bytes, big endian)
    - Dados (variável)
    """
    flags = 0
    if ack:
        flags |= FLAG_ACK
    if nak:
        flags |= FLAG_NAK

    # Calcular checksum sobre os dados
    checksum = calculate_checksum(data)

    # Se for para corromper o ACK/NAK, inverte os bits do checksum
    if corrupt_ack:
        checksum = ~checksum & 0xFFFF

    # Estrutura do pacote: sequencia (4), flags (1), checksum (2), dados
    packet = struct.pack('>I', seq_num)  # 4 bytes para a sequência
    packet += struct.pack('B', flags)    # 1 byte para flags
    packet += struct.pack('>H', checksum)  # 2 bytes para checksum
    packet += data  # Dados

    return packet

def unpack_packet(packet):
    """
    Descompacta um pacote e retorna:
    - Sequência (int)
    - ACK flag (bool)
    - NAK flag (bool)
    - Checksum recebido (int)
    - Dados (bytes)
    """
    if len(packet) < 7:
        raise ValueError("Pacote muito curto para desempacotar.")

    seq_num = struct.unpack('>I', packet[0:4])[0]
    flags = struct.unpack('B', packet[4:5])[0]
    checksum = struct.unpack('>H', packet[5:7])[0]
    data = packet[7:]

    ack_flag = bool(flags & FLAG_ACK)
    nak_flag = bool(flags & FLAG_NAK)

    return seq_num, ack_flag, nak_flag, checksum, data
import struct

def calculate_checksum(data):
    checksum = sum(data) % 65535
    return checksum.to_bytes(2, byteorder='big')

def create_packet(seq_num, data, ack=False, nak=False, checksum_error=False):
    flags = 0
    if ack:
        flags |= 1  # Bit 0
    if nak:
        flags |= 2  # Bit 1
    if checksum_error:
        flags |= 4  # Bit 2

    seq_num_bytes = struct.pack('!I', seq_num)  # 4 bytes
    flags_bytes = struct.pack('!B', flags)      # 1 byte
    data_length = struct.pack('!I', len(data))  # 4 bytes
    checksum = calculate_checksum(data)

    if checksum_error:
        # Introduzir erro no checksum
        checksum = b'\x00\x00'

    packet = seq_num_bytes + flags_bytes + checksum + data_length + data
    return packet

def unpack_packet(packet):
    if len(packet) < 11:
        raise ValueError("Pacote muito curto para desempacotar.")

    seq_num = struct.unpack('!I', packet[0:4])[0]
    flags = struct.unpack('!B', packet[4:5])[0]
    checksum = packet[5:7]
    data_length = struct.unpack('!I', packet[7:11])[0]
    data = packet[11:11+data_length]

    ack_flag = bool(flags & 1)
    nak_flag = bool(flags & 2)
    checksum_error = bool(flags & 4)

    return seq_num, ack_flag, nak_flag, checksum, data

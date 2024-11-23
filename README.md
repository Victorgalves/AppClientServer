# AppClientServer

Go-Back-N (GBN)

Servidor:

python servidor_asyncio.py --port 5001 --protocol GBN --simulate_ack_loss --lost_acks 4 12 --simulate_ack_loss --lost_acks 4 12


Cliente:

python cliente_asyncio.py --host 127.0.0.1 --port 5001 --protocol GB --window 5 --packets 20 --simulate_data_error --error_packets 4 12 --mode batch

Selective Repeat (SR)

Servidor:

python servidor_asyncio.py --port 5001 --protocol SR --simulate_ack_loss --lost_acks 4 12 --simulate_ack_error --error_acks 7 15 --simulate_window_update


Cliente:

python cliente_asyncio.py --host 127.0.0.1 --port 5001 --protocol SR --window 5 --packets 20 --simulate_data_error --error_packets 4 12 --mode batch

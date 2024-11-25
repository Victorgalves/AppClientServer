
# **AppClientServer**

## **Requisitos do Projeto**

### **Sobre o Cliente**

- **Deve ser possível enviar 1 único pacote ou vários em rajada:**  
  ✅ *Atendido.* O código permite escolher entre os modos `single` (envio único) ou `batch` (rajada).

- **Deve ser possível incluir erros de integridade em pacotes específicos:**  
  ✅ *Atendido.* A função `corrupt_data_if_needed` no cliente verifica os pacotes indicados no argumento `--error_packets` e corrompe os dados, se necessário.

- **A janela de recepção do servidor deve ser considerada e atualizada dinamicamente:**  
  ✅ *Atendido.* O cliente lê e utiliza os tamanhos de janela enviados pelo servidor (`recv_window_size`) e atualiza dinamicamente conforme mensagens recebidas.

- **A janela de congestionamento deve ser atualizada de acordo com as perdas de pacotes e as confirmações duplicadas percebidas:**  
  ✅ *Atendido.* O código implementa a atualização da janela de congestionamento (`congestion_window`) com modos **Slow Start** e **Congestion Avoidance**, além de reagir a **timeouts** e **ACKs duplicados**.

---

### **Sobre o Servidor**

- **Deve ser possível marcar pacotes que não serão confirmados:**  
  ✅ *Atendido.* O argumento `--no_ack_packets` permite indicar pacotes que não receberão ACK, simulando perdas.

- **Deve ser possível incluir erros de integridade nas confirmações enviadas:**  
  ✅ *Atendido.* A lógica do servidor permite simular confirmações corrompidas para pacotes específicos usando o argumento `--error_acks`.

- **Deve ser possível sinalizar para o cliente confirmações negativas:**  
  ✅ *Atendido.* O servidor verifica a integridade dos pacotes recebidos e, ao detectar erros de checksum, envia **NAKs** ao cliente.

- **Deve ser possível negociar com o cliente se será utilizada a repetição seletiva ou o Go-Back-N:**  
  ✅ *Atendido.* O protocolo é negociado na conexão inicial, com suporte a **GBN** ou **SR**.

- **A janela de recepção deve ser informada ao cliente e atualizada dinamicamente:**  
  ✅ *Atendido.* O servidor envia o tamanho inicial da janela ao cliente e atualiza dinamicamente conforme configurado.

---

### **Pontuação Extra (checagem de integridade)**

✅ *Atendido.* A implementação possui métodos de checagem de integridade no envio e recebimento de pacotes (**checksum**).

---

## **Como Executar o Projeto**

### **Passos Iniciais**
1. Clone o projeto em sua máquina:  
   ```bash
   git clone <URL_DO_REPOSITORIO>
   ```
2. É necessário ter o **Python 3** ou superior instalado.
3. Acesse o diretório do projeto:  
   ```bash
   cd <NOME_DO_DIRETORIO>
   ```

---

### **Execução com Menu Interativo**
1. Abra dois terminais: um para o **servidor** e outro para o **cliente**.
2. No terminal do servidor, execute:  
   ```bash
   python menu.py
   ```
3. No terminal do cliente, execute:  
   ```bash
   python menu.py
   ```
4. Siga as opções apresentadas no menu do cliente.

---

### **Execução via Linha de Comando**

#### **Go-Back-N (GBN):**
- **Servidor:**  
  ```bash
  python servidor.py
  ```
- **Servidor (Simulação de Erros em ACKs):**  
  ```bash
  python servidor.py --simulate_ack_error --error_acks 2
  ```
- **Cliente (Rajada - Padrão):**  
  ```bash
  python cliente.py
  ```
- **Cliente (Envio Único):**  
  ```bash
  python cliente.py --mode single
  ```

#### **Selective Repeat (SR):**
- **Servidor:**  
  ```bash
  python servidor.py --protocol SR
  ```
- **Servidor (Simulação de Erros em ACKs):**  
  ```bash
  python servidor.py --protocol SR --simulate_ack_error --error_acks 2
  ```
- **Cliente (Rajada - Padrão):**  
  ```bash
  python cliente.py --protocol SR
  ```
- **Cliente (Envio Único):**  
  ```bash
  python cliente.py --protocol SR --mode single
  ```

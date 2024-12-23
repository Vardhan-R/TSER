from cryptography.fernet import Fernet
import random
import rsa
import selectors
import socket
import sys
import time
import types

class TSERPath:
    def __init__(self, recipient: str, intermediate_nodes: list[str], public_keys: list[rsa.PublicKey]) -> None:
        self.recipient = recipient
        self.intermediate_nodes = intermediate_nodes
        self.public_keys = public_keys

        self.n_i_nodes = len(self.intermediate_nodes)

    def genInitData(self) -> bytes:
        self.sym_keys = [Fernet.generate_key() for _ in range(self.n_i_nodes)]

        next_nodes = [self.recipient] + self.intermediate_nodes[:0:-1]
        data = b""
        for recipient, sym_key, public_key in zip(next_nodes, self.sym_keys[::-1], self.public_keys[::-1]):
            msg = f"{sym_key} {recipient} ".encode() + data
            ctx = rsa.encrypt(msg, public_key)
            data = b"TSER " + ctx

        return data

    def initPath(self, selector: selectors.DefaultSelector):
        startConnection(selector, lineToAddress(intermediate_nodes[0]), 1)

    def wrapMessage(self, message: str) -> bytes:
        # content = message
        # for recipient in self.intermediate_nodes:
        #     content = str(recipient, content).encode()
        return b""

def choose(lst: list):
    """
    Chooses an element at random, and returns it.
    """

    return random.choice(lst)

def decryptData(data: bytes, private_key: rsa.PrivateKey) -> str:
    if data[-5:] != b" TSER":
        raise Exception(f"TSER footer not found in {data}")

    try:
        response = ""
        data = data[:-5]
        while data:
            response += rsa.decrypt(data[:256], private_key).decode()
            data = data[256:]
    except rsa.DecryptionError:
        raise Exception("Error during decryption")

    return response

def framePathRequest(recipient: str) -> bytes:
    path_request = f"Contact {recipient}"
    return path_request.encode()

def lineToAddress(line: str) -> tuple[str, int]:
    host, port = line.strip().split(':')
    port = int(port)
    return host, port

def startConnection(selector: selectors.DefaultSelector, recipient_address, connection_id):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(recipient_address)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    data = types.SimpleNamespace(
        connid=connection_id,
        # msg_total=sum(len(m) for m in messages),
        recv_total=0,
        # messages=messages.copy(),
        outb=b"",
    )
    selector.register(sock, events, data=data)

    return True

self_listen_host = sys.argv[1]
self_listen_port = int(sys.argv[2])

# Get the trusted servers' addresses
with open("./trusted_servers.txt", 'r') as fp:
    raw_lines = fp.readlines()

trusted_addrs = list(map(lineToAddress, raw_lines))

# Pick a trusted server
t_server: tuple[str, int] = choose(trusted_addrs)

self_public_key, self_private_key = rsa.newkeys(2048)

# sel = selectors.DefaultSelector()

# # For listening (to communicate with other clients)
# lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# lsock.bind((self_listen_host, self_listen_port))
# lsock.listen()
# print(f"Listening on {(self_listen_host, self_listen_port)}")
# lsock.setblocking(False)
# sel.register(lsock, selectors.EVENT_READ, data=None)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    # # Choose address of client
    # s.bind((self_host, self_port))
    print((self_listen_host, self_listen_port))

    # Connect to the chosen trusted server
    s.connect((t_server[0], t_server[1]))
    print("Connected to the trusted server", (t_server[0], t_server[1]))

    # Send the listening address and the public key
    while True:
        s.sendall(f"Sharing_basic_info {self_listen_host}:{self_listen_port} {self_public_key.n} {self_public_key.e}".encode())
        data = s.recv(4096)
        response = decryptData(data, self_private_key)
        if response == "Received basic info":
            break
        print(f"Incorrect data received: {data}")
        print(f"Decoded as: {response}")
        time.sleep(1)

    while (recipient := input('Who do you want to contact? ')) != "exit":
        s.sendall(framePathRequest(recipient))

        data = s.recv(4096)
        response = decryptData(data, self_private_key)
        print(response)

        if response not in ("Address not found", "No intermediate nodes", "Error while generating reponse"):
            # Create the path
            lft, rgt = response.split('|')
            intermediate_nodes = lft.split(' ')
            public_keys = [rsa.PublicKey(*map(int, s.split(','))) for s in rgt.split(' ')]
            path = TSERPath(recipient, intermediate_nodes, public_keys)
            print("Path registered")

            break   # To do: replace with a multi-threaded solution

# sel = selectors.DefaultSelector()

# sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# sock.bind((self_host, self_port))
# print((self_host, self_port))
# sock.setblocking(False)
# sock.connect((t_server[0], t_server[1]))
# sel.register(sock, selectors.EVENT_READ, data=None)

# try:
#     while True:
#         events = sel.select(timeout=-1) # timeout <= 0 ==> non-blocking
#         for key, mask in events:
#             if key.data is None:
#                 acceptWrapper(key.fileobj)
#             else:
#                 serviceConnection(key, mask)
# except KeyboardInterrupt:
#     print("Caught keyboard interrupt, exiting...")
# finally:
#     sel.close()

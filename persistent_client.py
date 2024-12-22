import socket
import time

HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = 60001  # The port used by the server

msgs = [f"message {i}" for i in range(1, 10)]

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    for msg in msgs:
        s.sendall(msg.encode())
        data = s.recv(1024)
        print(f"Received {data!r}")
        time.sleep(1)

print("Connection closed from client's side")
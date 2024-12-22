import selectors
import socket
import sys
import time
import types

HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 65432  # Port to listen on (non-privileged ports are > 1023)

def acceptWrapper(sock: socket.socket):
    conn, addr = sock.accept()  # Should be ready to read
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data=data)

def generateResponse(recv_data: bytes) -> bytes:
    msg = recv_data.decode()
    response = msg.encode()
    return response

def serviceConnection(key: selectors.SelectorKey, mask):
    sock: socket.socket = key.fileobj
    data = key.data
    if mask & selectors.EVENT_READ:
        recv_data = sock.recv(1024)  # Should be ready to read
        if recv_data:
            data.outb += generateResponse(recv_data)
        else:
            print(f"Closing connection to {data.addr}")
            sel.unregister(sock)
            sock.close()
    if mask & selectors.EVENT_WRITE:
        if data.outb:
            print(f"Echoing {data.outb!r} to {data.addr}")
            time.sleep(1)
            sent = sock.send(data.outb)  # Should be ready to write
            data.outb = data.outb[sent:]

sel = selectors.DefaultSelector()

# host, port = sys.argv[1], int(sys.argv[2])
host, port = HOST, PORT
lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((host, port))
lsock.listen()
print(f"Listening on {(host, port)}")
lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)

try:
    while True:
        events = sel.select(timeout=-1) # timeout <= 0 ==> non-blocking
        for key, mask in events:
            if key.data is None:
                acceptWrapper(key.fileobj)
            else:
                serviceConnection(key, mask)
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()

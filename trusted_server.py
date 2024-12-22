from pubnub.callbacks import SubscribeCallback
from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub
import numpy
import os
import rsa
import selectors
import socket
import sys
import time
import types

class MySubscribeCallback(SubscribeCallback):
    def presence(self, pubnub, presence):
        pass

    def status(self, pubnub, status):
        pass

    def message(self, pubnub, message):
        if message.publisher == pnconfig.user_id:
            return

        msg: str = message.message
        msg_lst = msg.split(' ')
        match msg_lst[0]:   # Action/Command
            case "Joined":
                all_clients[msg_lst[1]] = None  # Store it as a string
            case "Left":
                all_clients.pop(msg_lst[1])
            case "New_path":
                ...
            case "Sharing_public_key":
                sender = msg_lst[1]
                public_key = rsa.PublicKey(*map(int, msg_lst[2:]))
                all_clients[sender] = public_key
        print(f"Trusted server {message.publisher}: {msg[:50]}")

def acceptWrapper(sock: socket.socket):
    conn, addr = sock.accept()  # Should be ready to read
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data=data)

    return addr

def addressToLine(address: tuple[str, int]) -> str:
    return f"{address[0]}:{address[1]}"

def choose(collection: set, max_count: int, but: set):
    """
    Chooses elements at random, and returns them.
    """

    rem = list(collection - but)
    count = min(len(rem), max_count)
    try:
        return numpy.random.choice(rem, count, False)
    except ValueError:  # if len(rem) == 0
        return []

def generatePublishMessage(info: dict[str]) -> str | None:
    msg_to_publish = None

    match info["action"]:
        case "Joined":  # Client joined
            client_host, client_port = info["sender"]
            msg_to_publish = f"Joined {client_host}:{client_port}"
        case "Left":    # Client left
            client_host, client_port = info["sender"]
            msg_to_publish = f"Left {client_host}:{client_port}"

    match info["command"]:
        case "Contact": # Client tried to contact another client
            if info["response"] not in (b"Address not found", b"No intermediate nodes"):
                sender = info["sender"]
                chosen_intermediate_nodes = info["response"].decode()
                recipient = info["recipient"]
                msg_to_publish = f"New_path {sender} {chosen_intermediate_nodes} {recipient}"
        case "Sharing_public_key":  # Client's public key
            sender = info["sender"]
            public_key: rsa.PublicKey = info["public key"]
            msg_to_publish = f"Sharing_public_key {sender} {public_key.n} {public_key.e}"

    return msg_to_publish

def generateResponse(recv_data: bytes, sender: str) -> dict[str]:
    ret = {"command": None, "response": None}

    msg = recv_data.decode()
    msg_lst = msg.split(' ')

    try:
        ret["command"] = msg_lst[0]
        match ret["command"]:
            case "Contact":
                ret["recipient"] = msg_lst[1]   # As a string
                all_client_addrs = all_clients.keys()
                if ret["recipient"] in all_client_addrs:
                    intermediate_nodes = set(all_client_addrs)
                    print(intermediate_nodes)
                    chosen_intermediate_nodes = choose(intermediate_nodes, 3, {sender, ret["recipient"]})  # Choose at most 3 intermediate nodes
                    if len(chosen_intermediate_nodes) == 0: # No intermediate nodes
                        ret["response"] = b"No intermediate nodes"
                    else:
                        public_keys = [f"{all_clients[node].n},{all_clients[node].e}" for node in chosen_intermediate_nodes]
                        ret["response"] = f"{' '.join(chosen_intermediate_nodes)}|{' '.join(public_keys)}".encode()
                else:   # Address not found
                    ret["response"] = b"Address not found"
            case "Sharing_public_key":  # "Sharing_public_key {n} {e}"
                public_key = rsa.PublicKey(*map(int, msg_lst[1:]))
                all_clients[sender] = public_key
                ret["public key"] = public_key
                ret["response"] = b"Received public key"
            case _:
                ret["response"] = f"Command not found: {ret["command"]}".encode()
    except Exception as e:
        ret["response"] = str(e).encode()

    return ret

def lineToAddress(line: str) -> tuple[str, int]:
    host, port = line.strip().split(':')
    port = int(port)
    return host, port

def myPublishCallback(envelope, status) -> None:
    # Check whether request successfully completed or not
    if not status.is_error():
        pass

def publish(pubnub: PubNub, channel: str, message: str, publish_callback_function) -> None:
    pubnub.publish().channel(channel).message(message).pn_async(publish_callback_function)

def serviceConnection(key: selectors.SelectorKey, mask) -> dict[str]:
    ret = {"action": None, "command": None, "sender": None, "response": None}

    sock: socket.socket = key.fileobj
    data = key.data
    ret["sender"] = addressToLine(data.addr)

    if mask & selectors.EVENT_READ:
        recv_data = sock.recv(1024)  # Should be ready to read
        if recv_data:
            res = generateResponse(recv_data, ret["sender"])
            ret["command"] = res["command"]
            ret["response"] = res["response"]
            data.outb += ret["response"]

            match ret["command"]:
                case "Contact":
                    ret["recipient"] = res["recipient"]
                case "Sharing_public_key":
                    ret["public key"] = res["public key"]
        else:
            print(f"Closing connection to {data.addr}")
            sel.unregister(sock)
            sock.close()
            ret["action"] = "Left"

    if mask & selectors.EVENT_WRITE:
        if data.outb:
            print(f"Sending {data.outb!r} to {data.addr}")
            time.sleep(1)
            sent = sock.send(data.outb)  # Should be ready to write
            data.outb = data.outb[sent:]

    return ret

with open("./trusted_servers.txt", 'r') as fp:
    raw_lines = fp.readlines()

trusted_addrs = list(map(lineToAddress, raw_lines))
t_server_idx = int(sys.argv[1])
self_host, self_port = trusted_addrs[t_server_idx]

other_t_servers = trusted_addrs.pop(t_server_idx)

all_clients = {}    # {address_as_string: public_key}

sel = selectors.DefaultSelector()

lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((self_host, self_port))
lsock.listen()
print(f"Listening on {(self_host, self_port)}")
lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)

pnconfig = PNConfiguration()
pnconfig.publish_key = 'demo'
pnconfig.subscribe_key = 'demo'
pnconfig.user_id = sys.argv[1]
pnconfig.ssl = True
pubnub = PubNub(pnconfig)

pubnub.add_listener(MySubscribeCallback())
channel = "chan-1"
pubnub.subscribe().channels("chan-1").execute()

try:
    while True:
        # Client stuff
        events = sel.select(timeout=-1) # timeout <= 0 ==> non-blocking
        for key, mask in events:
            if key.data is None:
                client_addr = acceptWrapper(key.fileobj)
                all_clients[addressToLine(client_addr)] = None  # Store the client info as a string, and set the public key to `None` for now
                msg_to_publish = generatePublishMessage({"action": "Joined", "command": None, "sender": client_addr})
                publish(pubnub, channel, msg_to_publish, myPublishCallback)
            else:
                res = serviceConnection(key, mask)
                msg_to_publish = generatePublishMessage(res)
                if msg_to_publish:
                    publish(pubnub, channel, msg_to_publish, myPublishCallback)

        # # Other server stuff
        # time.sleep(0.1)
        # msg = f"This is a test message ({i})."
        # pubnub.publish().channel("chan-1").message(msg).pn_async(myPublishCallback)
        # i += 1
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting...")
except Exception as e:
    print(e)
finally:
    lsock.close()
    sel.close()
    os._exit(1)

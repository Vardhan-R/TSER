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
                if msg_lst[1] not in all_clients.keys():
                    all_clients[msg_lst[1]] = None  # Store it as a string
            case "Left":
                try:
                    all_clients.pop(msg_lst[1])
                except KeyError:
                    pass
            case "New_path":
                ...
            case "Sharing_basic_info":
                sender = msg_lst[1]
                client_listen_addr = msg_lst[2]
                public_key = rsa.PublicKey(*map(int, msg_lst[3:]))
                all_clients[sender] = types.SimpleNamespace(listen_addr=client_listen_addr, public_key=public_key)
        print(f"Trusted server {message.publisher}: {msg[:100]}")

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

def encryptData(data: bytes, public_key: rsa.PublicKey) -> bytes:
    """
    Encrypts the data using the public key and adds the TSER footer.
    """

    ciphertext = b""

    # Encrypt
    while data:
        ciphertext += rsa.encrypt(data[:245], public_key)
        data = data[245:]

    # Add the TSER footer
    ciphertext += b" TSER"

    return ciphertext

def generatePublishMessage(info: dict[str]) -> str | None:
    msg_to_publish = None

    match info["action"]:
        case "Joined":  # Client joined
            msg_to_publish = f"Joined {info["sender"]}"
        case "Left":    # Client left
            msg_to_publish = f"Left {info["sender"]}"

    match info["command"]:
        case "Contact": # Client tried to contact another client
            if info["response"] not in (b"Address not found", b"No intermediate nodes", b"Error while generating reponse"):
                sender = info["sender"]
                response = info["response"].decode()
                chosen_i_nodes_str, _ = response.split('|')
                recipient = info["recipient"]
                msg_to_publish = f"New_path {sender} {chosen_i_nodes_str} {recipient}"
                print(msg_to_publish)
        case "Sharing_basic_info":  # Client's listening address and public key
            sender = info["sender"]
            listen_addr = info["listening address"]
            public_key: rsa.PublicKey = info["public key"]
            msg_to_publish = f"Sharing_basic_info {sender} {listen_addr} {public_key.n} {public_key.e}"

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
                for k, v in all_clients.items():
                    if v is not None:
                        if ret["recipient"] == v.listen_addr:
                            recipient_comm_addr = k
                            intermediate_nodes = {k for k in all_clients.keys() if all_clients[k] is not None}
                            # intermediate_nodes = set(all_client_addrs)
                            # print(intermediate_nodes)
                            chosen_intermediate_nodes = choose(intermediate_nodes, 3, {sender, recipient_comm_addr})    # Choose at most 3 intermediate nodes
                            if len(chosen_intermediate_nodes) == 0: # No intermediate nodes
                                ret["response"] = b"No intermediate nodes"
                            else:
                                i_nodes_listen_addrs = [all_clients[node].listen_addr for node in chosen_intermediate_nodes]
                                public_keys = [f"{all_clients[node].public_key.n},{all_clients[node].public_key.e}" for node in chosen_intermediate_nodes]
                                ret["response"] = f"{' '.join(i_nodes_listen_addrs)}|{' '.join(public_keys)}".encode()
                            break
                else:   # Address not found
                    ret["response"] = b"Address not found"
            case "Sharing_basic_info":  # "Sharing_basic_info {listen_host}:{listen_port} {n} {e}"
                ret["listening address"] = msg_lst[1]
                public_key = rsa.PublicKey(*map(int, msg_lst[2:]))
                all_clients[sender] = types.SimpleNamespace(listen_addr=msg_lst[1], public_key=public_key)
                # print("Here:", all_clients[sender])
                ret["public key"] = public_key
                ret["response"] = b"Received basic info"
            case _:
                ret["response"] = f"Command not found: {ret["command"]}".encode()
    except Exception as e:
        print("Exception here:", e)
        # ret["response"] = str(e).encode()
        ret["response"] = b"Error while generating reponse"

    print('ret["response"]:', ret["response"])
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

            # Try to encrypt the response to be sent
            if all_clients[ret["sender"]] is None:  # The client's basic info is set to `None`
                data.outb += ret["response"] + b" TSER"
            else:   # The client's basic info is known
                data.outb += encryptData(ret["response"], all_clients[ret["sender"]].public_key)

            match ret["command"]:
                case "Contact":
                    ret["recipient"] = res["recipient"]
                case "Sharing_basic_info":
                    ret["listening address"] = res["listening address"]
                    ret["public key"] = res["public key"]
        else:
            print(f"Closing connection to {data.addr}")
            sel.unregister(sock)
            sock.close()
            ret["action"] = "Left"

    if mask & selectors.EVENT_WRITE:
        if data.outb:
            # print(f"Sending {data.outb!r} to {data.addr}")
            print(f"Sending msg to {data.addr}")
            # time.sleep(1)
            sock.sendall(data.outb)
            data.outb = b""
            # try:
            #     sent = sock.send(data.outb)  # Should be ready to write
            #     data.outb = data.outb[sent:]
            # except Exception as e:
            #     data.outb = b""
            #     print(type(e))
            #     print(e)

    return ret

with open("./trusted_servers.txt", 'r') as fp:
    raw_lines = fp.readlines()

trusted_addrs = list(map(lineToAddress, raw_lines))
t_server_idx = int(sys.argv[1])
self_host, self_port = trusted_addrs[t_server_idx]

other_t_servers = trusted_addrs.pop(t_server_idx)

all_clients = {}    # {address_as_string: types.SimpleNamespace(listen_addr, public_key)}

sel = selectors.DefaultSelector()

lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((self_host, self_port))
lsock.listen()
print(f"Listening on {(self_host, self_port)}")
lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)

pnconfig = PNConfiguration()
pnconfig.publish_key = "demo"
pnconfig.subscribe_key = "demo"
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
                sender = addressToLine(client_addr)
                all_clients[sender] = None  # Store the client info as a string, and set the public key to `None` for now
                msg_to_publish = generatePublishMessage({"action": "Joined", "command": None, "sender": sender})
                publish(pubnub, channel, msg_to_publish, myPublishCallback)
            else:
                res = serviceConnection(key, mask)
                msg_to_publish = generatePublishMessage(res)
                if msg_to_publish:
                    try:
                        publish(pubnub, channel, msg_to_publish, myPublishCallback)
                    except Exception as e:
                        print("Not publishing")
                        print(type(e))
                        print(e)

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

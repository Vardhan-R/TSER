# The Shallot Encryption Routing (TSER)

The Shallot Encryption Routing is an attempt at creating a software similar to [Tor](https://www.torproject.org) (albeit really _really_ badly).

## To Do

### `trusted_server.py`
- while returning a list of intermediate nodes, the trusted server must encrypt the message with the client's public key and add the TSER header
- the trusted server must also send `n_i_nodes` unique codes across to uniquely identify the path

### `TSER_client.py`
- keep one address to listen in
- a second address is used to communicate with a trusted server
- right after joining, send both these addresses and the public key to the trusted server
- use new addresses to contact other nodes on the network

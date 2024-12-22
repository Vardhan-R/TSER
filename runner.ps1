# Start the 3 trusted servers
for ($server_idx = 0; $server_idx -lt 3; $server_idx++) {
    # Start-Process cmd -ArgumentList "/c py trusted_server.py $server_idx"
    Start-Process powershell -ArgumentList "-noexit", "/c py trusted_server.py $server_idx"
}

# Give some time for the servers to subscribe and start listening
Start-Sleep -Seconds 3

# Start the clients
$n_clients = [int]$args[0]
$client_ports = 65000..65100
for ($i = 0; $i -lt $n_clients; $i++) {
    $client_port = $client_ports[$i]
    Start-Process cmd -ArgumentList "/c py TSER_client.py 127.0.0.1 $client_port"
    # Start-Process powershell -ArgumentList "-noexit", "/c py TSER_client.py 127.0.0.1 $client_port"
}

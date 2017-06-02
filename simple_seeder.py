import torrent, socket, pwp


def handle_incoming(conn, my_peer_id):

  print('Entering thread for {}'.format(':'.join(conn.getpeername())))

  # State of this peer
  am_choking = 1
  am_interested = 0
  peer_choking = 1
  peer_interested = 0

  try:
    d = pwp.receive_infohash(conn)
  except e:
    return

  # Check that we have the file specified by the infohash

  # Send our handshake
  pwp.send_handshake_reply(conn, d['info_hash'], b'1' * 20)

  # Receive the peer's peer_id
  pwp.receive_peer_id(conn)

  # Close the connection
  conn.close()

  print('Connection to {} closed'.format(':'.join(conn.getpeername())))


def start(port):

  # Create socket for TCP communication
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

  # Bind socket to a local port
  try:
    s.bind(port)
  except socket.error as e:
    print('Socket Bind Failed: ' + e)

  # Begin listening on socket
  s.listen(8)

  while True:
    # Accept a connection
    conn, addr = s.accept()

    # Handle the connection in its own thread
    t = threading.Thread(target=handle_incoming, args=(conn,))

    #Start the thread
    t.start()


def main():

  port = 6681

  for arg in sys.argv[1:]:
    if arg.startswith('-p') or arg.startswith('--port'):
      port = int(arg[2:])

  start(port)

if __name__ == '__main__':
  main()

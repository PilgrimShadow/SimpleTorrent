import socket
import threading

def handle_incoming(conn):

  am_choking = 1
  am_interested = 0
  peer_choking = 1
  peer_interested = 0

  pass


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

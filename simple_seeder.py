import sys, os, socket, threading

# Project
import torrent, pwp


def handle_incoming(conn, my_peer_id):

  peer_info = conn.getpeername()

  print('Connected to {}:{}'.format(peer_info[0], peer_info[1]))

  # State of this peer
  am_choking = 1
  am_interested = 0
  peer_choking = 1
  peer_interested = 0

  try:
    d = pwp.receive_infohash(conn)
  except e:
    conn.close()
    return

  # Check that we have the file specified by the infohash

  # Send our handshake
  pwp.send_handshake_reply(conn, d['info_hash'], my_peer_id)

  # Receive the peer's peer_id
  d['peer_id'] = pwp.receive_peer_id(conn)

  print('Completed handshake with {}:{}'.format(peer_info[0], peer_info[1]))

  # Close the connection
  conn.close()

  print('Closed connection to {}:{}'.format(peer_info[0], peer_info[1]), end='\n\n')


def start(port, my_peer_id):

  # Create socket for TCP communication
  s = socket.socket()

  # Bind socket to a local port
  try:
    s.bind(('localhost', port))
  except socket.error as e:
    print('Socket Bind Failed: ' + e)

  # Begin listening on socket
  s.listen(8)

  # A dictionary of all the infohashes we are seeding
  torrs = dict()

  # Get infohash of all files in the torrents/ directory
  for (dirpath, dirnames, filenames) in os.walk('torrents'):
    for filename in filenames:
      torr_info = torrent.read_torrent_file(dirpath + '/' + filename)
      torrs[torrent.infohash_hex(torr_info)] = torr_info['info']['name']

  print('Serving...\n' + '\n'.join(hexhash + ' ' + name for hexhash, name in torrs.items()))

  while True:
    # Accept a connection
    conn, addr = s.accept()

    # Handle the connection in its own thread
    t = threading.Thread(target=handle_incoming, args=(conn, my_peer_id))

    #Start the thread
    t.start()


def main():

  port = 6881
  my_peer_id  = b'1' * 20

  # Parse Options
  for arg in sys.argv[1:]:
    if arg.startswith('-p'):
      port = int(arg[2:])

    if arg.startswith('--port'):
      port = int(arg[6:])

  start(port, my_peer_id)

if __name__ == '__main__':
  main()

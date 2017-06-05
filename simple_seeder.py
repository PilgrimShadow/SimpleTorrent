#!/usr/bin/env python3.6
'''A simple torrent seeder

A multi-threaded server that seeds torrents
'''

# Stdlib
import sys, os, socket, threading, time

# Project
import torrent, pwp


def handle_incoming(conn, my_peer_id, torrents):
  '''Function called to handle each incoming connection'''

  # Get address and port of our peer
  peer_info = conn.getpeername()

  print('Connected to {}:{}'.format(peer_info[0], peer_info[1]))

  # State of this peer
  am_choking = 1
  am_interested = 0
  peer_choking = 1
  peer_interested = 0

  peer_has = set()

  # Receive the first part of the handshake
  d = pwp.receive_infohash(conn)

  # Check that we have the file specified by the infohash
  if d['info_hash'] not in torrents.keys():
    print('{}:{} requested unknown torrent:'.format(peer_info[0], peer_info[1]), d['info_hash'].hex())
    conn.close()
    print('Closed connection to {}:{}'.format(peer_info[0], peer_info[1]), end='\n\n')
    return

  torr_info = torrents[d['info_hash']]

  # Send our handshake
  pwp.send_handshake_reply(conn, d['info_hash'], my_peer_id)

  # Receive the rest of the handshake (peer_id)
  d['peer_id'] = pwp.receive_peer_id(conn)

  print('Completed handshake with {}:{}'.format(peer_info[0], peer_info[1]))

  # Open the file
  f = open('files/' + torr_info['info']['name'], 'rb')

  while True:
    msg = pwp.parse_next_message(conn)
    msg_id = msg['id']

    if msg_id == -2:
      break  # The connection was closed
    elif msg_id == -1:
      pass   # Keep-alive
    elif msg_id == 0:
      peer_choking = 1
    elif msg_id == 1:
      peer_choking = 0
    elif msg_id == 2:
      peer_interested = 1
    elif msg_id == 3:
      peer_interested = 0
    elif msg_id == 4:
      peer_has.add(msg['payload'])
    elif msg_id == 5:
      pass
    elif msg_id == 6:
      offset = (msg['payload']['index'] * (2**18)) + msg['payload']['begin']
      f.seek(offset)
      block = f.read(msg['payload']['length'])
      conn.send(pwp.piece(msg['payload']['index'], msg['payload']['begin'], block))

      # Testing
      time.sleep(0.01)
    elif msg_id == 7:
      pass
    elif msg_id == 8:
      pass
    elif msg_id == 9:
      pass

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
      if filename[0] != '.':
        torr_info = torrent.read_torrent_file(dirpath + '/' + filename)
        torrs[torrent.infohash(torr_info)] = torr_info

  print('Serving...\n' + '\n'.join(ihash.hex() + ' ' + torr['info']['name'] for ihash, torr in torrs.items()), end='\n\n')

  while True:
    # Accept a connection
    conn, addr = s.accept()

    # Handle the connection in its own thread
    t = threading.Thread(target=handle_incoming, args=(conn, my_peer_id, torrs))

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

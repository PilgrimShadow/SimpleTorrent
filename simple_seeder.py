#!/usr/bin/env python3.6
'''A simple torrent seeder

A multi-threaded server that seeds torrents
'''

# Stdlib
import sys, os, socket, threading, time, math

# Project
import torrent, pwp


def byte_to_set(byte):
  return { i for i in range(8) if (byte & (128 >> i)) }


def bytestring_to_set(bytestring):
  s = set()

  for i, byte in enumerate(bytestring):
    s |= { b + i*8 for b in byte_to_set(byte) }

  return s

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

  # The set of pieces our peer has
  peer_has = set()

  # Receive the first part of the handshake
  d = pwp.receive_infohash(conn)

  # Check that we have the file specified by the infohash
  if d['info_hash'] not in torrents.keys():
    print('{}:{} requested unknown torrent:'.format(peer_info[0], peer_info[1]), d['info_hash'].hex())
    conn.close()
    print('Closed connection to {}:{}'.format(peer_info[0], peer_info[1]), end='\n\n')
    return

  # Get some info for our torrent
  torr_info = torrents[d['info_hash']]
  piece_size = torr_info['info']['piece length']
  num_pieces = int(math.ceil(torr_info['info']['length'] / piece_size))

  # Send our handshake
  pwp.send_handshake_reply(conn, d['info_hash'], my_peer_id)

  # Receive the rest of the handshake (peer_id)
  d['peer_id'] = pwp.receive_peer_id(conn)

  print('Completed handshake with {}:{}'.format(peer_info[0], peer_info[1]))

  # Open the file
  f = open('files/' + torr_info['info']['name'], 'rb')

  # Get the length of the file
  file_len = f.seek(0, 2)

  # TODO: Send our bitfield message

  # Receive and parse the first message
  msg = pwp.parse_next_message(conn)
  msg_id = msg['id']

  # Check for a bitfield message
  if msg_id == 5:

    # Check the bitfield length
    if len(msg['payload']) != int(math.ceil(num_pieces / 8)):
      print('Received invalid bitfield from {}:{} (wrong length)'.format(peer_info[0], peer_info[1]))
      conn.close
      return

    peer_has = bytestring_to_set(msg['payload'])

    # Check if any invalid bits were set
    if max(peer_has) >= num_pieces:
      print('Received invalid bitfield from {}:{} (extra bits were set)'.format(peer_info[0], peer_info[1]))
      conn.close()
      return

    # Receive and parse the next message
    msg = pwp.parse_next_message(conn)
    msg_id = msg['id']
    

  while True:

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
      print('Received bitfield after initial message...closing connection')
      break
    elif msg_id == 6:

      # Compute the byte-offset of this block within the file
      offset = (msg['payload']['index'] * piece_size) + msg['payload']['begin']

      # Check that the block is valid
      if offset + msg['payload']['length'] > file_len:
        print('{}:{} requested invalid block (overflow)'.format(peer_info[0], peer_info[1]))
        break

      f.seek(offset)

      # Read the requested block
      block = f.read(msg['payload']['length'])

      # Send the requested block
      conn.send(pwp.piece(msg['payload']['index'], msg['payload']['begin'], block))

    elif msg_id == 7:
      pass
    elif msg_id == 8:
      pass
    elif msg_id == 9:
      pass

    # Receive and parse the next message
    msg = pwp.parse_next_message(conn)
    msg_id = msg['id']


  # Close the connection
  conn.close()

  print('Closed connection to {}:{}'.format(peer_info[0], peer_info[1]), end='\n\n')


def start(port, my_peer_id):

  # Create socket for TCP communication
  s = socket.socket()

  # Bind socket to a local port
  try:
    s.bind(('192.168.1.123', port))
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

  # Display the torrents we are serving
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

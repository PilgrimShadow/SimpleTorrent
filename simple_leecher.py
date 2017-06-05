#!/usr/bin/env python3.6
import sys, socket, math, hashlib, time

# Project
import torrent, pwp

def main():

  # Port on which to connect
  port = 6881

  # Peer id used for this peer
  my_peer_id  = b'2' * 20

  # Parse the options
  for arg in sys.argv[1:-2]:
    if arg.startswith('-p'):
      port = int(arg[2:])

    if arg.startswith('--port'):
      port = int(arg[6:])

  addr = sys.argv[-2]
  torr_file = sys.argv[-1]

  # Parse the given torrent file
  torr_info = torrent.read_torrent_file(torr_file)

  # Compute the infohash for the given torrent
  bytehash = torrent.infohash(torr_info)
  print('infohash:', bytehash.hex())

  # Create a socket object
  conn = socket.socket()

  # Connect to the remote addres
  conn.connect((addr, port))

  # Create our handshake bytestring
  handshake = pwp.create_handshake(bytehash, my_peer_id)

  # Send our handshake
  conn.send(handshake)  

  shake_resp = pwp.receive_full_handshake(conn)

  if shake_resp['reserved'] != (b'\x00' * 8):
    print('Handshake failed: unequal reserved bits')
    return

  if shake_resp['info_hash'] != bytehash:
    print('Handshake failed: unequal infohashes')
    return

  print('Handshake success')

  # Indicate that we are interested in receiving pieces
  conn.send(pwp.interested())

  # Request the entire file
  req = pwp.request_all(torr_info['info']['length'])
  conn.send(req)

  blocks_expected = len(req) / 17
  pieces_expected = int(math.ceil(blocks_expected / 16))
  blocks_received = 0
  bytes_received  = 0

  pieces = [set() for _ in range(pieces_expected)]

  print('Progress: {:.2f}%'.format(100 * bytes_received / torr_info['info']['length']), end='')

  # Receive messages until file is complete
  while blocks_received < blocks_expected:
    msg = pwp.parse_next_message(conn)
    msg_id = msg['id']

    if msg_id == -2:
      break
    elif msg_id == 7:

      if msg['payload']['begin'] % (2**14) != 0:
        print('Received block with invalid offset')
        return

      if len(msg['payload']['block']) > 2**14:
        print('Received block longer than 2**14 bytes')
        return

      blocks_received += 1
      bytes_received  += len(msg['payload']['block'])

      print('\rProgress: {:.2f}%'.format(100 * bytes_received / torr_info['info']['length']), end='')

      pieces[msg['payload']['index']].add((msg['payload']['begin'], msg['payload']['block']))

  print()

  # Assemble pieces and write to disk
  with open('{}'.format(torr_info['info']['name']), 'wb') as f:
    for index, piece in enumerate(pieces):

      assembled = b''.join(block[1] for block in sorted(piece))

      if hashlib.sha1(assembled).digest() == torr_info['info']['pieces'][20 * index: 20 * (index+1)]:
        f.write(assembled)
      else:
        f.write(bytes(len(assembled)))
        print('Piece {} is invalid. Writing zeros instead.'.format(index))


if __name__ == '__main__':
  main()

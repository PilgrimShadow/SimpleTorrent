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

  # TODO: Check for a partial download

  # Create a socket object
  conn = socket.socket()

  # Connect to the remote addres
  conn.connect((addr, port))

  # Create our handshake bytestring
  handshake = pwp.create_handshake(bytehash, my_peer_id)

  # Send our handshake
  conn.send(handshake)  

  # Receive handshake from peer
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
  blocks_in_last_piece = blocks_expected % 16
  bytes_received  = 0

  pieces = {i : set() for i in range(pieces_expected)}

  print('Progress: {:.2f}%'.format(100 * bytes_received / torr_info['info']['length']), end='')

  # Create the output file
  with open('downloads/' + torr_info['info']['name'], 'w'):
    pass

  # Receive messages until file is complete
  while len(pieces) > 0:

    # Receive and parse the next message
    msg = pwp.parse_next_message(conn)
    msg_id = msg['id']

    if msg_id == -2:
      break
    elif msg_id == 7:

      if msg['payload']['index'] >= pieces_expected:
        print('Received block with invalid piece index')
        return

      if msg['payload']['begin'] % (2**14) != 0:
        print('Received block with invalid offset')
        return

      if len(msg['payload']['block']) > 2**14:
        print('Received block longer than 2**14 bytes')
        return

      bytes_received  += len(msg['payload']['block'])

      # Display the download progress
      print('\rProgress: {:.2f}%'.format(100 * bytes_received / torr_info['info']['length']), end='')

      index = msg['payload']['index']

      # Add the block to our collection
      pieces[index].add((msg['payload']['begin'], msg['payload']['block']))

      # Assemble the piece if all blocks have arrived
      if (index == pieces_expected-1 and len(pieces[index]) == blocks_in_last_piece) or len(pieces[index]) == 16:

          offset = index * (2**18)
          piece = pieces[index]
          assembled = b''.join(block[1] for block in sorted(piece))

          # If the piece is valid...
          if hashlib.sha1(assembled).digest() == torr_info['info']['pieces'][20 * index: 20 * (index+1)]:

            # Save the piece to disk
            with open('downloads/' + torr_info['info']['name'], 'rb+') as f:
              f.seek(offset)
              f.write(assembled)

            # This piece is no longer needed
            del pieces[index]

            # Send 'have' message to peer
            conn.send(pwp.have(index))
          else:
            # Discard all blocks of the invalid piece
            pieces[index] = set()

            # Re-request the invalid piece
            conn.send(pwp.request_piece(index, torr_info['info']['length']))

            print('Received invalid piece: {}.'.format(msg['payload']['index']))
        
  print()


if __name__ == '__main__':
  main()

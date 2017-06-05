import sys, socket

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
  blocks_received = 0

  # Receive messages until file is complete
  while blocks_received < blocks_expected:
    msg = pwp.parse_next_message(conn)
    msg_id = msg['id']

    if msg_id == -2:
      break
    elif msg_id == 7:
      blocks_received += 1
      print('Blocks received: {}'.format(blocks_received))

      # Save the block
      with open('pieces/{}_{}_{}'.format(torr_info['info']['name'], msg['payload']['index'], msg['payload']['begin']), 'wb') as f:
        f.write(msg['payload']['block'])
      

if __name__ == '__main__':
  main()

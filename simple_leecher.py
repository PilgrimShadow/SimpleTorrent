import sys, socket

# Project
import torrent, pwp

def main():

  # Port over which to connect
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

  torr_info = torrent.read_torrent_file(torr_file)

  ihash = torrent.infohash(torr_info)
  print('infohash:', ihash)

  handshake = pwp.create_handshake(ihash, my_peer_id)

  conn = socket.socket()

  conn.connect((addr, port))

  conn.send(handshake)  

  shake_resp = pwp.receive_full_handshake(conn)

  if shake_resp['reserved'] != (b'\x00' * 8):
    print('Handshake failed: unequal reserved bits')
    return

  if shake_resp['info_hash'] != ihash:
    print('Handshake failed: unequal infohashes')
    return

  print('Handshake success')


if __name__ == '__main__':
  main()

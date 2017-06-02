import socket, struct, threading


def recv_until(conn, n, reattempts=3):

  msg = conn.recv(n)

  for _ in range(reattempts):
    if len(msg) < n:
      msg += conn.recv(n - len(msg))
    else:
      break

  if len(msg) != n:
    raise Exception ('Error: Failed to receive full message')

  return msg


def generate_peer_id():
  pass


def create_handshake(protocol, info_hash, peer_id):
  '''Create the bytestring for a handshake'''

  if len(protocol) > 255:
    raise Exception('protocol name is too long')

  if len(info_hash) != 20:
    raise Exception('info_hash is not 20 bytes long')

  if len(peer_id) != 20:
    raise Exception('peer_id is not 20 bytes long')

  pstr_len = len(protocol).to_bytes(1, 'big')
  pstr = bytes(protocol, 'ascii')
  reserved = b'\x00' * 8
  ih = bytes(info_hash, 'ascii')
  pi = bytes(peer_id, 'ascii')

  return pstr_len + pstr + reserved + ih + pi


def receive_full_handshake(conn):

  inf = receive_infohash(conn)
  peer_id = receive_peer_id(conn)


def receive_infohash(conn):

  # Recieve the length of the protocol string
  raw_len = conn.recv(1)

  if len(raw_len) == 0:
    raise Exception('connection closed')
  else:
    pstr_len = ord(raw_len)

  shake_body = recv_until(conn, 28 + pstr_len)

  return {
    'pstr': shake_body[:pstr_len],
    'reserved': shake_body[pstr_len : pstr_len + 8],
    'info_hash': shake_body[pstr_len+8 : pstr_len+28]
  }


def send_handshake_reply(conn, info_hash, this_peer_id):

  assert(len(info_hash) == 20 and len(this_peer_id) == 20)

  pstr = b'BitTorrent protocol'
  pstr_len = len(pstr).to_bytes(1, 'big')
  reserved = bytes(8)

  conn.send(pstr_len + pstr + reserved + info_hash + this_peer_id)


def receive_peer_id(conn):

  peer_id = recv_until(conn, 20)
  return peer_id.decode()


def parse_next_message(conn):
  '''Parse the next message received from a peer'''

  resp = {'id': 0, 'name': '', 'payload': ''}

  # Get the length of the next message
  len_prefix = conn.recv(4)
  msg_len = struct.unpack('>I', len_prefix)[0]

  if msg_len == 0:
    resp['name'] = 'keep-alive'
    return resp

  remaining = conn.recv(msg_len)

  resp['id'] = remaining[0]

  # Get payload if it exists
  if resp['id'] == 0:
    resp['name'] = 'choke' 
  elif resp['id'] == 1:
    resp['name'] = 'unchoke'
  elif resp['id'] == 2:
    resp['name'] = 'interested'
  elif resp['id'] == 3:
    resp['name'] = 'uninterested'
  elif resp['id'] == 4:
    resp['name'] = 'have'
    resp['payload'] = struct.unpack('>I', remaining[1:])[0]
  elif resp['id'] == 5:
    resp['name'] = 'bitfield'
    resp['payload'] = remaining[1:]
  elif resp['id'] == 6:
    resp['name'] = 'request'
    index, begin, length = struct.unpack('>III', remaining[1:])
    resp['payload'] = { 'index': index, 'begin': begin, 'length': length }
  elif resp['id'] == 7:
    resp['name'] = 'piece'
    index, begin = struct.unpack('>II', remaining[1:9])
    resp['payload'] = { 'index': index, 'begin': begin, 'block': remaining[9:] }
  elif resp['id'] == 8:
    resp['name'] = 'cancel'
    index, begin, length = struct.unpack('>III', remaining[1:])
    resp['payload'] = { 'index': index, 'begin': begin, 'length': length }
    pass
  elif resp['id'] == 9:
    resp['name'] = 'port'
    resp['payload'] = struct.unpack('>H', remaining[1:])[0]
  else:
    # Invalid msg id
    raise Exception('Invalid message received')

  return resp


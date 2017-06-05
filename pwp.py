'''Peer Wire Protocol

'''


# Stdlib
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


def create_handshake(info_hash, peer_id, protocol = 'BitTorrent protocol'):
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

  return pstr_len + pstr + reserved + info_hash + peer_id


def receive_full_handshake(conn):

  ihash = receive_infohash(conn)
  ihash['peer_id'] = receive_peer_id(conn)

  return ihash


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
  return peer_id

def keep_alive():
  return b'\x00\x00\x00\x00'

def choke():
  return b'\x00\x00\x00\x01\x00'

def unchoke():
  return b'\x00\x00\x00\x01\x01'

def interested():
  return b'\x00\x00\x00\x01\x02'

def uninterested():
  return b'\x00\x00\x00\x01\x03'
  
def have(index):
  return b'\x00\x00\x00\x05\x04' + index.to_bytes(4, 'big')

def request(index, begin, length):
  return b'\x00\x00\x00\x0d\x06' + b''.join(x.to_bytes(4, 'big') for x in [index, begin, length])

def piece(index, begin, block):
  msg_len = (len(block) + 9).to_bytes(4, 'big')
  return msg_len + b'\x07' + block

def cancel(index, begin, length):
  return b'\x00\x00\x00\x0d\x08' + b''.join(x.to_bytes(4, 'big') for x in [index, begin, length])

def port(listen_port):
  return b'\x00\x00\x00\x03\x09' + listen_port.to_bytes(2, 'big')


def request_all(file_size):
  piece_size = 2**18
  block_size = 2**14
  blocks_per_piece = piece_size / block_size
  num_whole_pieces = file_size // piece_size

  # The number of whole blocks in the last piece
  rem_blocks = (file_size % piece_size) // block_size

  # The size of the last block
  last_block = file_size % block_size

  if rem_blocks > 0:
    t = b''.join(request(num_whole_pieces, j*block_size, block_size) for j in range(rem_blocks))
  else:
    t = b''

  if last_block > 0:
    v = request(num_whole_pieces, rem_blocks*block_size, last_block)
  else:
    v = b''

  return b''.join( request(i, j*block_size, block_size) for i in range(num_whole_pieces) for j in range(blocks_per_piece) ) + t + v

  

def parse_next_message(conn):
  '''Parse the next message received from a peer'''

  resp = {'id': -1, 'name': '', 'payload': ''}

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


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
  return msg_len + b'\x07' + b''.join(x.to_bytes(4, 'big') for x in [index, begin]) + block

def cancel(index, begin, length):
  return b'\x00\x00\x00\x0d\x08' + b''.join(x.to_bytes(4, 'big') for x in [index, begin, length])

def port(listen_port):
  return b'\x00\x00\x00\x03\x09' + listen_port.to_bytes(2, 'big')


def request_all(file_size):
  piece_size = 2**18
  block_size = 2**14
  blocks_per_piece = 16
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

 
def request_piece(index, file_len):
  '''Request an entire piece'''

  piece_size = 2**18
  block_size = 2**14

  net_offset = index * piece_size
  reqs = []

  # Create individual requests
  for i in range(16):
    if net_offset >= file_len:
      break

    reqs.append(request(index, i*block_size, min(block_size, file_len - net_offset)))
    net_offset += block_size

  # Join all requests into single byte-string
  return b''.join(reqs)


class MessageParser():
  '''Class for parsing PWP messages

     TODO: Perhaps turn this into an iterator?
  '''

  def __init__(self, transport=None, initial_data=b''):

    # Any initial data to place in the buffer
    self.unread= initial_data

    # The transport field to be included in all messages
    self.transport = transport

    # Have we seen the infohash yet?
    self.infohash = False

    # Have we seen the peer_id yet?
    self.peer_id = False


  def __iter__(self):
    return self


  def add(self, data):
    '''Add more data to the buffer'''
    self.unread += data


  def has_next(self):
    '''Indicates whether there is a complete message in the buffer'''

    # We are waiting on the infohash
    if not self.infohash:
      if len(self.unread) > 0:
        handshake_len = 49 + self.unread[0]
        if len(self.unread) >= handshake_len:
          return True

      return False

    # We are waiting on the peer_id
    if not self.peer_id:
      return len(self.unread) >= 20

    # We are waiting on a normal message
    if len(self.unread) < 4:
      return False

    # Read the length of the next message
    msg_len = struct.unpack('>I', self.unread[:4])[0]

    # Check if the entire message is in the buffer
    return len(self.unread) >= 4+msg_len


  def __next__(self):
    '''Parse and return the next message'''

    # A dictionary representing the parsed message
    resp = {'id': -2, 'name': '', 'transport': self.transport, 'payload': None}

    # This class will behave as an iterator
    if not self.has_next():
      raise StopIteration()

    # The next 'message' is the infohash
    if not self.infohash:
      resp['name'] = 'infohash'
      pstr_len = self.unread[0]
      resp['payload'] = self.unread[pstr_len+9 : pstr_len+29]
      self.unread = self.unread[29+pstr_len:]
      self.infohash = True
      return resp

    # The next 'message' is the peer_id
    if not self.peer_id:
      resp['name'] = 'peer_id'
      resp['payload'] = self.unread[:20]
      self.unread = self.unread[20:]
      self.peer_id = True
      return resp

    # Read the length of the next message
    msg_len = struct.unpack('>I', self.unread[:4])[0]

    # Handle the keep-alive message
    if msg_len == 0:
      resp['id'] = -1
      resp['name'] = 'keep-alive'
      self.unread = self.unread[4:]
      return resp

    msg = self.unread[4:4 + msg_len]

    # TODO: Check if the msg id is an ascii decimal
    resp['id'] = msg[0]
     
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
      resp['payload'] = struct.unpack('>I', msg[1:])[0]
    elif resp['id'] == 5:
      resp['name'] = 'bitfield'
      resp['payload'] = msg[1:]
    elif resp['id'] == 6:
      resp['name'] = 'request'
      index, begin, length = struct.unpack('>III', msg[1:])
      resp['payload'] = { 'index': index, 'begin': begin, 'length': length }
    elif resp['id'] == 7:
      resp['name'] = 'piece'
      index, begin = struct.unpack('>II', msg[1:9])
      resp['payload'] = { 'index': index, 'begin': begin, 'block': msg[9:] }
    elif resp['id'] == 8:
      resp['name'] = 'cancel'
      index, begin, length = struct.unpack('>III', msg[1:])
      resp['payload'] = { 'index': index, 'begin': begin, 'length': length }
    elif resp['id'] == 9:
      resp['name'] = 'port'
      resp['payload'] = struct.unpack('>H', msg[1:])[0]
    else:
      # Invalid msg id
      raise Exception('Invalid message received')

    # Advance the buffer
    self.unread = self.unread[4 + msg_len:]

    return resp

  def next(self):
    return self.__next__()


def parse_next_message(conn):
  '''Parse the next message received from a peer'''

  resp = {'id': -2, 'name': '', 'payload': ''}

  # Get the length of the next message
  len_prefix = conn.recv(4)

  # Check if connection is closed
  if len(len_prefix) == 0:
    return resp

  msg_len = struct.unpack('>I', len_prefix)[0]

  if msg_len == 0:
    resp['id'] = -1
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
  elif resp['id'] == 9:
    resp['name'] = 'port'
    resp['payload'] = struct.unpack('>H', remaining[1:])[0]
  else:
    # Invalid msg id
    raise Exception('Invalid message received')

  return resp


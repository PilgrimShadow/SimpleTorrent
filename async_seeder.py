#!/usr/bin/env python3.6
'''A torrent seeder built with asyncio

A server that seeds torrents
'''

# Stdlib
import asyncio, logging, os, sys, math

# Project
import torrent, pwp


def byte_to_set(byte):
  '''Convert a single byte into a set'''
  return { i for i in range(8) if (byte & (128 >> i)) }


def bytestring_to_set(bytestring):
  '''Convert a bytestring into a set'''
  s = set()

  for i, byte in enumerate(bytestring):
    s |= { b + i*8 for b in byte_to_set(byte) }

  return s

# Configure the logger
logging.basicConfig(
  level=logging.DEBUG,
  datefmt='%Y/%m/%d %H:%M:%S',
  format='%(asctime)s %(name)s %(message)s',
  filename='server_log.txt'
)

class PeerWireProtocol(asyncio.Protocol):
  '''Implements the Peer-Wire-Protocol

     Parses incoming PWP messages and places them into a queue.
  '''

  def __init__(self, peers, files, torrents, seeking=None): 

    # The queue in which to place messages
    self.queue = asyncio.Queue()

    # The peer list
    self.peers = peers

    # The file dictionary
    self.files = files

    # The torrents we are serving
    self.torrents = torrents

    self.torr = None

    # Torrent identifier
    self.infohash = None

    # The pieces we are missing
    self.pieces = None

    # Are we seeking a particular torrent?
    if seeking is not None:
      self.torr = seeking
      self.infohash = torrent.infohash(seeking)
      self.pieces = dict()

    # The message parser for this connection
    self.parser = pwp.MessageParser()

    # TODO: Change this
    self.peer_id = b'1'*20

    # The function used to handle messages
    self.handler = self._infohash_handler


  def _infohash_handler(self):
    '''Handles the reception of the infohash'''
  
    if self.parser.has_next():

      msg = self.parser.next()

      if self.infohash is None:
        self.infohash = msg['payload']

        # Check that we have the file specified by the infohash
        if self.infohash not in self.torrents:
          self.log.debug('requested unknown torrent: {}'.format(self.infohash.hex()))
          transport.close()
          return

        # The metainfo for the file we are serving
        self.torr = self.torrents[self.infohash]

        # Send our handshake
        self.transport.write(pwp.create_handshake(self.infohash, self.peer_id))

      else:
        # Check that the response shake has the same infohash
        if self.infohash != msg['payload']:
          self.log.debug('response handshake had incorrect infohash')
          self.transport.close()
          return

      # Details about pieces and blocks for this torrent
      self.blocks_expected = int(math.ceil(self.torr['info']['length'] / 2**14))
      self.pieces_expected = int(math.ceil(self.torr['info']['length'] / self.torr['info']['piece length']))
      self.blocks_per_piece = int(self.torr['info']['piece length'] / 2**14)
      self.blocks_in_last_piece = self.blocks_expected % self.blocks_per_piece

      if self.pieces is not None:
        self.pieces = { i : set() for i in range(self.pieces_expected) }
      else:
        self.pieces = dict()

      # Open the file if necessary
      if self.infohash not in self.files:
        self.files[self.infohash] = open('files/' + self.torr['info']['name'], 'rb' if len(self.pieces)==0 else 'wb+')

      self.file = self.files[self.infohash]

      # Advance the handler
      self.handler = self._peer_id_handler

      # Handle any other messages
      self.handler()


  def _peer_id_handler(self):
    '''Handles the reception of the peer_id''' 

    if self.parser.has_next():

      msg = self.parser.next()

      peer_id = msg['payload']

      peer_info = {'infohash': self.infohash, 'peer_id': peer_id,
        'transport': self.transport, 'queue': self.queue,
        'peer_choking': True, 'am_choking': True,
        'peer_interested': False, 'am_interested': False,
        'peer_has': set(), 'torr': self.torr, 'file': self.file,
        'blocks_expected': self.blocks_expected, 'pieces_expected': self.pieces_expected,
        'blocks_per_piece': self.blocks_per_piece, 'blocks_in_last_piece': self.blocks_in_last_piece,
        'pieces': self.pieces}

      # Add this peer to the list
      self.peers.append(peer_info)

      # We are now ready to handle normal PWP messages
      self.handler = self._message_handler

      # Handle any other messages
      self.handler()


  # TODO: Move these checks to the MessageParser
  def _bitfield_handler(self):

    # Check for a bitfield message
    if msg_id == 5:

      # Check the bitfield length
      if len(msg['payload']) != int(math.ceil(num_pieces / 8)):
        print('Received invalid bitfield from {}:{} (wrong length)'.format(peer_info[0], peer_info[1]))
        transport.close()
        return

      peer_has = bytestring_to_set(msg['payload'])

      # Check if any invalid bits were set
      if max(peer_has) >= num_pieces:
        print('Received invalid bitfield from {}:{} (extra bits were set)'.format(peer_info[0], peer_info[1]))
        transport.close()
        return


  def _message_handler(self):
    '''Handles normal PWP messages'''

    # Put all new messages into queue
    for msg in self.parser:
      self.queue.put_nowait(msg)


  def connection_made(self, transport):
    '''Called when a connection is established'''

    self.transport = transport
    self.peername = transport.get_extra_info('peername')

    # Set the logger for this connection
    self.log = logging.getLogger('{}:{}'.format(*self.peername))

    self.log.debug('connection made')

    # Initiate the handshake, if necessary
    if self.torr is not None:
      self.transport.write(pwp.create_handshake(self.infohash, self.peer_id))

      # TODO: Send our bitfield

      # Request the entire file
      self.transport.write(pwp.request_all(self.torr['info']['length']))


  def connection_lost(self, exc):
    '''Called when the connection is lost'''

    # Put the connection closed message in the queue
    self.queue.put_nowait({'id': -2, 'name': 'closed', 'payload': None})

    self.log.debug('connection lost')

    super().connection_lost(exc)


  def data_received(self, data):
    '''Called when a socket receives data'''

    # Add the data to the message buffer
    self.parser.add(data)

    # Handle the messages
    self.handler()


async def worker(peers, n=10, sleep=0.001):
  '''Fairly handle peer messages

  All connected peers are served at the same rate. When there is
  no work to do, this worker sleeps for the specified amount of time.

  '''

  # Closed connections to be cleaned up
  closed = set()

  while True:

    # Was there any work to do?
    worked = False

    for i, peer in enumerate(peers):

      # Handle up to n messages per peer
      for _ in range(n):

        if peer['queue'].empty():
          break

        # Get the next message for this peer
        msg = peer['queue'].get_nowait()
        peer['queue'].task_done()
        worked = True

        if msg['id'] == -1:
          pass   # Keep-alive
        elif msg['id'] == -2:
          closed.add(i)
        elif msg['id'] == 0:
          peer['am_choking'] = True
        elif msg['id'] == 1:
          peer['peer_choking'] = False
        elif msg['id'] == 2:
          peer['am_interested'] = True
        elif msg['id'] == 3:
          peer['peer_interested'] = False
        elif msg['id'] == 4:
          peer['peer_has'].add(msg['payload'])
        elif msg['id'] == 5:
          peer['peer_has'].update(byteset_to_set(msg['payload']))
        elif msg['id'] == 6:

          piece_len = peer['torr']['info']['piece length']

          # Compute the byte-offset of this block within the file
          offset = (msg['payload']['index'] * piece_len) + msg['payload']['begin']

          # Check that the block is valid
          if offset + msg['payload']['length'] > peer['torr']['info']['length']:
            print('requested invalid block (overflow)')
            continue

          peer['file'].seek(offset)

          # Read the requested block
          block = peer['file'].read(msg['payload']['length'])

          # Send the requested block
          peer['transport'].write(pwp.piece(msg['payload']['index'], msg['payload']['begin'], block))

        elif msg['id'] == 7:

          print('received piece')

          index = msg['payload']['index']

          # We don't need this block
          if index not in peer['pieces']:
            continue

          # Add the block to our collection
          peer['pieces'][index].add((msg['payload']['begin'], msg['payload']['block']))

          # Assemble the piece if all blocks have arrived
          if (index == peer['pieces_expected']-1 and len(peer['pieces'][index]) == peer['blocks_in_last_piece']) or len(peer['pieces'][index]) == peer['blocks_per_piece']:

            offset = index * peer['torr']['info']['piece length']
            assembled = b''.join(block[1] for block in sorted(peer['pieces'][index]))

            # If the piece is valid...
            if hashlib.sha1(assembled).digest() == peer['torr']['info']['pieces'][20 * index: 20 * (index+1)]:

              # Save the piece to disk
              peer['file'].seek(offset)
              peer['file'].write(assembled)

              # This piece is no longer needed
              del peer['pieces'][index]

              # Send 'have' message to peer
              peer['transport'].write(pwp.have(index))
            else:

              # Discard all blocks of the invalid piece
              pieces[index] = set()

              # Re-request the invalid piece
              peer['transport'].write(pwp.request_piece(index, peer['torr']['info']['length'], peer['torr']['info']['piece length']))

    # Clear data for all closed connections
    for i in closed:
      del peers[i]['queue']
      del peers[i]

    closed = set()

    # Sleep if no work was done (this allows other coroutines to run)
    if not worked:
      await asyncio.sleep(sleep)


def start(port, my_peer_id):
  '''Start the server on the given port'''

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

  # The event loop
  loop = asyncio.get_event_loop()

  # List of all peers to which we are connected
  peers = []

  # Mapping from infohash to file-object
  files = dict()

  # Create the server coroutine
  server_factory = loop.create_server(lambda: PeerWireProtocol(peers, files, torrs), host='192.168.1.123', port=port)

  # Schedule the server
  server = loop.run_until_complete(server_factory)

  try:
    x = loop.run_until_complete(worker(peers))
  except KeyboardInterrupt:
    print('\rshutting down...')

  # Close all files
  for f in files.values():
    f.close()

  # Start closing the server
  server.close()

  # Wait until the server is closed
  loop.run_until_complete(server.wait_closed())

  # Close the event loop
  loop.close()


def leech(torr, addr):
  '''Download the given torrent from the given peers.'''

  # The event loop
  loop = asyncio.get_event_loop()

  # List of all peers to which we are connected
  peers = []

  # Mapping from infohash to file-object
  files = dict()

  # Create the connection coroutine
  coro = loop.create_connection(lambda: PeerWireProtocol(peers, files, [], torr), host=addr[0], port=addr[1])

  trans, proto = loop.run_until_complete(coro)

  try:
    x = loop.run_until_complete(worker(peers))
  except KeyboardInterrupt:
    print('\rshutting down...')

  # Close all files
  for f in files.values():
    f.close()

  # Close the connection
  trans.close()

  # Close the event loop
  loop.close()


def main():
  import sys

  port = 6881
  my_peer_id  = b'1' * 20

  if sys.argv[1] == 'leech':
    torr = torrent.read_torrent_file(sys.argv[2])
    addr = sys.argv[3]

    leech(torr, (addr, port))

  elif sys.argv[1] == 'seed':
    start(port, my_peer_id)


  # Parse Options
  for arg in sys.argv[1:]:
    if arg.startswith('-p'):
      port = int(arg[2:])

    if arg.startswith('--port'):
      port = int(arg[6:])

if __name__ == '__main__':
  main()

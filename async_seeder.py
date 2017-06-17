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
  format='%(name)s: %(message)s',
  stream=sys.stderr
)

class PeerWireProtocol(asyncio.Protocol):
  '''Implements the Peer-Wire-Protocol

     Parses incoming PWP messages and places them into a queue.
  '''

  def __init__(self, loop, peers, files, torrents): 

    # The queue in which to place messages
    self.queue = asyncio.Queue(loop=loop)

    # The peer list
    self.peers = peers

    # The file dictionary
    self.files = files

    # The torrents we are serving
    self.torrents = torrents

    # The message parser for this connection
    self.parser = pwp.MessageParser()

    # Torrent identifier
    self.infohash = b''

    # The function used to handle messages
    self.handler = self._infohash_handler


  def _infohash_handler(self):
    '''Handles the reception of the infohash'''
  
    if self.parser.has_next():

      msg = self.parser.next()

      self.infohash = msg['payload']

      # Check that we have the file specified by the infohash
      if self.infohash not in self.torrents:
        self.log.debug('requested unknown torrent: {}'.format(self.infohash.hex()))
        transport.close()
        return

      # The metainfo for the file we are serving
      self.torr = self.torrents[self.infohash]

      if self.infohash not in self.files:
        self.files[self.infohash] = open('files/' + self.torr['info']['name'], 'rb')

      self.file = self.files[self.infohash]

      # Send our handshake
      self.transport.write(pwp.create_handshake(self.infohash, b'1'*20))

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
        'peer_has': set(), 'torr': self.torr, 'file': self.file}

      # Add this peer to the list
      self.peers.append(peer_info)

      # We are now ready to handle normal PWP messages
      self.handler = self._message_handler

      # Handle any other messages
      self.handler()


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

    self.log.debug('Connection made')


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


async def worker(peers, torrs, n=10, sleep=0.001):
  '''Fairly handle peer messages

  All connected peers are served at the same rate. When there is
  no work to do, this worker sleeps for the specified amount of time.

  '''

  # Map from infohash to file object
  files = dict()

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


    # Clear data for all closed connections
    for i in closed:
      peers[i]['transport'].close()
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
  server_factory = loop.create_server(lambda: PeerWireProtocol(loop, peers, files, torrs), host='localhost', port=port)

  # Schedule the server
  server = loop.run_until_complete(server_factory)

  try:
    x = loop.run_until_complete(worker(peers, torrs))
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


def main():
  import sys

  port = 6881
  my_peer_id  = b'1' * 20

  # Parse Options
  for arg in sys.argv[1:]:
    if arg.startswith('-p'):
      port = int(arg[2:])

    if arg.startswith('--port'):
      port = int(arg[6:])

  # Start the server
  start(port, my_peer_id)

if __name__ == '__main__':
  main()

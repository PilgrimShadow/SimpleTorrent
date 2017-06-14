#!/usr/bin/env python3.6
'''A torrent seeder built with asyncio

A multi-threaded server that seeds torrents
'''

# Stdlib
import asyncio, sys, os, socket, threading, time, math

# Project
import torrent, pwp


def byte_to_set(byte):
  return { i for i in range(8) if (byte & (128 >> i)) }


def bytestring_to_set(bytestring):
  s = set()

  for i, byte in enumerate(bytestring):
    s |= { b + i*8 for b in byte_to_set(byte) }

  return s


class TorrentProtocol(asyncio.Protocol):
  '''A simple torrent protocol

  '''

  def __init__(self, queue, torrents): 

    # The queue in which to place messages
    self.queue = queue
    self.parser = pwp.MessageParser()
    self.torrents = torrents

    # The state of this peer
    self.am_choking = 1
    self.am_interested = 0
    self.peer_choking = 1
    self.peer_interested = 0

    # Torrent and peer identifiers
    self.infohash = b''
    self.peer_id  = b''

    # The set of pieces our peer has
    self.peer_has = set()

    # The function used to handle messages
    self.handler = self._infohash_handler


  def _infohash_handler(self):
    '''Handles the reception of the infohash'''
  
    if self.parser.has_next():

      msg = self.parser.next()

      self.infohash = msg['payload']

      # TODO: Check if we have the torrent, and get info
      # Check that we have the file specified by the infohash
      if self.infohash not in self.torrents.keys():
        print('{} requested unknown torrent: {}'.format(self.peername), self.infohash.hex())
        transport.close()
        return

      # Send our handshake
      self.transport.write(pwp.create_handshake(self.infohash, b'1'*20))

      # Only change the handler if a message was parsed
      self.handler = self._peer_id_handler

      # Handle any other messages
      self.handler()


  def _peer_id_handler(self):
    '''Handles the reception of the peer_id''' 

    if self.parser.has_next():

      msg = self.parser.next()

      self.peer_id = msg['payload']

      # Put the handshake message in the queue
      self.queue.put_nowait({'id': -3, 'name': 'handshake', 'payload': {'infohash': self.infohash, 'peer_id': self.peer_id}})

      # Only change the handler if a message was parsed
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
    '''Handles normal PWP messages with a peer'''

    for msg in self.parser:
      self.queue.put_nowait(msg)


  def connection_made(self, transport):
    '''Called when a connection is established'''

    self.peername = transport.get_extra_info('transport')
    print('Connection from {}'.format(self.peername))

    self.transport = transport


  def connection_lost(self, exc):
    print('Lost connection with {}'.format(self.peername))


  def data_received(self, data):
    '''Called when a socket receives data'''

    # Add the data to the message buffer
    self.parser.add(data)

    # Handle the messages
    self.handler()


def peer_data(handshake):
  return {'infohash': handshake['payload']['infohash'],
          'peer_id': handshake['payload']['peer_id'],
          'peer_choking': True, 'am_choking': True,
          'peer_interested': False, 'am_interested': False,
          'peer_has': set()}


async def consumer(msg_queue, torrents):
  '''Function called to handle each incoming connection'''

  # Map from peer_id to peer_info
  peers = dict()

  # Map from infohash to file info
  files = dict()

  # Get some info for our torrent
  #torr_info = torrents[d['info_hash']]
  #piece_size = torr_info['info']['piece length']
  #num_pieces = int(math.ceil(torr_info['info']['length'] / piece_size))

  while True:

    # Get the next message from the queue
    msg = await msg_queue.get()

    # TODO: Testing
    print(msg)
    continue

    if msg['name'] == 'handshake':
      peers[msg['peer_id']] = peer_data(msg)
    elif msg_id == -2:
      del peers[msg['peer_id']] # Connection was closed
    elif msg_id == -1:
      pass   # Keep-alive
    elif msg['id'] == 0:
      peers[msg['peer_id']]['peer_choking'] = True
    elif msg['id'] == 1:
      peers[msg['peer_id']]['peer_choking'] = False
    elif msg['id'] == 2:
      peers[msg['peer_id']]['peer_interested'] = True
    elif msg['id'] == 3:
      peers[msg['peer_id']]['peer_interested'] = False
    elif msg['id'] == 4:
      peers[msg['peer_id']]['peer_has'].add(msg['payload'])
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

  loop = asyncio.get_event_loop()

  # The message queue
  q = asyncio.Queue(loop=loop)

  # Create the server coroutine
  coro = loop.create_server(lambda: TorrentProtocol(q, torrs), '127.0.0.1', port)

  # Schedule the server
  server = loop.run_until_complete(asyncio.gather(coro, consumer(q, torrs)))

  # Close the server
  server.close()

  # Close the event loop
  loop.close()


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

'''Library for creating and reading torrent files'''

# Stdlib
import datetime, hashlib

def parse_bencode(byts, start=0):
  '''Parse a bencoded bytestring'''

  pos = start

  if byts[pos] == ord('i'):
    pos += 1

    while byts[pos: pos+1].isdigit():
      pos += 1

    if byts[pos] != ord('e'):
      raise Exception('Invalid bencoding of integer (no terminating e)')

    # Skip the trailing 'e'
    pos += 1

    return int(byts[start+1 : pos-1].decode()), pos

  elif byts[pos:pos+1].isdigit():
    raw_len = byts[pos:pos+1]
    pos += 1

    while byts[pos: pos+1].isdigit():
      raw_len += byts[pos:pos+1]
      pos += 1

    if byts[pos] != ord(':'):
      raise Exception('Invalid bencoding of string (missing colon after length)')

    pos += 1
    str_len = int(raw_len.decode()) 
    res = byts[pos : pos + str_len]
    pos += str_len
    
    return res, pos

  elif byts[pos] == ord('l'):
    res = []
    pos += 1

    while byts[pos] != ord('e'):
      item, pos = parse_bencode(byts, pos)
      res.append(item)

    return res, pos + 1

  elif byts[pos] == ord('d'):
    res = dict()
    pos += 1

    while byts[pos] != ord('e'):
      raw_key, pos = parse_bencode(byts, pos)
      value, pos = parse_bencode(byts, pos)
      if raw_key.decode() in {'announce', 'comment', 'created by', 'encoding', 'name'}:
        res[raw_key.decode()] = value.decode()
      else:
        res[raw_key.decode()] = value

    return res, pos + 1


def infohash(torr_dict):
  '''Return the infohash of a torrent as a hexstring'''
  return hashlib.sha1(bencode(torr_dict['info'])).digest()


def read_torrent_file(file_name):
  '''Read a torrent file'''

  with open(file_name, 'br') as f:
    byts = f.read()

  return parse_bencode(byts)[0]


def create_torrent(file_name, piece_length=2**18, comment=''):
  '''Generate torrent info for the given file.

  Return a dictionary containing the torrent info for the given file.
  '''

  # TODO: If file_name is a directory, create a multi-file torrent

  hash_list = []
  file_length  = 0

  torrent = {
              'announce': '',
              'info': {
                'name': file_name.split('/')[-1],
                'piece length': piece_length
              },
              'comment': comment,
              'created by': 'SimpleTorrent',
              'encoding': 'ascii'
            }

  with open(file_name, 'rb') as f:
    
    md5hash = hashlib.md5()

    # Read the first piece
    piece = f.read(piece_length)

    # Compute the sha1 digest of every piece
    while len(piece) > 0:
      md5hash.update(piece)
      hash_list.append(hashlib.sha1(piece).digest())
      piece = f.read(piece_length)

    # The length of the file (in bytes)
    torrent['info']['length'] = f.tell()

  # Concatenate the piece hashes to create the 'piece' field
  torrent['info']['pieces'] = b''.join(hash_list)

  # Add the md5 sum of the file
  torrent['info']['md5sum'] = md5hash.digest().hex()

  # Add the time of creation
  torrent['creation date'] = int(datetime.datetime.now().timestamp())

  return torrent
  
 

def bencode(data):
  '''Bencode data

  Given a dictionary, return a bencoded bytestring of that dictionary.
  ''' 

  if isinstance(data, int):
    return bytes('i{:d}e'.format(data), 'ascii')
  elif isinstance(data, str):
    return bytes('{:d}:{:s}'.format(len(data), data), 'ascii')
  elif isinstance(data, bytes):
    return bytes(str(len(data)), 'ascii') + b':' + data
  elif isinstance(data, list):
    return b'l' + b''.join(bencode(elem) for elem in data) + b'e'
  elif isinstance(data, dict):
    return b'd' + b''.join(bencode(key) + bencode(value) for key, value in sorted(data.items(), key=lambda item: item[0])) + b'e'
  else:
    raise Exception('Invalid data type encountered: {}'.format(data))


def create_torrent_file(input_file, save_dir='torrents'):
  '''Create a torrent file for the given input file.'''

  t = create_torrent(input_file)
  output_file = '{}/{}.torrent'.format(save_dir, input_file.split('/')[-1])

  with open(output_file, 'bw') as f:
    f.write(bencode(t))




import hashlib
import datetime


def parse_bencode(text, start=0):

  pos = start

  if text[pos] == 'i':
    pos += 1

    while text[pos].isdigit():
      pos += 1

    if text[pos] != 'e':
      raise Exception('Invalid bencoding of integer (no terminating e)')

    # Skip the trailing 'e'
    pos += 1

    return int(text[start+1 : pos-1]), pos

  elif text[pos].isdigit():
    raw_len = text[pos]
    pos += 1

    while text[pos].isdigit():
      raw_len += text[pos]
      pos += 1

    if text[pos] != ':':
      raise Exception('Invalid bencoding of string (missing colon after length)')

    pos += 1
    str_len = int(raw_len) 
    res = text[pos : pos + str_len]
    pos += str_len
    
    return res, pos

  elif text[pos] == 'l':
    res = []
    pos += 1

    while text[pos] != 'e':
      item, pos = parse_bencode(text, pos)
      res.append(item)

    return res, pos + 1

  elif text[pos] == 'd':
    res = dict()
    pos += 1

    while text[pos] != 'e':
      key, pos = parse_bencode(text, pos)
      value, pos = parse_bencode(text, pos)
      res[key] = value

    return res, pos + 1


def infohash(torr_dict):
  '''Compute the infohash of a torrent'''

  benc = bytes(bencode(torr_dict['info']), 'ascii')

  return hashlib.sha1(benc).hexdigest()


def read_torrent_file(file_name):
  '''Read a torrent file'''

  with open(file_name) as f:
    text = f.read()

  return parse_bencode(text)[0]


def create_torrent(file_name, piece_length=2**18, comment=''):
  '''Generate torrent info for the given file.

  Return a dictionary containing the torrent info for the given file.
  '''

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
    
    # Read the first piece
    piece = f.read(piece_length)

    while len(piece) > 0:
      hash_list.append(hashlib.sha1(piece).hexdigest())
      piece = f.read(piece_length)

    # The length of the file (in bytes)
    torrent['info']['length'] = f.tell()

  # Add the hash list to the dictionary
  torrent['info']['pieces'] = ''.join(hash_list)

  # Add the time of creation
  torrent['creation date'] = int(datetime.datetime.now().timestamp())

  return torrent
  
 

def bencode(data):
  '''Bencode data

  Given a dictionary, return a bencoded bytestring of that dictionary.
  ''' 

  if isinstance(data, int):
    return 'i{:d}e'.format(data)
  elif isinstance(data, str):
    return '{:d}:{:s}'.format(len(data), data)
  elif isinstance(data, list):
    return 'l' + ''.join(bencode(elem) for elem in data) + 'e'
  elif isinstance(data, dict):
    return 'd' + ''.join(bencode(key) + bencode(value) for key, value in sorted(data.items(), key=lambda item: item[0])) + 'e'
  else:
    raise Exception('Invalid data type encountered: {}'.format(data))


def create_torrent_file(input_file, output_file):
  '''Create a torrent file for the given input file.'''

  t = create_torrent(input_file)
  fn = output_file if output_file.endswith('.torrent') else output_file + '.torrent'

  with open(fn, 'w') as f:
    f.write(bencode(t))




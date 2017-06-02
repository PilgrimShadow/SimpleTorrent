import hashlib
import datetime

def read_torrent(file_name):
  pass

def create_torrent(file_name, comment):

  piece_length = 2 ** 18
  hash_list = []
  file_length  = 0

  torrent = {
              'announce': '',
              'info': {
                'name': file_name.split('/')[-1],
                'piece length': piece_length
              },
              'comment': comment
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
  '''Bencode data''' 

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
  t = create_torrent(input_file)
  fn = output_file if output_file.endswith('.torrent') else output_file + '.torrent'
  with open(fn, 'w') as f:
    f.write(bencode(t))




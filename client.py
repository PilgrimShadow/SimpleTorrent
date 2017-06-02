import torrent
import sys

def main():

  peers = []

  for arg in sys.argv[1:]:
    if arg.beginswith('-p'):
      ip, raw_port = arg[2:].split(':')
      peers.append((ip, int(raw_port)))

  if sys.argv[1] == 'add':
    t = torrent.read_torrent(sys.argv[2])

if __name__ == '__main__':
  main()

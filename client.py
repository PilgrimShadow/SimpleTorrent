import torrents
import sys

def main():

  if sys.argv[1] == 'add':
    t = torrents.read_torrent(sys.argv[2])

if __name__ == '__main__':
  main()

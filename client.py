#!/usr/bin/env python3.6

import torrent
import sys, os

def main():

  peers = []

  for arg in sys.argv[1:]:
    if arg.startswith('-p'):
      ip, raw_port = arg[2:].split(':')
      peers.append((ip, int(raw_port)))

  if sys.argv[1] == 'add':
    file_name = sys.argv[2].split('/')[-1]
    torrent.create_torrent_file(sys.argv[2])
    os.link(sys.argv[2], 'files/' + file_name)
    

if __name__ == '__main__':
  main()

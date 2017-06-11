#!/usr/bin/env python3.6

# Stdlib
import sys, os

# Project
import torrent

def main():

  peers = []

  for arg in sys.argv[1:]:
    if arg.startswith('-p'):
      ip, raw_port = arg[2:].split(':')
      peers.append((ip, int(raw_port)))

  if sys.argv[1] == 'add':

    # Get the pathless filename
    file_name = sys.argv[2].split('/')[-1]

    # Create a torrent for the new file
    torrent.create_torrent_file(sys.argv[2])

    # Link the file into the local files/ directory
    os.link(sys.argv[2], 'files/' + file_name)
    

if __name__ == '__main__':
  main()

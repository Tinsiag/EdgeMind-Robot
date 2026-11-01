#!/usr/bin/env python3
"""Copy files to the Lichee Pi 4A over SFTP (password auth).

usage: lpi4a_put.py <remote_dir> <local_file> [local_file ...]
"""
import sys, os, paramiko

HOST, USER, PWD = '10.0.0.237', 'debian', 'debian'

def main():
    remote_dir, files = sys.argv[1], sys.argv[2:]
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20, banner_timeout=30, auth_timeout=30)
    sftp = c.open_sftp()
    try:
        sftp.stat(remote_dir)
    except IOError:
        sftp.mkdir(remote_dir)
    for f in files:
        dest = remote_dir.rstrip('/') + '/' + os.path.basename(f)
        sftp.put(f, dest)
        print(f'{f} -> {dest} ({os.path.getsize(f)} bytes)')
    sftp.close(); c.close()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Run a command on the Lichee Pi 4A over SSH (password auth) and print output."""
import sys, paramiko

HOST, USER, PWD = '10.0.0.237', 'debian', 'debian'

def main():
    cmd = sys.stdin.read() if sys.argv[1:2] == ['-'] else ' '.join(sys.argv[1:])
    timeout = 120
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20, banner_timeout=30, auth_timeout=30)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    stdin.close()
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    rc = stdout.channel.recv_exit_status()
    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write(err)
    c.close()
    sys.exit(rc)

if __name__ == '__main__':
    main()

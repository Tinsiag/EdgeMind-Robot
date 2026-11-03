"""4A task deployment/readback helper. Credentials come from the environment."""
import argparse,hashlib,json,os
from pathlib import Path
import paramiko

def main():
    p=argparse.ArgumentParser();p.add_argument('--command');p.add_argument('--put',nargs=2,action='append',default=[])
    p.add_argument('--get',nargs=2,action='append',default=[]);p.add_argument('--timeout',type=int,default=90)
    a=p.parse_args();s=paramiko.SSHClient();s.load_system_host_keys();s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect('192.168.40.101',username='debian',password=os.environ['EDGE_SSH_PASSWORD'],timeout=10)
    try:
        if a.put or a.get:
            with s.open_sftp() as f:
                for local,remote in a.put:
                    f.put(local,remote)
                    with f.open(remote,'rb') as h:body=h.read()
                    assert body==Path(local).read_bytes(),remote
                    print(json.dumps(dict(path=remote,sha256=hashlib.sha256(body).hexdigest())))
                for remote,local in a.get:
                    f.get(remote,local)
        if a.command:
            _,out,err=s.exec_command(a.command,timeout=a.timeout)
            print(out.read().decode('utf-8',errors='replace'),end='')
            errors=err.read().decode('utf-8',errors='replace')
            if errors:print(errors,end='')
            code=out.channel.recv_exit_status()
            if code:raise SystemExit(code)
    finally:s.close()
if __name__=='__main__':main()

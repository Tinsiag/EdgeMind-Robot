"""One STOP session, then read-only requests; never configures or arms motors."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from client import Client
from telemetry import TelemetryReceiver


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer",default="192.168.0.2")
    parser.add_argument("--reads",type=int,default=100)
    parser.add_argument("--interval",type=float,default=.05)
    parser.add_argument("--timeout",type=float,default=.25)
    args=parser.parse_args()
    output=ROOT/".local/control-debug"/datetime.now().strftime("%Y%m%d-%H%M%S")
    output.mkdir(parents=True,exist_ok=False)
    receiver=TelemetryReceiver(args.peer)
    client=None
    events=[]
    try:
        client=Client(args.peer,timeout=args.timeout);client.sensors_only=True
        # EMP1 is sent once a second and remains available without a control session.
        time.sleep(1.2)
        for index in range(args.reads+1):
            kind=4 if index==0 else 0x44
            payload=b"" if index==0 else struct.pack("<I",index%12)
            event={"utc":datetime.now(timezone.utc).isoformat(),"kind":kind,"index":index}
            before,_=receiver.read()
            event["fpga_network_before"]=before.network_diagnostics() if before else None
            event["receiver_before"]=receiver.diagnostics()
            started=time.monotonic()
            try:
                reply=client.command(kind,payload,reply=0x80 if index==0 else 0xc4)
                event.update(ok=True,reply_hex=reply.hex())
            except (TimeoutError,OSError) as exc:
                event.update(ok=False,error=str(exc))
            snap,_=receiver.read()
            event.update(elapsed_ms=(time.monotonic()-started)*1000,
                         control=asdict(client.diag),telemetry=asdict(snap) if snap else None,
                         fpga_network=snap.network_diagnostics() if snap else None,
                         receiver=receiver.diagnostics())
            events.append(event)
            with (output/"events.jsonl").open("a",encoding="utf-8") as log:
                log.write(json.dumps(event,ensure_ascii=False)+"\n")
            if index==0 and not event["ok"]:
                # No automatic STOP retries and no reads before session establishment.
                break
            time.sleep(args.interval)
        report={"requests":len(events),"successful":sum(e["ok"] for e in events),
                "failed_indices":[e["index"] for e in events if not e["ok"]],
                "arm_or_motion_commands_sent":False,"initial_stop_sent":True,
                "output":str(output)}
        (output/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
    finally:
        if client:client.close()
        receiver.close()


if __name__=="__main__":main()

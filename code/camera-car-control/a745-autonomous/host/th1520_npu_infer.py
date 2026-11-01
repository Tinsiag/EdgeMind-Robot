#!/usr/bin/env python3
"""Run one TH1520 MBS inference through the vendor NPU test runtime.

The RevyOS image ships the runtime and MBS testbench, but not an ONNX->MBS
converter. Conversion is therefore performed on the development machine with
the matching TH1520 imgdnn toolchain, then the resulting MBS is copied here.
"""
import argparse, os, subprocess, pathlib, json, time

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--model',required=True)
    ap.add_argument('--input',required=True); ap.add_argument('--out',default='/tmp/th1520-npu-out')
    ap.add_argument('--repeat',type=int,default=1); a=ap.parse_args()
    pathlib.Path(a.out).mkdir(parents=True,exist_ok=True)
    cmd=['/usr/share/npu/test/cnn_testbench','--unpacked_in','--unpacked_out','-m',a.model,
         '-o',a.out,'-t','2000','--repeat_count',str(a.repeat),'--task_count','1',a.input]
    t=time.monotonic(); p=subprocess.run(cmd,text=True,capture_output=True); elapsed=time.monotonic()-t
    result={'returncode':p.returncode,'elapsed_s':elapsed,'model':a.model,'input':a.input,
            'output_dir':a.out,'npu_device':os.path.exists('/dev/vha0'),'stdout':p.stdout[-4000:],
            'stderr':p.stderr[-2000:]}
    print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(p.returncode)
if __name__=='__main__': main()

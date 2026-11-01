#!/usr/bin/env python3
"""Time one ONNX model on the TH1520 NPU (SHL) and on CPU, using the model's
own declared input shape. Each provider runs in a fresh child process so a
SIGILL in one backend cannot take the whole benchmark down.

usage: npu_test.py <model.onnx> [provider]
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))


def run_one(path, provider):
    import numpy as np
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4
    t0 = time.time()
    sess = ort.InferenceSession(path, opts, providers=[provider])
    load = time.time() - t0
    inp = sess.get_inputs()[0]
    shape = [d if isinstance(d, int) and d > 0 else 1 for d in inp.shape]
    dtype = np.int8 if 'int8' in (inp.type or '') else (
        np.uint8 if 'uint8' in (inp.type or '') else np.float32)
    x = (np.random.rand(*shape) if dtype == np.float32 else np.zeros(shape)).astype(dtype)
    times = []
    for _ in range(3):
        t = time.time()
        out = sess.run(None, {inp.name: x})[0]
        times.append(time.time() - t)
    return {'provider': provider, 'providers_in_use': sess.get_providers(),
            'load_s': round(load, 2), 'input': inp.name, 'input_shape': shape,
            'input_type': inp.type, 'out_shape': list(out.shape),
            'first_s': round(times[0], 3), 'best_s': round(min(times), 3),
            'fps_est': round(1.0 / min(times), 2) if min(times) > 0 else None}


def main():
    model = sys.argv[1]
    path = model if os.path.isabs(model) else os.path.join(HERE, model)
    if len(sys.argv) > 2:
        print(json.dumps(run_one(path, sys.argv[2])), flush=True)
        return
    for provider in ('ShlExecutionProvider', 'CPUExecutionProvider'):
        p = subprocess.run([sys.executable, '-u', os.path.abspath(__file__), path, provider],
                           capture_output=True, text=True, timeout=1800)
        line = (p.stdout or '').strip().splitlines()
        if p.returncode == 0 and line:
            print(line[-1], flush=True)
        else:
            why = f'exit {p.returncode}'
            if p.returncode == -4:
                why = 'SIGILL (illegal instruction)'
            err = (p.stderr or '').strip().replace('\n', ' ')[-200:]
            print(json.dumps({'provider': provider, 'error': why, 'stderr': err}), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()

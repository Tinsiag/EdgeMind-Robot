#!/usr/bin/env python3
"""Benchmark YOLO inference backends on the Lichee Pi 4A (TH1520).

Tries, for each candidate model: ShlExecutionProvider (NPU) then
CPUExecutionProvider, at several input sizes. Writes JSON to stdout.
Run detached:  setsid nohup ./venv-system/bin/python -u bench_backends.py > bench.log 2>&1 &
"""
import json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = [m for m in ('yolov5n_cpu_fp32.onnx', 'yolov5n_int8.onnx') if os.path.isfile(os.path.join(HERE, m))]
SIZES = [int(s) for s in (sys.argv[1:] or ['320', '640'])]


def bench(path, provider, size, runs=2):
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4
    t0 = time.time()
    sess = ort.InferenceSession(path, opts, providers=[provider])
    load = time.time() - t0
    inp = sess.get_inputs()[0]
    shape = [d if isinstance(d, int) else (1 if i == 0 else size) for i, d in enumerate(inp.shape)]
    if len(shape) == 4:
        shape[2] = shape[3] = size
    dtype = np.float32
    if 'int8' in (inp.type or ''):
        dtype = np.int8
    elif 'uint8' in (inp.type or ''):
        dtype = np.uint8
    x = np.zeros(shape, dtype)
    times = []
    for _ in range(runs):
        t = time.time()
        out = sess.run(None, {inp.name: x})[0]
        times.append(time.time() - t)
    return {'load_s': round(load, 2), 'declared_input': list(inp.shape), 'used_input': shape,
            'input_type': inp.type, 'out_shape': list(out.shape),
            'first_s': round(times[0], 2), 'steady_s': round(min(times), 2),
            'providers': sess.get_providers()}


def main():
    import onnxruntime as ort
    results = {'onnxruntime': ort.__version__, 'available': ort.get_available_providers(),
               'npu_device': os.path.exists('/dev/vha0'),
               'npu_readable': os.access('/dev/vha0', os.R_OK | os.W_OK), 'runs': []}
    for model in MODELS:
        path = os.path.join(HERE, model)
        for provider in ('ShlExecutionProvider', 'CPUExecutionProvider'):
            if provider not in results['available']:
                continue
            for size in SIZES:
                entry = {'model': model, 'provider': provider, 'size': size}
                try:
                    entry.update(bench(path, provider, size))
                except Exception as exc:
                    entry['error'] = str(exc).replace('\n', ' ')[:220]
                results['runs'].append(entry)
                print(json.dumps(entry), flush=True)
    print('RESULT ' + json.dumps(results), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()

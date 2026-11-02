"""Bounded client for the deployed HHB daemon's file-path line protocol.

stdin: absolute path to float32 RGB CHW data, followed by LF (or QUIT).
stdout: READY <runtime input bytes>, then TIME <ms>, DET <n>, n detections,
END. READY describes the quantized runtime tensor, not the float file size.
The daemon opens the file itself; sending tensor bytes to stdin deadlocks.
"""
import math
import os
import select
import subprocess
import tempfile
import time


class NpuDaemon:
    def __init__(self, command, timeout=5.0, start_timeout=20.0, input_bytes=2949120):
        self.command = command
        self.timeout = timeout
        self.start_timeout = start_timeout
        self.input_bytes = input_bytes
        self.proc = None
        self.buffer = bytearray()
        self.tail = []
        self.path = None

    def _line(self, deadline):
        while True:
            if b'\n' in self.buffer:
                line, _, rest = self.buffer.partition(b'\n')
                self.buffer = bytearray(rest)
                value = line.decode('utf-8', 'replace').strip()
                self.tail = (self.tail + [value])[-8:]
                return value
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.proc.stdout], [], [], remaining)[0]:
                raise TimeoutError('NPU response timeout: ' + ' | '.join(self.tail)[-600:])
            chunk = os.read(self.proc.stdout.fileno(), 4096)
            if not chunk:
                raise RuntimeError('NPU daemon EOF: ' + ' | '.join(self.tail)[-600:])
            self.buffer.extend(chunk)
            if len(self.buffer) > 65536:
                raise RuntimeError('NPU daemon output line too long')

    def _send(self, data, deadline):
        pending = memoryview(data)
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [self.proc.stdin], [], remaining)[1]:
                raise TimeoutError('NPU request timeout')
            try:
                written = os.write(self.proc.stdin.fileno(), pending[:4096])
            except BlockingIOError:
                continue
            pending = pending[written:]

    def start(self):
        self.close()
        self.tail = []
        try:
            self.proc = subprocess.Popen(self.command, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         bufsize=0, start_new_session=True)
            os.set_blocking(self.proc.stdin.fileno(), False)
            deadline = time.monotonic() + self.start_timeout
            while not self._line(deadline).startswith('READY '):
                pass
            fd, self.path = tempfile.mkstemp(prefix='fpga-yolo-', suffix='.bin',
                                            dir='/dev/shm' if os.path.isdir('/dev/shm') else None)
            os.close(fd)
        except Exception:
            self.close()
            raise

    def infer(self, blob):
        if len(blob) != self.input_bytes:
            raise ValueError(f'expected {self.input_bytes} float32 input bytes, got {len(blob)}')
        if self.proc is None or self.proc.poll() is not None:
            raise RuntimeError('NPU daemon is not running')
        try:
            with open(self.path, 'wb') as stream:
                stream.write(blob)
            deadline = time.monotonic() + self.timeout
            self._send(os.fsencode(self.path) + b'\n', deadline)
            ms, count, dets = None, None, []
            while True:
                line = self._line(deadline)
                if line.startswith('TIME '):
                    ms = float(line.split()[1])
                elif line.startswith('DET '):
                    count = int(line.split()[1])
                    if not 0 <= count <= 512:
                        raise RuntimeError('invalid NPU detection count')
                elif line == 'END':
                    if count is None or ms is None or len(dets) != count:
                        raise RuntimeError('incomplete NPU detection response')
                    if not math.isfinite(ms) or ms < 0:
                        raise RuntimeError('invalid NPU timing')
                    return ms, dets
                elif count is not None and len(dets) < count:
                    fields = line.split()
                    if len(fields) != 6:
                        raise RuntimeError('invalid NPU detection: ' + line[:160])
                    label = int(fields[0])
                    numbers = tuple(float(x) for x in fields[1:])
                    if not 0 <= label < 80 or not all(math.isfinite(x) for x in numbers):
                        raise RuntimeError('invalid NPU detection values')
                    if not 0 <= numbers[0] <= 1:
                        raise RuntimeError('invalid NPU confidence')
                    dets.append((label, *numbers))
                elif line.startswith(('ERR', 'ERROR', 'FATAL')):
                    raise RuntimeError(line[:600])
        except Exception:
            # A timed-out reply must never become the next frame's result.
            self.close()
            raise

    def close(self):
        proc, self.proc = self.proc, None
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            for pipe in (proc.stdin, proc.stdout):
                if pipe:
                    pipe.close()
        self.buffer.clear()
        if self.path:
            try:
                os.unlink(self.path)
            except FileNotFoundError:
                pass
            self.path = None

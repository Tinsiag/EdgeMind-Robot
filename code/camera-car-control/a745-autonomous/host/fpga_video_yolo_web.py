#!/usr/bin/env python3
"""FPGA EV10 video -> YOLOv5 detection -> browser (MJPEG) on Lichee Pi 4A.

FPGA protocol (a745_video_udp_tx.v): one UDP datagram per 640-pixel line,
payload = 'EV10' | frame_id u32 | line u16 | bytes u16 | RGB565 LE pixels.
The line number is the absolute image row, so lost datagrams only leave a
stale row and never shift the image.

Threads: UDP receive/assemble (never blocks), detector (runs on the newest
complete frame, slow is fine), renderer (overlay newest boxes, JPEG at a
fixed rate). Browser: http://<4a-ip>:8090/   status: /status.json
"""
import http.server, json, os, socket, struct, threading, time
import numpy as np
import cv2

UDP_PORT = int(os.environ.get('VIDEO_UDP_PORT', '6104'))
HTTP_PORT = int(os.environ.get('VIDEO_HTTP_PORT', '8090'))
WIDTH, HEIGHT = 640, 480
MAGIC = b'EV10'
MODEL = os.environ.get('YOLO_MODEL', os.path.expanduser('~/fpga/yolov5n.onnx'))
CONF = float(os.environ.get('YOLO_CONF', '0.30'))
NMS = float(os.environ.get('YOLO_NMS', '0.45'))
STREAM_FPS = float(os.environ.get('STREAM_FPS', '15'))
COMPLETE_RATIO = 0.95  # publish a frame when >=95% of its rows arrived

COCO = ('person bicycle car motorcycle airplane bus train truck boat traffic_light fire_hydrant stop_sign '
        'parking_meter bench bird cat dog horse sheep cow elephant bear zebra giraffe backpack umbrella '
        'handbag tie suitcase frisbee skis snowboard sports_ball kite baseball_bat baseball_glove skateboard '
        'surfboard tennis_racket bottle wine_glass cup fork knife spoon bowl banana apple sandwich orange '
        'broccoli carrot hot_dog pizza donut cake chair couch potted_plant bed dining_table toilet tv laptop '
        'mouse remote keyboard cell_phone microwave oven toaster sink refrigerator book clock vase scissors '
        'teddy_bear hair_drier toothbrush').split()


class Assembler:
    """Collect rows of the current frame_id; publish when nearly complete."""
    def __init__(self):
        self.lock = threading.Condition()
        self.buf = np.zeros((HEIGHT, WIDTH * 2), np.uint8)
        self.rows = np.zeros(HEIGHT, bool)
        self.fid = None
        self.frame = None          # latest complete RGB565 frame (HEIGHT, WIDTH*2)
        self.seq = 0               # increments per published frame
        self.stats = dict(packets=0, bad_packets=0, frames=0, partial_frames=0, missing_rows=0)
        self.fps = 0.0; self._t = time.monotonic(); self._n = 0

    def _publish(self):
        got = int(self.rows.sum())
        if got >= HEIGHT * COMPLETE_RATIO:
            self.stats['missing_rows'] += HEIGHT - got
            with self.lock:
                self.frame = self.buf.copy(); self.seq += 1; self.stats['frames'] += 1
                self.lock.notify_all()
            self._n += 1; now = time.monotonic()
            if now - self._t >= 1.0:
                self.fps = self._n / (now - self._t); self._n = 0; self._t = now
        elif got:
            self.stats['partial_frames'] += 1
        self.rows[:] = False

    def put(self, p):
        if len(p) < 12 or p[:4] != MAGIC:
            self.stats['bad_packets'] += 1; return
        fid, line, size = struct.unpack_from('<IHH', p, 4)
        if size != WIDTH * 2 or len(p) < 12 + size or line >= HEIGHT:
            self.stats['bad_packets'] += 1; return
        self.stats['packets'] += 1
        if fid != self.fid:
            if self.fid is not None and self.rows.any():
                self._publish()
            self.fid = fid
        self.buf[line] = np.frombuffer(p, np.uint8, size, 12)
        self.rows[line] = True
        if line == HEIGHT - 1:
            self._publish()


def rgb565_to_bgr(raw):
    v = raw.view('<u2').reshape(HEIGHT, WIDTH)
    bgr = np.empty((HEIGHT, WIDTH, 3), np.uint8)
    r = (v >> 11) & 31; g = (v >> 5) & 63; b = v & 31
    bgr[..., 2] = (r << 3) | (r >> 2)
    bgr[..., 1] = (g << 2) | (g >> 4)
    bgr[..., 0] = (b << 3) | (b >> 2)
    return bgr


class Detector:
    """YOLO on the newest frame. Supports both head layouts and both backends.

    v5  : output [1, N, 85]  -> cx,cy,w,h,obj,80 class scores
    v5u/v8: output [1, 84, N] -> cx,cy,w,h + 80 class scores (no objectness)

    Backend order is onnxruntime then OpenCV DNN: OpenCV 4.6 on the Lichee Pi
    4A cannot parse fp16 weights or the opset>=13 Split form, while
    onnxruntime 1.14 reads both. Whichever loads first is used.
    """
    def __init__(self, asm):
        self.asm = asm; self.boxes = []; self.ms = 0.0; self.runs = 0; self.error = ''
        self.lock = threading.Lock()
        self.net = None; self.sess = None; self.iname = None
        self.backend = 'none'; self.size = 640
        if os.environ.get('YOLO_ENABLE', '1') != '1':
            self.error = 'disabled by YOLO_ENABLE=0'; return
        if not os.path.isfile(MODEL):
            self.error = f'model not found: {MODEL}'; return
        threads = int(os.environ.get('YOLO_THREADS', '4'))
        try:
            import onnxruntime as ort
            so = ort.SessionOptions(); so.intra_op_num_threads = threads
            providers = [p for p in os.environ.get('YOLO_PROVIDERS', 'CPUExecutionProvider').split(',') if p]
            self.sess = ort.InferenceSession(MODEL, so, providers=providers)
            inp = self.sess.get_inputs()[0]; self.iname = inp.name
            dims = [d for d in inp.shape if isinstance(d, int) and d > 0]
            self.size = dims[-1] if dims else 640
            self.backend = 'onnxruntime:' + ','.join(self.sess.get_providers())
        except Exception as exc:
            self.error = f'onnxruntime: {str(exc)[:160]}'
            try:
                self.net = cv2.dnn.readNetFromONNX(MODEL)
                cv2.setNumThreads(threads)
                self.backend = 'opencv-dnn'
                self.size = int(os.environ.get('YOLO_SIZE', '640'))
                self.error = ''
            except Exception as exc2:
                self.error = f'{self.error} | opencv: {str(exc2)[:160]}'

    def loop(self):
        seen = 0
        while self.sess is not None or self.net is not None:
            with self.asm.lock:
                self.asm.lock.wait_for(lambda: self.asm.seq != seen)
                seen = self.asm.seq; raw = self.asm.frame
            try:
                t = time.monotonic(); boxes = self.detect(rgb565_to_bgr(raw))
                with self.lock:
                    self.boxes = boxes; self.ms = (time.monotonic() - t) * 1000; self.runs += 1
            except Exception as exc:
                with self.lock: self.error = f'inference: {str(exc)[:200]}'
                time.sleep(2)

    def detect(self, bgr):
        n = self.size
        # Letterbox 640x480 into a square n x n, keeping aspect ratio.
        scale = min(n / WIDTH, n / HEIGHT)
        rw, rh = int(round(WIDTH * scale)), int(round(HEIGHT * scale))
        resized = cv2.resize(bgr, (rw, rh))
        canvas = np.full((n, n, 3), 114, np.uint8)
        ox, oy = (n - rw) // 2, (n - rh) // 2
        canvas[oy:oy + rh, ox:ox + rw] = resized
        if self.sess is not None:
            blob = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
            out = self.sess.run(None, {self.iname: blob})[0]
        else:
            self.net.setInput(cv2.dnn.blobFromImage(canvas, 1 / 255.0, (n, n), swapRB=True, crop=False))
            out = self.net.forward()
        out = np.squeeze(out)
        if out.shape[0] in (84, 85) and out.shape[0] < out.shape[1]:
            out = out.T                                   # [84,N] -> [N,84]
        if out.shape[1] == 85:                            # v5: objectness * class
            cls = out[:, 5:].argmax(1)
            score = out[:, 4] * out[np.arange(len(out)), 5 + cls]
        else:                                             # v8/v5u: class score only
            cls = out[:, 4:].argmax(1)
            score = out[np.arange(len(out)), 4 + cls]
        keep = score > CONF
        out, cls, score = out[keep], cls[keep], score[keep]
        if not len(out):
            return []
        xywh = []
        for cx, cy, w, h in out[:, :4]:
            xywh.append([int((cx - w / 2 - ox) / scale), int((cy - h / 2 - oy) / scale),
                         int(w / scale), int(h / scale)])
        idx = cv2.dnn.NMSBoxes(xywh, score.tolist(), CONF, NMS)
        res = []
        for i in np.array(idx).reshape(-1):
            x, y, w, h = xywh[i]
            res.append(dict(cls=COCO[int(cls[i])], score=round(float(score[i]), 3),
                            box=[max(0, x), max(0, y), min(WIDTH - 1, x + w), min(HEIGHT - 1, y + h)]))
        return res


class Renderer:
    def __init__(self, asm, det):
        self.asm = asm; self.det = det; self.jpeg = None; self.cond = threading.Condition()

    def loop(self):
        seen = 0; period = 1.0 / STREAM_FPS
        while True:
            t = time.monotonic()
            with self.asm.lock:
                seq, raw = self.asm.seq, self.asm.frame
            if raw is not None and seq != seen:
                seen = seq; img = rgb565_to_bgr(raw)
                with self.det.lock: boxes = list(self.det.boxes)
                for b in boxes:
                    x1, y1, x2, y2 = b['box']
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(img, f"{b['cls']} {b['score']:.2f}", (x1, max(14, y1 - 4)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                ok, enc = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    with self.cond: self.jpeg = enc.tobytes(); self.cond.notify_all()
            time.sleep(max(0.0, period - (time.monotonic() - t)))


asm = Assembler(); det = Detector(asm); ren = Renderer(asm, det)


def receive():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 * 1024 * 1024)
    s.bind(('', UDP_PORT))
    buf = bytearray(2048)
    while True:
        n = s.recv_into(buf)
        asm.put(memoryview(buf)[:n].tobytes())


PAGE = b'''<!doctype html><html><head><meta charset="utf-8"><title>FPGA Camera YOLO</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;background:#111;color:#ddd;font:14px system-ui,sans-serif}
main{max-width:660px;margin:auto;padding:12px}img{width:100%;border-radius:6px;background:#000}
pre{white-space:pre-wrap;background:#1b1b1b;padding:8px;border-radius:6px}</style></head>
<body><main><h3>FPGA Camera &rarr; Lichee Pi 4A YOLOv5</h3><img src="/video.mjpg">
<pre id="s">...</pre></main><script>
setInterval(()=>fetch('/status.json').then(r=>r.json()).then(j=>{
s.textContent=`video ${j.fps.toFixed(1)} fps | frames ${j.frames} | packets ${j.packets} | bad ${j.bad_packets} | partial ${j.partial_frames}
detector ${j.backend} ${j.infer_ms.toFixed(0)} ms | runs ${j.infer_runs} ${j.error}
`+j.boxes.map(b=>`${b.cls} ${b.score} [${b.box}]`).join('\\n')}),1000)</script></body></html>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path == '/status.json':
            with det.lock:
                st = dict(asm.stats, fps=asm.fps, backend=det.backend, model=os.path.basename(MODEL),
                          infer_size=det.size, infer_ms=det.ms, infer_runs=det.runs,
                          boxes=det.boxes, error=det.error)
            body = json.dumps(st).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
        elif self.path == '/':
            body = PAGE; self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
        elif self.path == '/video.mjpg':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame'); self.end_headers()
            last = None
            try:
                while True:
                    with ren.cond:
                        ren.cond.wait_for(lambda: ren.jpeg is not last, timeout=2)
                        jpg = last = ren.jpeg
                    if jpg:
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(jpg) + jpg + b'\r\n')
            except (BrokenPipeError, ConnectionResetError):
                return
        else:
            self.send_error(404); return
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)


class Server(http.server.ThreadingHTTPServer):
    allow_reuse_address = True; daemon_threads = True


if __name__ == '__main__':
    for fn in (receive, det.loop, ren.loop):
        threading.Thread(target=fn, daemon=True).start()
    print(f'EV10 UDP {UDP_PORT} -> http://0.0.0.0:{HTTP_PORT}/  model={MODEL if det.net else det.error}', flush=True)
    Server(('', HTTP_PORT), Handler).serve_forever()

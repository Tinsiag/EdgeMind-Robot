#!/usr/bin/env python3
"""EV10 receiver with frame checks, RGB565 conversion, optional YOLOv5n and MJPEG web output."""
import http.server, json, os, socket, struct, threading, time
from io import BytesIO

UDP_PORT = 6104
HTTP_PORT = int(os.environ.get('VIDEO_HTTP_PORT', '8090'))
WIDTH, HEIGHT = int(os.environ.get('VIDEO_WIDTH', '128')), int(os.environ.get('VIDEO_HEIGHT', '56'))
MAGIC = b'EV10'
MODEL = os.environ.get('YOLO_MODEL', os.path.expanduser('~/fpga/yolov5n.onnx'))

try:
    import numpy as np
except Exception:
    np = None
try:
    from PIL import Image, ImageDraw
except Exception:
    Image = ImageDraw = None
try:
    import cv2
except Exception:
    cv2 = None
try:
    import onnxruntime as ort
except Exception:
    ort = None
try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.frame_id = None
        self.parts = {}
        self.frame = None
        self.jpeg = None
        self.frames = 0
        self.packets = 0
        self.bad_packets = 0
        self.dropped_frames = 0
        self.last_error = ''
        self.last_boxes = []
        self.model = None
        self.dnn = None
        self.npu = None
        self.npu_input = None
        self.infer_busy = False
        if MODEL and YOLO:
            try:
                self.model = YOLO(MODEL)
            except Exception as exc:
                self.last_error = f'model: {exc}'
        if MODEL and self.model is None and ort is not None and os.path.isfile(MODEL) and os.environ.get('NPU_ENABLE','1') == '1':
            try:
                providers = ['ShlExecutionProvider', 'CPUExecutionProvider']
                self.npu = ort.InferenceSession(MODEL, providers=providers)
                self.npu_input = self.npu.get_inputs()[0].name
                self.last_error = 'ONNXRuntime SHL/NPU backend'
            except Exception as exc:
                self.last_error = f'npu model: {exc}'
        if MODEL and self.model is None and self.npu is None and cv2 is not None and os.path.isfile(MODEL):
            try:
                self.dnn = cv2.dnn.readNetFromONNX(MODEL)
                self.last_error = 'YOLOv5n OpenCV DNN CPU fallback'
            except Exception as exc:
                self.last_error = f'dnn model: {exc}'

    def put(self, packet):
        if len(packet) < 12 or packet[:4] != MAGIC:
            return
        fid, frag, size = struct.unpack_from('<IHH', packet, 4)
        body = packet[12:12 + size]
        if len(body) != size or not size:
            with self.lock:
                self.bad_packets += 1
                self.last_error = 'payload length'
            return
        with self.lock:
            self.packets += 1
            if self.frame_id is not None and fid < self.frame_id:
                self.bad_packets += 1
                return
            if self.frame_id != fid:
                if self.parts:
                    self.dropped_frames += 1
                self.parts = {}
                self.frame_id = fid
            self.parts[frag] = body
            total = sum(len(v) for v in self.parts.values())
            if total < WIDTH * HEIGHT * 2:
                return
            raw = b''.join(self.parts[k] for k in sorted(self.parts))[:WIDTH * HEIGHT * 2]
            if len(raw) != WIDTH * HEIGHT * 2:
                self.bad_packets += 1
                return
            self.frame = raw
            self.frames += 1
            self._render_locked(raw)
            self.parts = {}

    def _render_locked(self, raw):
        if np is not None:
            a = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 2)
            v = a[:, 0].astype(np.uint16) | (a[:, 1].astype(np.uint16) << 8)
            bgr = np.empty((HEIGHT * WIDTH, 3), dtype=np.uint8)
            bgr[:, 2] = ((v >> 11) * 255 // 31).astype(np.uint8)
            bgr[:, 1] = (((v >> 5) & 63) * 255 // 63).astype(np.uint8)
            bgr[:, 0] = ((v & 31) * 255 // 31).astype(np.uint8)
            bgr = bgr.reshape(HEIGHT, WIDTH, 3)
            boxes = []
            if self.model is not None:
                try:
                    result = self.model.predict(bgr, imgsz=384, verbose=False)[0]
                    for box in result.boxes:
                        x1, y1, x2, y2 = [int(x) for x in box.xyxy[0].tolist()]
                        score = float(box.conf[0]); cls = int(box.cls[0])
                        boxes.append((x1, y1, x2, y2, score, cls))
                        if cv2 is not None:
                            cv2.rectangle(bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(bgr, f'{cls}:{score:.2f}', (x1, max(15, y1 - 4)),
                                        cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 0), 1)
                except Exception as exc:
                    self.last_error = f'inference: {exc}'
            elif self.npu is not None:
                if not self.infer_busy:
                    self.infer_busy = True
                    threading.Thread(target=self._infer_npu, args=(bgr.copy(),), daemon=True).start()
            elif self.dnn is not None:
                # Keep HTTP and UDP responsive while the RISC-V CPU runs DNN.
                # The current frame is published immediately; the worker adds
                # boxes to later frames when inference completes.
                if not self.infer_busy:
                    self.infer_busy = True
                    base = bgr.copy()
                    threading.Thread(target=self._infer_dnn, args=(base,), daemon=True).start()
            self.last_boxes = boxes
            if cv2 is not None:
                ok, enc = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                self.jpeg = enc.tobytes() if ok else None
            return
        if Image is None:
            self.last_error = 'need numpy+opencv or Pillow'
            return
        im = Image.new('RGB', (WIDTH, HEIGHT)); px = im.load()
        for i in range(WIDTH * HEIGHT):
            v = raw[2 * i] | (raw[2 * i + 1] << 8)
            px[i % WIDTH, i // WIDTH] = ((v >> 8) & 248, (v >> 3) & 252, (v << 3) & 248)
        out = BytesIO(); im.save(out, 'JPEG', quality=80); self.jpeg = out.getvalue()

    def _infer_dnn(self, bgr):
        try:
            inp = cv2.dnn.blobFromImage(bgr, 1 / 255.0, (640, 384), swapRB=True, crop=False)
            self.dnn.setInput(inp); out = self.dnn.forward(); rows = out.reshape(-1, out.shape[-1])
            boxes0, scores0, classes0 = [], [], []; sx, sy = WIDTH / 640.0, HEIGHT / 384.0
            for row in rows:
                obj = float(row[4])
                if obj < 0.25: continue
                cls = int(np.argmax(row[5:])); score = obj * float(row[5 + cls])
                if score < 0.30: continue
                cx, cy, w, h = row[:4]; x, y = int((cx - w / 2) * sx), int((cy - h / 2) * sy)
                boxes0.append([x, y, int(w * sx), int(h * sy)]); scores0.append(score); classes0.append(cls)
            keep = cv2.dnn.NMSBoxes(boxes0, scores0, 0.30, 0.45); boxes = []
            for k in keep:
                i = int(k); x, y, w, h = boxes0[i]; x1, y1 = max(0, x), max(0, y)
                x2, y2 = min(WIDTH - 1, x + w), min(HEIGHT - 1, y + h)
                boxes.append((x1, y1, x2, y2, scores0[i], classes0[i]))
                cv2.rectangle(bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(bgr, f'{classes0[i]}:{scores0[i]:.2f}', (x1, max(15, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 0), 1)
            ok, enc = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            with self.lock:
                if ok: self.jpeg = enc.tobytes()
                self.last_boxes = boxes
        except Exception as exc:
            with self.lock: self.last_error = f'dnn inference: {exc}'
        finally:
            self.infer_busy = False

    def _infer_npu(self, bgr):
        try:
            inp = cv2.resize(bgr, (640, 384)).astype('float32')[:, :, ::-1] / 255.0
            inp = np.transpose(inp, (2, 0, 1))[None, ...]
            out = self.npu.run(None, {self.npu_input: inp})[0]
            rows = out.reshape(-1, out.shape[-1]); boxes0=[]; scores0=[]; classes0=[]
            for row in rows:
                if len(row) < 6: continue
                obj=float(row[4]); cls=int(np.argmax(row[5:])); score=obj*float(row[5+cls])
                if score < 0.30: continue
                cx,cy,w,h=row[:4]; sx,sy=WIDTH/640.0,HEIGHT/384.0
                boxes0.append([int((cx-w/2)*sx),int((cy-h/2)*sy),int(w*sx),int(h*sy)])
                scores0.append(score); classes0.append(cls)
            keep=cv2.dnn.NMSBoxes(boxes0,scores0,0.30,0.45); boxes=[]
            for k in keep:
                i=int(k); x,y,w,h=boxes0[i]; x1,y1=max(0,x),max(0,y); x2,y2=min(WIDTH-1,x+w),min(HEIGHT-1,y+h)
                boxes.append((x1,y1,x2,y2,scores0[i],classes0[i])); cv2.rectangle(bgr,(x1,y1),(x2,y2),(0,255,0),1)
                cv2.putText(bgr,f'{classes0[i]}:{scores0[i]:.2f}',(x1,max(10,y1-2)),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,255,0),1)
            ok,enc=cv2.imencode('.jpg',bgr,[int(cv2.IMWRITE_JPEG_QUALITY),80])
            with self.lock:
                if ok:self.jpeg=enc.tobytes()
                self.last_boxes=boxes
        except Exception as exc:
            with self.lock:self.last_error=f'npu inference: {exc}'
        finally:self.infer_busy=False

    def status(self):
        with self.lock:
            backend = 'ultralytics-cpu' if self.model is not None else ('shl-npu' if self.npu is not None else ('opencv-dnn-cpu' if self.dnn is not None else 'none'))
            return {'frames': self.frames, 'packets': self.packets, 'bad_packets': self.bad_packets,
                    'dropped_frames': self.dropped_frames, 'model': bool(self.model or self.dnn),
                    'backend': backend, 'npu_device': os.path.exists('/dev/vha0'),
                    'boxes': self.last_boxes, 'error': self.last_error}


store = Store()


def receive():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    sock.bind(('', UDP_PORT))
    while True:
        try:
            store.put(sock.recvfrom(4096)[0])
        except OSError:
            return


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/status.json':
            body = json.dumps(store.status()).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.path == '/':
            body = b'<html><body><h3>FPGA Camera + YOLOv5n</h3><img src="/video.mjpg"><pre id="s"></pre><script>setInterval(()=>fetch("/status.json").then(r=>r.text()).then(t=>s.textContent=t),1000)</script></body></html>'
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.path != '/video.mjpg':
            self.send_error(404); return
        self.send_response(200); self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame'); self.end_headers()
        while True:
            with store.lock: jpg = store.jpeg
            if jpg:
                self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(jpg)).encode() + b'\r\n\r\n' + jpg + b'\r\n'); self.wfile.flush()
            time.sleep(.03)

class ReuseServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    threading.Thread(target=receive, daemon=True).start()
    ReuseServer(('', HTTP_PORT), Handler).serve_forever()

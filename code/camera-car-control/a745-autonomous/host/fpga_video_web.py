#!/usr/bin/env python3
"""Receive FPGA EV10 RGB565 packets and expose an MJPEG browser stream."""
import http.server, socket, struct, threading, time
from http import HTTPStatus
from PIL import Image
from io import BytesIO

UDP_PORT=6104; HTTP_PORT=8080; WIDTH=640; HEIGHT=480; MAGIC=b'EV10'
class Store:
 def __init__(self): self.lock=threading.Lock(); self.frame=None; self.parts={}; self.frame_id=None; self.total=0
 def put(self,p):
  if len(p)<12 or p[0:4]!=MAGIC:return
  fid,seq,size=struct.unpack_from('<IHH',p,4); body=p[12:12+size]
  with self.lock:
   if self.frame_id!=fid:self.parts={};self.frame_id=fid
   self.parts[seq]=body
   if len(self.parts)*1280>=WIDTH*HEIGHT*2:
    raw=b''.join(self.parts[k] for k in sorted(self.parts))[:WIDTH*HEIGHT*2]
    if len(raw)==WIDTH*HEIGHT*2:self.frame=raw;self.total+=1
 def jpeg(self):
  with self.lock: raw=self.frame
  if raw is None:return None
  rgb=bytearray(WIDTH*HEIGHT*3)
  for i in range(WIDTH*HEIGHT):
   v=raw[2*i]|(raw[2*i+1]<<8); rgb[3*i]=(v>>8)&248; rgb[3*i+1]=(v>>3)&252; rgb[3*i+2]=(v<<3)&248
  im=Image.frombytes('RGB',(WIDTH,HEIGHT),bytes(rgb)); out=BytesIO(); im.save(out,'JPEG',quality=80); return out.getvalue()
store=Store()
def rx():
 s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,8*1024*1024);s.bind(('',UDP_PORT))
 while True:
  try:store.put(s.recvfrom(2048)[0])
  except OSError:break
class H(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path=='/':
   b=b'<html><body><h3>FPGA Camera</h3><img src="/video.mjpg"></body></html>'
   self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  if self.path!='/video.mjpg':self.send_error(HTTPStatus.NOT_FOUND);return
  self.send_response(200);self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame');self.end_headers()
  while True:
   jpg=store.jpeg()
   if jpg:
    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(jpg)).encode()+b'\r\n\r\n'+jpg+b'\r\n');self.wfile.flush()
   time.sleep(.03)
if __name__=='__main__':
 threading.Thread(target=rx,daemon=True).start();print(f'http://0.0.0.0:{HTTP_PORT}/');http.server.ThreadingHTTPServer(('',HTTP_PORT),H).serve_forever()

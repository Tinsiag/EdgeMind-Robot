"""Receive-only A745 status: no command client, configuration, ARM or heartbeat."""
import socket, struct, threading, time

def decode_status(data):
    if len(data)!=112 or data[:4]!=b'EMS1' or struct.unpack_from('<HH',data,4)!=(1,112):
        raise ValueError('Invalid EMS1 datagram')
    flags=struct.unpack_from('<H',data,20)[0]
    revision=struct.unpack_from('<I',data,16)[0]
    reg,expected,value=(struct.unpack_from('<I',data,68)[0]>>16),data[69],data[68]
    return dict(seq=struct.unpack_from('<I',data,8)[0],ms=struct.unpack_from('<I',data,12)[0],revision=revision,flags=flags,
        state=data[22],faults=struct.unpack_from('<H',data,24)[0],armed=bool(flags&32),
        targets=struct.unpack_from('<ii',data,28),speeds=struct.unpack_from('<ii',data,36),
        counts=struct.unpack_from('<ii',data,44),yaw=struct.unpack_from('<h',data,52)[0]*180/32768,
        ranges=struct.unpack_from('<HHH',data,58),camera_error=data[98],camera_phase=(data[99]>>3)&15,
        camera_attempt=data[99]&7,camera_register=reg,camera_expected=expected,camera_value=value,
        video_frames=struct.unpack_from('<I',data,80)[0],frame_ready=bool(flags&512),
        ddr_ready=bool(flags&256),video_error=bool(flags&2048),camera_ready=(data[99]>>3)&15==11,
        rear=struct.unpack_from('<H',data,104)[0],left_clear=bool(data[106]&1),
        right_clear=bool(data[106]&2),scan_sequence=data[107],
        imu_valid=bool(flags&1),gyro_valid=bool(flags&2),
        encoder_no_pulse_left=bool(flags&4) if revision>=74507 else None,
        encoder_no_pulse_right=bool(flags&128) if revision>=74507 else None,
        imu_time_ms=struct.unpack_from('<I',data,64)[0],imu_errors=struct.unpack_from('<I',data,76)[0],
        imu_seq=struct.unpack_from('<I',data,100)[0],imu_fault_sources=data[26],imu_fault_valid_flags=data[27])

def decode_attitude(data):
    if len(data)!=48 or data[:4]!=b'EMF1' or struct.unpack_from('<HH',data,4)!=(1,48) or data[16]!=1:
        raise ValueError('Invalid EMF1 datagram')
    roll,pitch=struct.unpack_from('<hh',data,20)
    return dict(roll=roll*180/32768,pitch=pitch*180/32768,tilt_valid=bool(data[24]&1),
        cpu_alive=bool(data[41]&2),cpu_fault=bool(data[41]&4),cpu_progress=struct.unpack_from('<I',data,37)[0],
        imu_diagnostic=struct.unpack_from('<I',data,32)[0],imu_fault_sources=data[42],imu_fault_valid_flags=data[43],
        fault_roll=struct.unpack_from('<h',data,44)[0]*180/32768,
        fault_pitch=struct.unpack_from('<h',data,46)[0]*180/32768)

class Receiver:
    def __init__(self,peer='192.168.0.2',port=6103):
        self.peer=peer;self.status=None;self.attitude=None;self.updated=None;self.errors=0;self.radars=0
        self.closed=threading.Event();self.lock=threading.Lock()
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024*1024)
            self.socket.bind(('',port));self.socket.settimeout(.1)
        except BaseException:
            self.socket.close();raise
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        while not self.closed.is_set():
            try:data,source=self.socket.recvfrom(2048)
            except socket.timeout:continue
            except OSError:return
            if source!=(self.peer,6103):continue
            try:
                with self.lock:
                    if data[:4]==b'EMS1':self.status=decode_status(data);self.updated=time.monotonic()
                    elif data[:4]==b'EMF1':self.attitude=decode_attitude(data)
                    elif len(data)==64 and data[:4]==b'EML1':self.radars+=1
            except ValueError:self.errors+=1
    def read(self):
        with self.lock:
            fresh=self.updated is not None and time.monotonic()-self.updated<.6
            return (dict(self.status) if self.status and fresh else None,dict(self.attitude) if self.attitude and fresh else None)
    def close(self):
        self.closed.set();self.socket.close();self.thread.join(timeout=1)

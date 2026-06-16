import socket
import subprocess
import time
import cv2
import numpy as np

print("Starting gstreamer...")
p = subprocess.Popen("D:\\Coding\\msvc_x86_64\\bin\\gst-launch-1.0.exe -q videotestsrc num-buffers=10 ! videoconvert ! jpegenc ! tcpserversink host=127.0.0.1 port=5005", shell=True)
time.sleep(1)

print("Connecting...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("127.0.0.1", 5005))
print("Connected!")

_bytes = b''
for _ in range(50):
    _bytes += s.recv(65536)
    a = _bytes.find(b'\xff\xd8')
    if a != -1:
        b = _bytes.find(b'\xff\xd9', a + 2)
        if b != -1:
            jpg = _bytes[a:b+2]
            print("Found complete JPEG, size:", len(jpg))
            img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                print("Decoded image shape:", img.shape)
                break

p.terminate()

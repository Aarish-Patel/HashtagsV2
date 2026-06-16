import subprocess
import time
import cv2
import numpy as np
import threading

def test_raw_pipeline():
    print("Starting raw GStreamer pipeline...")
    # Read 10 frames from videotestsrc
    cmd = "D:\\Coding\\msvc_x86_64\\bin\\gst-launch-1.0.exe -q videotestsrc num-buffers=10 ! videoconvert ! video/x-raw,format=BGR,width=640,height=480 ! fdsink fd=1"
    
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True, bufsize=1048576)
    
    frame_size = 640 * 480 * 3
    frames_read = 0
    
    while frames_read < 5:
        # Read exactly one frame
        raw_bytes = b''
        while len(raw_bytes) < frame_size:
            chunk = p.stdout.read(frame_size - len(raw_bytes))
            if not chunk:
                break
            raw_bytes += chunk
            
        if len(raw_bytes) != frame_size:
            print("Failed to read full frame")
            break
            
        img = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((480, 640, 3))
        print("Successfully read raw frame! Shape:", img.shape, "Mean color:", img.mean())
        frames_read += 1

    p.terminate()

test_raw_pipeline()

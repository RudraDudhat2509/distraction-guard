"""Distraction Guard main loop. Runs on the Jetson Nano (JetPack 4.6, Python 3.6).

Camera -> SSD-MobileNet-v2 -> 3-second rule -> 'G'/'R' over USB serial to the Arduino.
Also writes one CSV row per frame for tests A to E.

Camera note: jetson-utils rotates a CSI camera by 180 degrees by default (and "--input-flip=none"
does not turn that off), so the camera board is mounted upside down and the picture comes out upright.
"""
import argparse
import csv
import json
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2
import jetson_inference
import jetson_utils
import serial

from guard_rule import PhoneRule

parser = argparse.ArgumentParser()
parser.add_argument("--camera", default="csi://0")
parser.add_argument("--port", default="/dev/ttyACM0")
parser.add_argument("--threshold", type=float, default=0.2)
parser.add_argument("--precision", default="FP16", help="FP16 or FP32, for test A")
parser.add_argument("--flip", default="", help="override the camera rotation, e.g. clockwise, rotate-180")
parser.add_argument("--width", type=int, default=1280)
parser.add_argument("--height", type=int, default=720)
parser.add_argument("--display", action="store_true", help="show the live window on the Jetson's monitor")
parser.add_argument("--stream", action="store_true", help="live video in a browser at http://<jetson-ip>:8000")
parser.add_argument("--log", default="log.csv")
parser.add_argument("--verbose", action="store_true", help="print a live status line twice a second")
args = parser.parse_args()

net = jetson_inference.detectNet(
    argv=["--network=ssd-mobilenet-v2", "--precision=" + args.precision,
          "--threshold=" + str(args.threshold)])
cam_args = ["guard", "--input-width=%d" % args.width, "--input-height=%d" % args.height]
if args.flip:
    cam_args.append("--input-flip=" + args.flip)
camera = jetson_utils.videoSource(args.camera, argv=cam_args)
display = jetson_utils.videoOutput("display://0") if args.display else None
show = args.stream or args.display
font = jetson_utils.cudaFont() if show else None

# --- browser video: the newest annotated frame as a JPEG, served as a never-ending image ---
latest = {"jpg": None}
status = {"person": 0, "phone": 0, "together": 0.0, "hold": 3.0, "alert": 0, "fps": 0.0, "t": 0.0}


class Viewer(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/status":
            body = json.dumps(status).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/video":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            sent = None
            try:
                while True:
                    jpg = latest["jpg"]
                    if jpg is None or jpg is sent:
                        time.sleep(0.02)
                        continue
                    sent = jpg
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg))
                    self.wfile.write(jpg + b"\r\n")
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        else:
            page = (b"<html><head><title>Distraction Guard</title></head>"
                    b"<body style='margin:0;background:#111'><img src='/video' style='width:100%'></body></html>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)


class ThreadedServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


if args.stream:
    threading.Thread(target=ThreadedServer(("0.0.0.0", 8000), Viewer).serve_forever, daemon=True).start()
    print("live video: http://192.168.55.1:8000", flush=True)
    small = jetson_utils.cudaAllocMapped(width=640, height=360, format="rgb8")

arduino = serial.Serial(args.port, 9600)
time.sleep(2)  # the Uno resets when the port opens
arduino.write(b"G")

rule = PhoneRule()
alert = False
last = time.time()
last_print = 0.0
frame_no = 0

with open(args.log, "w", newline="") as f:
    log = csv.writer(f)
    log.writerow(["t", "dt_s", "net_fps", "person", "phone", "together_s", "alert"])
    t0 = last
    while True:
        img = camera.Capture()
        if img is None:
            continue
        detections = net.Detect(img, overlay="box,labels,conf" if show else "none")
        names = set(net.GetClassDesc(d.ClassID) for d in detections)
        person, phone = "person" in names, "cell phone" in names

        now = time.time()
        dt, last = now - last, now
        new_alert = rule.update(person, phone, dt)
        if new_alert != alert:
            alert = new_alert
            arduino.write(b"R" if alert else b"G")

        log.writerow(["%.3f" % (now - t0), "%.4f" % dt, "%.1f" % net.GetNetworkFPS(),
                      int(person), int(phone), "%.2f" % rule.together, int(alert)])
        status.update(person=int(person), phone=int(phone), together=round(rule.together, 2),
                      hold=rule.hold, alert=int(alert), fps=round(net.GetNetworkFPS(), 1),
                      t=round(now - t0, 1))
        if args.verbose and now - last_print >= 0.5:
            last_print = now
            print("t=%6.1fs  fps=%4.1f  person=%d phone=%d  together=%4.1fs  LED=%s" % (
                now - t0, net.GetNetworkFPS(), person, phone, rule.together,
                "RED + buzzer" if alert else "green"), flush=True)

        if show:
            label = "RED: PHONE" if alert else "GREEN: ok"
            font.OverlayText(img, img.width, img.height, "%s | person %d phone %d | together %.1fs | %.0f FPS" % (
                label, person, phone, rule.together, net.GetNetworkFPS()), 8, 8,
                font.White, font.Red if alert else font.Gray40)
        if args.stream:
            frame_no += 1
            if frame_no % 2 == 0:  # about 13 frames a second is plenty to watch
                jetson_utils.cudaResize(img, small)
                jetson_utils.cudaDeviceSynchronize()
                ok, buf = cv2.imencode(".jpg", jetson_utils.cudaToNumpy(small)[:, :, ::-1],
                                       [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok:
                    latest["jpg"] = buf.tobytes()
        if display:
            display.Render(img)
            if not display.IsStreaming():
                break

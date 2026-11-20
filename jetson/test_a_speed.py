"""Test A: detector speed at one precision. Run on the Jetson with run_guard.py stopped.
usage: python3 test_a_speed.py FP16     then     python3 test_a_speed.py FP32
Writes results/speed_<precision>.json. The first FP32 run builds its GPU engine (several minutes).
"""
import glob
import json
import os
import statistics
import sys
import time

import jetson_inference
import jetson_utils

precision = sys.argv[1].upper()
FRAMES = 500       # detector calls on one still frame (pure detector speed, no camera limit)
LIVE_SECONDS = 20  # then a live camera loop (what the guard really achieves)

net = jetson_inference.detectNet(argv=["x", "--network=ssd-mobilenet-v2", "--precision=" + precision,
                                       "--threshold=0.2"])
engines = sorted(os.path.basename(p) for p in glob.glob(
    "/usr/local/bin/networks/SSD-Mobilenet-v2/*.engine"))

camera = jetson_utils.videoSource("csi://0", argv=["x", "--input-width=1280", "--input-height=720"])
for _ in range(45):  # let auto-exposure settle
    frame = camera.Capture()

for _ in range(30):  # warm-up
    net.Detect(frame, overlay="none")

call_ms, net_ms = [], []
for _ in range(FRAMES):
    t = time.perf_counter()
    net.Detect(frame, overlay="none")
    call_ms.append((time.perf_counter() - t) * 1000)
    net_ms.append(net.GetNetworkTime())

frames, start = 0, time.time()
while time.time() - start < LIVE_SECONDS:
    img = camera.Capture()
    if img is None:
        continue
    net.Detect(img, overlay="none")
    frames += 1
live_fps = frames / (time.time() - start)

result = {
    "precision": precision,
    "engine_files_present": engines,
    "still_frame_calls": FRAMES,
    "detect_call_ms_mean": round(statistics.mean(call_ms), 2),
    "detect_call_ms_median": round(statistics.median(call_ms), 2),
    "detect_call_ms_p95": round(sorted(call_ms)[int(0.95 * FRAMES)], 2),
    "detector_fps_from_calls": round(1000 / statistics.mean(call_ms), 1),
    "tensorrt_network_ms_mean": round(statistics.mean(net_ms), 2),
    "live_camera_loop_fps": round(live_fps, 1),
}
os.makedirs("results", exist_ok=True)
with open("results/speed_%s.json" % precision, "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))

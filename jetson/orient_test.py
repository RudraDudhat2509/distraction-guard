"""Try one camera orientation for a few seconds and count person / phone detections.
usage: python3 orient_test.py FLIP     (none, clockwise, counterclockwise, rotate-180)"""
import sys
import time

import numpy as np

import jetson_inference
import jetson_utils

flip = sys.argv[1]
secs = 6
sw180 = flip == "sw180"  # rotate 180 in software; the camera's own rotate-180 crashes on this JetPack
thresh = sys.argv[2] if len(sys.argv) > 2 else "0.5"
net = jetson_inference.detectNet(argv=["--network=ssd-mobilenet-v2", "--threshold=" + thresh])
cam = jetson_utils.videoSource("csi://0", argv=["--input-flip=" + ("none" if sw180 else flip)])

frames = person = phone = both = 0
best_phone = 0.0
saved = False
start = time.time()
while time.time() - start < secs:
    img = cam.Capture()
    if img is None:
        continue
    if sw180:
        jetson_utils.cudaDeviceSynchronize()
        img = jetson_utils.cudaFromNumpy(np.ascontiguousarray(jetson_utils.cudaToNumpy(img)[::-1, ::-1]))
    dets = net.Detect(img, overlay="box,labels,conf")
    names = set(net.GetClassDesc(d.ClassID) for d in dets)
    for d in dets:
        if net.GetClassDesc(d.ClassID) == "cell phone":
            best_phone = max(best_phone, d.Confidence)
    frames += 1
    person += "person" in names
    phone += "cell phone" in names
    both += "person" in names and "cell phone" in names
    if frames == 60 and not saved:
        jetson_utils.saveImage("orient_%s.jpg" % flip, img)
        saved = True

print("%-17s thr=%s frames=%d person=%d phone=%d both=%d best_phone_conf=%.2f" % (flip, thresh, frames, person, phone, both, best_phone))

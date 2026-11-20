# Distraction Guard

A small desk box that watches for a phone. A camera feeds a Jetson Nano, the Nano looks for a person and a phone in every frame, and an Arduino turns the result into lights and a buzzer. Green is fine. Red plus a beep means phone.

AI Lab project, IIT Bhilai. Team: Vatsal Yadav (lead), Rudra Dudhat, S Aparajith, Kanishk Nadeshwar.

## How it works

```
IMX219 camera -> Jetson Nano -> USB serial ('G' or 'R') -> Arduino Uno -> green LED, or red LED + buzzer
                    |
                    +-> video + status over the USB network -> laptop dashboard
```

- **Detection:** SSD-MobileNet-v2 (trained on COCO, from NVIDIA's jetson-inference), run on the Nano's GPU through TensorRT. We did not train anything.
- **Rule:** red turns on when a person and a phone are seen together for 1.0 s. A dropout of up to 1.5 s is forgiven and its time still counts.
- **Output:** the Jetson sends one byte to the Arduino only when the state changes. The Arduino drives the pins.

## Hardware

- Jetson Nano 4 GB developer kit, 5 V 4 A barrel supply
- IMX219 camera (160 degree lens) on the CSI port, mounted upside down
- Arduino Uno, plugged into a Jetson USB port
- Green LED on D8, red LED on D9, each through a 330 ohm resistor to GND
- Passive buzzer module: signal to D10, middle pin to 5 V, minus to GND
- Laptop, connected to the Jetson's USB-C port (shows up as a network at 192.168.55.1)

## Files

| Path | What it is |
|---|---|
| `arduino/led_controller/led_controller.ino` | Arduino sketch: reads `R` or `G`, sets the pins |
| `jetson/guard_rule.py` | The phone rule (pure Python, no Jetson imports) |
| `jetson/test_guard_rule.py` | 8 unit tests for the rule |
| `jetson/run_guard.py` | Main loop: camera, detector, rule, serial, log, live video |
| `jetson/test_a_speed.py` | Test A: detector speed at FP16 and FP32 |
| `jetson/orient_test.py` | Quick camera orientation and threshold check |
| `jetson/start.sh`, `stop.sh` | Start and stop the main loop on the Jetson |
| `dashboard/dashboard.py` | Laptop window: video, LED state, timer, alert log |
| `launch_demo.ps1` | One-click start from the laptop |
| `results/` | Speed results and the recorded runs used to tune the rule |

## Run it

On the laptop, with the Jetson powered, the USB-C cable connected and the Uno plugged into the Jetson:

```
.\launch_demo.ps1
```

By hand, on the Jetson (`~/guard`):

```
python3 run_guard.py --stream --verbose
```

Then open `http://192.168.55.1:8000` in a browser, or run `python dashboard/dashboard.py` on the laptop.

Flash the Arduino:

```
arduino-cli upload -p COM3 --fqbn arduino:avr:uno arduino/led_controller
```

Needs JetPack 4.6, jetson-inference built from source, and `python3-serial` on the Jetson.

## Results

**Test A, detector speed** (500 calls on one frame, Jetson Nano, SSD-MobileNet-v2):

| | FP16 | FP32 |
|---|---|---|
| Time per frame | 38.3 ms | 50.4 ms |
| Detector speed | 26.1 fps | 19.8 fps |
| Whole program with live camera | 23.3 fps | 18.2 fps |

FP16 is 1.32 times faster.

**Rule tuning.** With the proposal's 3 s hold, the red light took far too long, because the detector only sees the phone in some frames (4% to 53% of frames during a hold in our recordings). I replayed a recorded run (`results/logs/log_live2.csv`: 4 real holds, 2 quick 0.4 s passes of the phone) through different rules:

| Rule | Real holds that alerted | Quick passes ignored |
|---|---|---|
| 5 consecutive frames | 2 of 4 | yes |
| 10 consecutive frames | 1 of 4 | yes |
| 1.0 s hold, 1.5 s dropout forgiven (used) | 4 of 4 | yes |

Detection confidence threshold is 0.2, because at 0.5 the phone was almost never reported.

## Things worth knowing

- The Python API of this jetson-inference version ignores `--precision` and always picks FP16. We patched three lines in `detectNet.cpp` to read it, so FP32 could be measured.
- A CSI camera is rotated 180 degrees by default, and `--input-flip=none` does not turn that off, so the camera board is mounted upside down.
- The WebRTC stream crashes on this JetPack's GStreamer 1.14, so the live video is plain MJPEG over HTTP on port 8000.
- The Nano boots from its built-in 16 GB storage, not an SD card.

## Not done

Tests C, D and E from the proposal (delay, a 50-trial accuracy count, lighting and distance and angle) were not run, and the Raspberry Pi comparison was skipped. The main weakness is phone recall: a phone is small in a wide-angle picture squeezed to 300 x 300, so the detector often misses it for a second or two.

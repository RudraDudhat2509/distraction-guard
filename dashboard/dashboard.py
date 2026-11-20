"""Distraction Guard dashboard. Runs on the laptop and shows what the Jetson is doing:
live video, a big GREEN/RED state, the 3-second timer, and a log of alerts.

usage: python dashboard.py            (needs run_guard.py --stream running on the Jetson)
       python dashboard.py --selftest (fetch one frame and one status, print, exit)
"""
import io
import json
import sys
import threading
import time
import tkinter as tk
import urllib.request

from PIL import Image, ImageTk

BASE = "http://192.168.55.1:8000"

BG, PANEL, GOLD, INK, DIM = "#0d0d0f", "#17171b", "#c9a24a", "#e8e3d6", "#7d786b"
GREEN, GREEN_OFF, RED, RED_OFF = "#2fb36f", "#14301f", "#e0392f", "#3a1613"

shared = {"frame": None, "status": None, "ok": False}


def video_loop():
    while True:
        try:
            resp = urllib.request.urlopen(BASE + "/video", timeout=10)
            buf = b""
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                buf += chunk
                a = buf.find(b"\xff\xd8")
                b = buf.find(b"\xff\xd9", a + 2) if a >= 0 else -1
                if a >= 0 and b >= 0:
                    shared["frame"] = Image.open(io.BytesIO(buf[a:b + 2])).convert("RGB")
                    buf = buf[b + 2:]
        except Exception:
            shared["frame"] = None
            time.sleep(1)


def status_loop():
    while True:
        try:
            with urllib.request.urlopen(BASE + "/status", timeout=3) as r:
                shared["status"] = json.loads(r.read().decode())
                shared["ok"] = True
        except Exception:
            shared["ok"] = False
        time.sleep(0.12)


if "--selftest" in sys.argv:
    threading.Thread(target=video_loop, daemon=True).start()
    threading.Thread(target=status_loop, daemon=True).start()
    time.sleep(4)
    f = shared["frame"]
    print("status:", shared["status"])
    print("frame:", f.size if f else None)
    sys.exit(0 if (f and shared["status"]) else 1)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Distraction Guard")
        root.configure(bg=BG)
        root.geometry("1180x640")
        root.minsize(980, 560)

        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=20, pady=(14, 6))
        tk.Label(head, text="DISTRACTION GUARD", bg=BG, fg=GOLD, font=("Georgia", 20, "bold")).pack(side="left")
        self.conn = tk.Label(head, text="connecting...", bg=BG, fg=DIM, font=("Segoe UI", 10))
        self.conn.pack(side="right")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # fixed holder: its size comes from the window, never from the picture inside it
        self.holder = tk.Frame(body, bg=PANEL)
        self.holder.pack(side="left", fill="both", expand=True)
        self.holder.pack_propagate(False)
        self.video = tk.Label(self.holder, bg=PANEL, fg=DIM, text="waiting for video...", font=("Segoe UI", 12))
        self.video.place(relx=0.5, rely=0.5, anchor="center")

        side = tk.Frame(body, bg=BG, width=330)
        side.pack(side="right", fill="y", padx=(16, 0))
        side.pack_propagate(False)

        # the two hardware LEDs, mirrored
        led = tk.Frame(side, bg=PANEL)
        led.pack(fill="x")
        self.canvas = tk.Canvas(led, width=330, height=120, bg=PANEL, highlightthickness=0)
        self.canvas.pack()
        self.green = self.canvas.create_oval(60, 20, 120, 80, fill=GREEN_OFF, outline=GOLD, width=2)
        self.red = self.canvas.create_oval(210, 20, 270, 80, fill=RED_OFF, outline=GOLD, width=2)
        self.canvas.create_text(90, 98, text="GREEN LED", fill=DIM, font=("Segoe UI", 9))
        self.canvas.create_text(240, 98, text="RED LED + BUZZER", fill=DIM, font=("Segoe UI", 9))

        self.banner = tk.Label(side, text="ALL FINE", bg=GREEN, fg="white", font=("Segoe UI", 20, "bold"), pady=10)
        self.banner.pack(fill="x", pady=(10, 10))

        rows = tk.Frame(side, bg=PANEL)
        rows.pack(fill="x")
        self.person = self._row(rows, "Person in view")
        self.phone = self._row(rows, "Phone in view")

        tk.Label(side, text="Seen together (needs 3 s)", bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 2))
        self.bar = tk.Canvas(side, height=22, bg=PANEL, highlightthickness=0)
        self.bar.pack(fill="x")
        self.bar_fill = self.bar.create_rectangle(0, 0, 0, 22, fill=GOLD, width=0)
        self.bar_text = self.bar.create_text(165, 11, text="0.0 s", fill=INK, font=("Segoe UI", 9, "bold"))

        self.stats = tk.Label(side, text="", bg=BG, fg=DIM, font=("Segoe UI", 10), justify="left")
        self.stats.pack(anchor="w", pady=(10, 4))

        tk.Label(side, text="Alert log", bg=BG, fg=GOLD, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log = tk.Text(side, height=8, bg=PANEL, fg=INK, relief="flat", font=("Consolas", 9), state="disabled")
        self.log.pack(fill="both", expand=True)

        self.alerts = 0
        self.prev_alert = 0
        self.red_since = None
        self.photo = None
        self.tick()

    def _row(self, parent, name):
        r = tk.Frame(parent, bg=PANEL)
        r.pack(fill="x", padx=10, pady=4)
        tk.Label(r, text=name, bg=PANEL, fg=INK, font=("Segoe UI", 11)).pack(side="left")
        val = tk.Label(r, text="no", bg=PANEL, fg=DIM, font=("Segoe UI", 11, "bold"))
        val.pack(side="right")
        return val

    def write(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S  ") + text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def tick(self):
        s = shared["status"]
        frame = shared["frame"]
        if frame is not None:
            w, h = max(self.holder.winfo_width() - 4, 320), max(self.holder.winfo_height() - 4, 180)
            scale = min(w / frame.width, h / frame.height)
            img = frame.resize((int(frame.width * scale), int(frame.height * scale)))
            self.photo = ImageTk.PhotoImage(img)
            self.video.configure(image=self.photo, text="")
        else:
            self.video.configure(image="", text="waiting for video...")

        if shared["ok"] and s:
            self.conn.configure(text="connected to Jetson", fg=GREEN)
            alert = s["alert"]
            self.canvas.itemconfig(self.green, fill=GREEN_OFF if alert else GREEN)
            self.canvas.itemconfig(self.red, fill=RED if alert else RED_OFF)
            self.banner.configure(text="PHONE DETECTED" if alert else "ALL FINE", bg=RED if alert else GREEN)
            for lab, v in ((self.person, s["person"]), (self.phone, s["phone"])):
                lab.configure(text="YES" if v else "no", fg=GOLD if v else DIM)
            frac = min(s["together"] / s["hold"], 1.0)
            self.bar.coords(self.bar_fill, 0, 0, self.bar.winfo_width() * frac, 22)
            self.bar.coords(self.bar_text, self.bar.winfo_width() / 2, 11)
            self.bar.itemconfig(self.bar_text, text="%.1f s" % s["together"])
            self.stats.configure(text="Detector speed  %.0f frames/s\nRunning for     %.0f s\nAlerts so far   %d" % (
                s["fps"], s["t"], self.alerts))
            if alert and not self.prev_alert:
                self.alerts += 1
                self.red_since = time.time()
                self.write("RED ON  phone with person")
            elif self.prev_alert and not alert:
                self.write("GREEN   cleared after %.0f s" % (time.time() - (self.red_since or time.time())))
            self.prev_alert = alert
        else:
            self.conn.configure(text="no connection to the Jetson", fg=RED)
        self.root.after(60, self.tick)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    threading.Thread(target=video_loop, daemon=True).start()
    threading.Thread(target=status_loop, daemon=True).start()
    root.mainloop()

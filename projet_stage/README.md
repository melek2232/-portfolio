<h1 align="center">📦 Object / Barcode Counter</h1>
<h3 align="center">Raspberry Pi 5 · Real-time inventory verification</h3>

<p align="center">
  <img src="https://img.shields.io/badge/Raspberry%20Pi-5-C51A4A?style=flat-square&logo=raspberry-pi&logoColor=white">
  <img src="https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/YOLOv8-detection-111111?style=flat-square">
  <img src="https://img.shields.io/badge/Barcode-Zebra%20HID-0033A0?style=flat-square">
</p>

Displays two live counts side by side on screen:

| 📷 Objects (camera) | 🔫 Scanned (barcode) |
|---|---|
| How many objects the camera currently sees, via on-device YOLOv8n detection | How many *unique* articles have been scanned with a Zebra barcode scanner |

The screen shows **🟢 MATCH** when the two numbers are equal, and **🔴 MISMATCH** (with the difference shown) when they aren't. A barcode can never be counted twice — scanning the same code again in Add mode is ignored. **Add** and **Remove** are both driven by the scan itself: a mode switch on screen decides whether the next scan adds or removes an article, so nothing besides the scanner is needed during normal use.

---

## 🛒 About the Chariot

This app runs inside a custom-built **chariot** (cart), designed in CAD, that stores component reels (*bobines*) in a set of drawers. The software acts as a **verifier** for the chariot: the camera counts how many bobines are visibly present, the scanner tracks how many have been officially checked in or out, and the app confirms the two numbers match — so a bobine going missing (or added without being logged) is caught **immediately**, instead of at the next manual inventory check.

---

## 🧰 1. Hardware

- 🖥️ Raspberry Pi 5
- 🖼️ A screen (HDMI display, official touchscreen, etc.)
- 🎥 A USB webcam, **or** the official Raspberry Pi Camera Module (CSI)
- 🔫 A Zebra barcode scanner (DS22xx, LI36xx, DS3608, CS4070, etc.) with a USB cable — these ship by default in **HID Keyboard Wedge** mode, i.e. they "type" the barcode and press Enter, exactly like a keyboard. No driver needed.

## ⚙️ 2. Install

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libgl1

# Only if you're using the Pi Camera Module (CSI) instead of a USB webcam:
sudo apt install -y python3-picamera2 --no-install-recommends

cd counter_app
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
```

> ℹ️ `ultralytics` will download the small `yolov8n.pt` model (~6 MB) automatically the first time you run the app, so make sure the Pi has internet access on first run.

## 🎛️ 3. Configure

Open `config.py`:

| Setting | What it does |
|---|---|
| `CAMERA_SOURCE` | `0` for the first USB webcam, or `"picamera"` for the Pi Camera Module |
| `CLASSES_OF_INTEREST` | Leave empty to count *any* object the model recognizes, or list specific COCO class names (e.g. `["bottle", "box"]`) to only count certain items |
| `DETECT_EVERY_N_FRAMES` | Raise (e.g. 3–4) if the video feels slow; lower for more responsive counting |

## 🔫 4. Set up the Zebra scanner

Most Zebra scanners work out of the box in HID mode. If scans aren't being recognized, or the count doesn't update after a scan:

1. Open the **Product Reference Guide** (PRG) for your exact scanner model (available from Zebra's support site).
2. Scan the setup barcode for **"USB HID Keyboard"** (interface) if it isn't already selected.
3. Scan the setup barcode for **"Suffix = Enter"** / **"Add CR Suffix"** so each scan ends with a Return keystroke — the app relies on this to know when a barcode is complete.

## ▶️ 5. Run

```bash
source .venv/bin/activate
python3 app.py
```

- 🖱️ Click into the window once so it has keyboard focus, then scan — the scanner's keystrokes are captured anywhere in the window.
- 🔀 Use the **Add mode / Remove mode** radio buttons to choose what the next scan does.
- 🔄 **Reset all** clears every scanned article back to zero (the object count from the camera is unaffected — it always reflects what's currently in view).
- ⎋ Press `Esc` to leave fullscreen.

## 🚀 6. Optional: auto-start on boot (kiosk mode)

To have the Pi boot straight into this app on the attached screen, create a systemd service:

```bash
sudo tee /etc/systemd/system/counter-app.service > /dev/null <<'EOF'
[Unit]
Description=Object/Barcode Counter
After=graphical.target

[Service]
Environment=DISPLAY=:0
User=pi
WorkingDirectory=/home/pi/counter_app
ExecStart=/home/pi/counter_app/.venv/bin/python3 /home/pi/counter_app/app.py
Restart=on-failure

[Install]
WantedBy=graphical.target
EOF

sudo systemctl enable counter-app.service
sudo systemctl start counter-app.service
```

> 💡 Adjust paths/username if you didn't use the default `pi` user or a different install location.

## ⚡ 7. Performance notes for the Pi 5

- YOLOv8n runs at a few frames per second on the Pi 5 CPU — plenty for counting objects sitting on a table/belt.
- Need more speed? Export the model to NCNN format, which `ultralytics` can do in one line:
  ```bash
  python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='ncnn')"
  ```
  then set `MODEL_PATH = "yolov8n_ncnn_model"` in `config.py`.

---

## 📁 Project structure

```
counter_app/
├── app.py         # main GUI (Tkinter) — video, counts, mode switch, list
├── detector.py     # camera capture + YOLOv8n object-counting thread
├── inventory.py    # thread-safe state: scanned set, counts, add/remove
├── scanner.py       # turns raw keystrokes into complete barcodes
├── config.py        # all the settings you're likely to want to change
└── requirements.txt
```

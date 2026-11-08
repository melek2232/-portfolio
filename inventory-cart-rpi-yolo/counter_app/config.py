"""Configuration for the Object / Barcode Counter application.

Edit the values below to match your hardware. Nothing in the other files
needs to change for normal tuning.
"""

# ---- Camera settings ----
# 0 (or 1, 2...) selects a USB webcam through OpenCV.
# Set to "picamera" to use the official Raspberry Pi Camera Module via
# picamera2 instead (requires `sudo apt install python3-picamera2`).
CAMERA_SOURCE = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# Run the (relatively expensive) detection model every N frames instead of
# every single frame. 2-3 is a good balance on a Pi 5. The video preview
# still updates every frame; only the object count/boxes lag slightly.
DETECT_EVERY_N_FRAMES = 2

# ---- Object detection settings ----
# Path to your ONNX-exported model (NOT a .pt file — this project runs
# inference through onnxruntime only, never torch/ultralytics, because
# torch's CPU kernels crash with "Instruction non permise" (SIGILL) on
# this Pi's ARM core). See README for the export command.
MODEL_PATH = "yolov8n.onnx"
CONFIDENCE_THRESHOLD = 0.5
NMS_IOU_THRESHOLD = 0.45

# Maps class index (as predicted by MODEL_PATH) -> class name. onnxruntime
# doesn't carry class names the way `ultralytics` did, so this has to be
# hardcoded here to match whichever model MODEL_PATH points to.
#
# Right now this is the standard 80-class COCO list, matching the generic
# yolov8n.onnx placeholder above — it has NO "bobine" class, so filtering
# for "bobine" below will always report a count of 0 with this model.
# Once you've trained your own single-class reel detector (see README:
# "Training a bobine detector") and exported it, replace this with:
#     CLASS_NAMES = {0: "bobine"}
# and point MODEL_PATH at that new .onnx file.
CLASS_NAMES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
    10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench",
    14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
    20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
    25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee",
    30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite",
    34: "baseball bat", 35: "baseball glove", 36: "skateboard",
    37: "surfboard", 38: "tennis racket", 39: "bottle", 40: "wine glass",
    41: "cup", 42: "fork", 43: "knife", 44: "spoon", 45: "bowl",
    46: "banana", 47: "apple", 48: "sandwich", 49: "orange", 50: "broccoli",
    51: "carrot", 52: "hot dog", 53: "pizza", 54: "donut", 55: "cake",
    56: "chair", 57: "couch", 58: "potted plant", 59: "bed",
    60: "dining table", 61: "toilet", 62: "tv", 63: "laptop", 64: "mouse",
    65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave",
    69: "oven", 70: "toaster", 71: "sink", 72: "refrigerator", 73: "book",
    74: "clock", 75: "vase", 76: "scissors", 77: "teddy bear",
    78: "hair drier", 79: "toothbrush",
}

# Only count these classes; leave [] to count every detected object.
# You asked to count only reels — this is set for that, but see the
# CLASS_NAMES note above: it won't actually detect any until MODEL_PATH
# points to a model that was trained on a "bobine" class.
CLASSES_OF_INTEREST = ["bobine"]

# ---- Barcode scanner settings ----
# Most Zebra scanners (DS22xx, LI36xx, DS3608, CS4070...) ship configured
# as a USB "HID Keyboard Wedge": to the computer they look exactly like
# someone typing the barcode very fast and pressing Enter. No special
# driver is required, this app just listens for keystrokes.
#
# If your scanner does NOT send an Enter/Return after each scan, open the
# Zebra "Product Reference Guide" for your model and scan the setup
# barcode for "Suffix = Enter" (sometimes called "Add CR/LF Suffix").
MIN_BARCODE_LENGTH = 3
# Max time (seconds) allowed between keystrokes of the SAME scan before we
# assume it was human typing rather than the scanner, and reset the buffer.
MAX_KEY_GAP_SECONDS = 0.5

# Set to True if the system keyboard layout is French AZERTY: the scanner
# sends US-layout scancodes, so digits arrive as "&éé"()-è_çà" instead of
# "0123456789" unless we translate them back in code. Leave False if the
# system layout is US, or if you've already set the scanner's own
# "Keyboard Country" setting to match.
SCANNER_KEYBOARD_IS_AZERTY = True

# Prints every keystroke, buffer state, and scan result to the terminal.
# Keep this on until scanning is confirmed working end-to-end, then flip
# to False (it's noisy, but harmless — pure console output).
DEBUG_SCAN = True

# If your scanner IS configured to send Enter/CR after each barcode, that
# still works fine — DEBUG_SCAN logs confirmed some Zebra units send NO
# terminator character at all (Data Suffix = None), so relying only on
# Enter means a correctly-scanned barcode is never submitted. As a robust
# fallback that works either way: if no new keystroke arrives within this
# many milliseconds of the last one, treat the buffer as a finished scan
# and submit it automatically, exactly as if Enter had been pressed.
SCAN_IDLE_FLUSH_MS = 150

# ---- Display ----
FULLSCREEN = True
WINDOW_TITLE = "Object / Barcode Counter"

"""Raspberry Pi 5 Object / Barcode Counter — main application.

Shows a live camera feed with the number of objects currently detected,
next to the number of unique articles scanned with a Zebra barcode
scanner. The two numbers are meant to match; the status banner turns red
when they don't.

Add / Remove both happen through the scan itself:
  - "Add mode"    (default): scanning a new barcode adds it. Scanning the
                   SAME barcode twice is ignored (no duplicates allowed).
  - "Remove mode": scanning a barcode that was previously added removes it
                   again (e.g. an item was taken back off the table).

Run with:  python3 app.py
"""

import queue
import tkinter as tk

import cv2
from PIL import Image, ImageTk

import config
from detector import ObjectDetector
from inventory import Inventory
from scanner import AZERTY_TO_DIGIT, ScanBuffer


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(config.WINDOW_TITLE)
        if config.FULLSCREEN:
            self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.configure(bg="#111111")

        self.inventory = Inventory()
        self.scan_buffer = ScanBuffer(
            min_length=config.MIN_BARCODE_LENGTH,
            max_gap_seconds=config.MAX_KEY_GAP_SECONDS,
            layout_map=AZERTY_TO_DIGIT if config.SCANNER_KEYBOARD_IS_AZERTY else None,
        )
        self.mode = tk.StringVar(value="ADD")
        self._flush_job = None  # pending id from root.after() for idle auto-submit

        self.frame_queue = queue.Queue(maxsize=1)
        self.detector = ObjectDetector(self.inventory, config, self.frame_queue)

        self._build_ui()

        # Catch every keystroke anywhere in the window: this is where the
        # scanner's "typing" arrives, regardless of which widget has focus.
        self.root.bind_all("<Key>", self._on_key)

        # Belt-and-suspenders: after ANY mouse click, once Tk has finished
        # handling it (hence after_idle), hand keyboard focus back to root.
        # Combined with takefocus=0 on the interactive widgets below, this
        # guarantees a click can never leave a child widget holding focus
        # and silently swallowing the scanner's keystrokes.
        self.root.bind_all("<Button-1>", lambda e: self.root.after_idle(self.root.focus_force), add="+")

        # A fullscreen/kiosk window doesn't always receive keyboard focus
        # automatically from the window manager (especially with no mouse
        # interaction on boot). Without focus, <Key> events from the
        # scanner never reach any widget, so bind_all silently sees
        # nothing. Force focus now and keep reclaiming it periodically in
        # case another window/screensaver steals it later.
        self.root.focus_force()
        self._reclaim_focus()

        self.detector.start()
        self._poll_video()
        self._poll_state()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        main = tk.Frame(self.root, bg="#111111")
        main.pack(fill="both", expand=True)

        self.video_label = tk.Label(main, bg="black")
        self.video_label.pack(side="left", fill="both", expand=True)

        panel = tk.Frame(main, bg="#111111", width=380)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)

        status_frame = tk.Frame(panel, bg="#222222")
        status_frame.pack(fill="x", pady=10, padx=10)

        tk.Label(status_frame, text="Objects (camera)", font=("DejaVu Sans", 12),
                 fg="#aaaaaa", bg="#222222").pack(pady=(8, 0))
        self.object_count_label = tk.Label(
            status_frame, text="0", font=("DejaVu Sans", 48, "bold"),
            fg="white", bg="#222222")
        self.object_count_label.pack()

        tk.Label(status_frame, text="Scanned (barcode)", font=("DejaVu Sans", 12),
                 fg="#aaaaaa", bg="#222222").pack()
        self.scanned_count_label = tk.Label(
            status_frame, text="0", font=("DejaVu Sans", 48, "bold"),
            fg="white", bg="#222222")
        self.scanned_count_label.pack(pady=(0, 8))

        self.match_label = tk.Label(
            panel, text="MATCH", font=("DejaVu Sans", 20, "bold"),
            fg="white", bg="green")
        self.match_label.pack(fill="x", pady=10, padx=10, ipady=10)

        mode_frame = tk.Frame(panel, bg="#111111")
        mode_frame.pack(fill="x", pady=10, padx=10)
        tk.Radiobutton(mode_frame, text="Add mode", variable=self.mode, value="ADD",
                        font=("DejaVu Sans", 14), bg="#111111", fg="white",
                        selectcolor="#333333", takefocus=0).pack(side="left", expand=True)
        tk.Radiobutton(mode_frame, text="Remove mode", variable=self.mode, value="REMOVE",
                        font=("DejaVu Sans", 14), bg="#111111", fg="white",
                        selectcolor="#333333", takefocus=0).pack(side="left", expand=True)

        tk.Button(panel, text="Reset all", command=self._on_reset,
                  font=("DejaVu Sans", 14), bg="#442222", fg="white", takefocus=0).pack(
                      fill="x", padx=10, pady=5)

        tk.Label(panel, text="Scanned articles", font=("DejaVu Sans", 12),
                 fg="#aaaaaa", bg="#111111").pack(pady=(15, 0))
        self.listbox = tk.Listbox(panel, font=("DejaVu Sans", 11), bg="#1a1a1a", fg="white",
                                   takefocus=0)
        self.listbox.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_label = tk.Label(panel, text="", font=("DejaVu Sans", 11),
                                   fg="#dddddd", bg="#111111", wraplength=340, justify="left")
        self.log_label.pack(fill="x", padx=10, pady=10)

    # --------------------------------------------------------- scanning
    def _on_key(self, event):
        if config.DEBUG_SCAN:
            print(f"[DEBUG] key event: keysym={event.keysym!r} char={event.char!r} "
                  f"focus_widget={self.root.focus_get()}")
        if event.keysym in ("Return", "KP_Enter"):
            self._cancel_flush()
            code = self.scan_buffer.feed_enter()
            if config.DEBUG_SCAN:
                print(f"[DEBUG] feed_enter() -> {code!r} (buffer was {self.scan_buffer.buffer!r})")
            if code:
                self._process_scan(code)
        elif len(event.char) == 1 and event.char.isprintable():
            self.scan_buffer.feed_char(event.char)
            if config.DEBUG_SCAN:
                print(f"[DEBUG] buffer now = {self.scan_buffer.buffer!r}")
            self._schedule_flush()

    def _schedule_flush(self):
        """(Re)start the idle timer: if no further keystroke arrives within
        SCAN_IDLE_FLUSH_MS, treat the buffer as a completed scan. This
        covers scanners that don't send an Enter/CR terminator at all."""
        self._cancel_flush()
        self._flush_job = self.root.after(config.SCAN_IDLE_FLUSH_MS, self._flush_scan_buffer)

    def _cancel_flush(self):
        if self._flush_job is not None:
            self.root.after_cancel(self._flush_job)
            self._flush_job = None

    def _flush_scan_buffer(self):
        self._flush_job = None
        code = self.scan_buffer.feed_enter()
        if config.DEBUG_SCAN:
            print(f"[DEBUG] idle flush -> {code!r}")
        if code:
            self._process_scan(code)

    def _process_scan(self, code):
        if config.DEBUG_SCAN:
            print(f"[DEBUG] _process_scan({code!r}) mode={self.mode.get()}")
        if self.mode.get() == "ADD":
            self.inventory.add_barcode(code)
        else:
            self.inventory.remove_barcode(code)

    def _on_reset(self):
        self.inventory.reset()

    def _reclaim_focus(self):
        """Keep keyboard focus on this window so scanner keystrokes are
        never silently lost to the desktop/window manager."""
        if not self.root.focus_get():
            self.root.focus_force()
        self.root.after(1000, self._reclaim_focus)

    # ------------------------------------------------------------ video
    def _poll_video(self):
        try:
            frame = self.frame_queue.get_nowait()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            w = self.video_label.winfo_width() or config.FRAME_WIDTH
            h = self.video_label.winfo_height() or config.FRAME_HEIGHT
            img.thumbnail((max(w, 1), max(h, 1)))
            photo = ImageTk.PhotoImage(image=img)
            self.video_label.configure(image=photo)
            self.video_label.image = photo  # keep a reference alive
        except queue.Empty:
            pass
        self.root.after(30, self._poll_video)

    # -------------------------------------------------------- state/UI
    def _poll_state(self):
        snap = self.inventory.snapshot()
        self.object_count_label.configure(text=str(snap["object_count"]))
        self.scanned_count_label.configure(text=str(snap["scanned_count"]))

        if snap["match"]:
            self.match_label.configure(text="MATCH", bg="green")
        else:
            diff = snap["object_count"] - snap["scanned_count"]
            sign = "+" if diff > 0 else ""
            self.match_label.configure(text=f"MISMATCH ({sign}{diff})", bg="#b30000")

        self.listbox.delete(0, tk.END)
        for code, ts in reversed(snap["codes"][-100:]):
            self.listbox.insert(tk.END, f"{ts}  {code}")

        if snap["log"]:
            self.log_label.configure(text=snap["log"][-1])

        self.root.after(200, self._poll_state)

    def on_close(self):
        self.detector.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()

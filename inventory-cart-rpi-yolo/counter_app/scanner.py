"""Barcode-scan buffering logic.

A Zebra scanner in the default USB HID keyboard-wedge mode behaves like a
very fast typist: it emits the barcode's characters and finishes with
Enter. This class just needs individual keystrokes fed to it (e.g. from a
Tkinter <Key> binding) and assembles them into complete barcodes, telling
scanner input apart from a human typing in a text box by how fast the
keystrokes arrive.
"""

import time

# The scanner sends raw USB HID scancodes as if talking to a US-QWERTY
# keyboard. If the OS keymap is French AZERTY, the *unshifted* top-row
# digit keys print punctuation instead of digits (scancode "1" -> "&",
# "2" -> "é", etc.), because those symbols sit where digits are on a US
# layout. This table reverses that specific mismatch so the app doesn't
# depend on the system keyboard layout at all. Extend it if your barcodes
# also contain letters (AZERTY swaps A/Q and W/Z, moves M, etc.).
AZERTY_TO_DIGIT = {
    "&": "1", "é": "2", '"': "3", "'": "4", "(": "5",
    "-": "6", "è": "7", "_": "8", "ç": "9", "à": "0",
}


class ScanBuffer:
    def __init__(self, min_length=3, max_gap_seconds=0.5, layout_map=None):
        self.buffer = ""
        self.min_length = min_length
        self.max_gap_seconds = max_gap_seconds
        self._last_key_time = 0.0
        # Pass layout_map=None (default) to disable translation, or e.g.
        # layout_map=AZERTY_TO_DIGIT to correct the AZERTY/US mismatch.
        self.layout_map = layout_map or {}

    def feed_char(self, char: str):
        """Feed one printable character coming from a keystroke."""
        char = self.layout_map.get(char, char)
        now = time.time()
        if now - self._last_key_time > self.max_gap_seconds:
            # Too long since the last keystroke: start a fresh buffer.
            self.buffer = ""
        self._last_key_time = now
        self.buffer += char

    def feed_enter(self):
        """Call when Enter/Return is pressed. Returns the completed barcode
        (or None if it was empty / too short), and clears the buffer."""
        code = self.buffer.strip()
        self.buffer = ""
        if len(code) >= self.min_length:
            return code
        return None

import scanner
from scanner import AZERTY_TO_DIGIT, ScanBuffer


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(monkeypatch, **kw):
    clock = FakeClock()
    monkeypatch.setattr(scanner.time, "time", clock)
    return ScanBuffer(**kw), clock


def type_code(buf, clock, text, gap=0.01):
    for ch in text:
        clock.t += gap
        buf.feed_char(ch)


def test_complete_barcode_is_returned_on_enter(monkeypatch):
    buf, clock = make(monkeypatch)
    type_code(buf, clock, "123456")
    assert buf.feed_enter() == "123456"
    assert buf.buffer == ""                          # buffer cleared after a scan


def test_too_short_code_is_rejected(monkeypatch):
    buf, clock = make(monkeypatch, min_length=3)
    type_code(buf, clock, "12")
    assert buf.feed_enter() is None


def test_slow_typing_starts_a_new_buffer(monkeypatch):
    buf, clock = make(monkeypatch, max_gap_seconds=0.5)
    type_code(buf, clock, "999")
    clock.t += 2.0                                   # a human pause: earlier keys are dropped
    type_code(buf, clock, "4567")
    assert buf.feed_enter() == "4567"


def test_azerty_digits_are_translated(monkeypatch):
    buf, clock = make(monkeypatch, layout_map=AZERTY_TO_DIGIT)
    type_code(buf, clock, "&é\"'(")                  # what an AZERTY layout prints for 1 2 3 4 5
    assert buf.feed_enter() == "12345"

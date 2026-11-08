"""Motor back-ends. duty values are in [-1, 1] (positive = forward)."""
import threading
import time


class Motors:
    connected = True        # SerialMotors overrides: False while the Mega link is down

    def set(self, left, right):
        raise NotImplementedError

    def stop(self):
        self.set(0.0, 0.0)

    def ticks(self):
        """Latest encoder reading (left, right, monotonic_time) or None."""
        return None


class DryRunMotors(Motors):
    """Does nothing: lets you test odometry, SLAM and Nav2 with no hardware."""

    def set(self, left, right):
        pass


class SerialMotors(Motors):
    """Arduino Mega (firmware/mega_motor_driver) on a USB serial port.

    Sends  "M <left> <right>\\n"  (PWM -255..255) at least every `keepalive` seconds: the
    Mega stops the motors by itself if it hears nothing for about 0.4 s.
    Reads  "T <left> <right>"  encoder ticks, if the firmware has ENCODERS 1.
    The port is re-opened automatically if the cable is unplugged and plugged again.
    """

    def __init__(self, port, baud, invert_left, invert_right, logger,
                 boot_wait=2.0, keepalive=0.1):
        import serial  # imported here: dry-run / GPIO users do not need pyserial
        self._serial = serial
        self.port = port
        self.baud = int(baud)
        self.inv = (-1.0 if invert_left else 1.0, -1.0 if invert_right else 1.0)
        self.log = logger
        self.boot_wait = float(boot_wait)
        self.keepalive = float(keepalive)
        self._ser = None
        self._ready = False
        self._lock = threading.Lock()
        self._last = None
        self._last_t = 0.0
        self._ticks = None
        self._running = True
        self._open()      # raises if the port cannot be opened: clear error at start-up
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    @property
    def connected(self):
        return bool(self._ready)

    # ------------------------------------------------------------ connection
    def _open(self):
        ser = self._serial.Serial(self.port, self.baud, timeout=0.05, write_timeout=0.2)
        time.sleep(self.boot_wait)           # the Mega resets when the port is opened
        ser.reset_input_buffer()
        ser.write(b'S\n')
        with self._lock:
            self._ser = ser
            self._ready = True
            self._last = None
        self.log.info(f'Mega connected on {self.port} @ {self.baud}')

    def _drop(self, exc):
        self.log.error(f'serial link lost ({exc}); will retry')
        with self._lock:
            ser, self._ser, self._ready = self._ser, None, False
        try:
            if ser is not None:
                ser.close()
        except Exception:  # noqa: BLE001
            pass

    def _reader(self):
        buf = b''
        last_warn = 0.0
        while self._running:
            ser = self._ser
            if ser is None:
                time.sleep(1.0)
                try:
                    self._open()
                except Exception as exc:  # noqa: BLE001
                    if time.monotonic() - last_warn > 10.0:
                        last_warn = time.monotonic()
                        self.log.warning(f'cannot open {self.port}: {exc}')
                continue
            try:
                data = ser.read(64)
            except Exception as exc:  # noqa: BLE001
                if not self._running:      # closed on purpose
                    break
                self._drop(exc)
                buf = b''
                continue
            if not data:
                continue
            buf += data
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                self._parse(line.decode('ascii', 'ignore').strip())
            if len(buf) > 200:
                buf = b''

    def _parse(self, line):
        if line.startswith('T '):
            parts = line.split()
            try:
                self._ticks = (int(parts[1]), int(parts[2]), time.monotonic())
            except (IndexError, ValueError):
                pass
        elif line.startswith('#'):
            self.log.info(f'Mega: {line}')
        elif line.startswith('?'):
            self.log.warning(f'Mega did not understand: {line}')

    def _write(self, text):
        with self._lock:
            ser = self._ser if self._ready else None
        if ser is None:
            return False
        try:
            ser.write(text.encode('ascii'))
            return True
        except Exception as exc:  # noqa: BLE001
            self._drop(exc)
            return False

    # ---------------------------------------------------------------- Motors
    def set(self, left, right):
        l = int(round(max(-1.0, min(1.0, left * self.inv[0])) * 255))
        r = int(round(max(-1.0, min(1.0, right * self.inv[1])) * 255))
        now = time.monotonic()
        if (l, r) == self._last and now - self._last_t < self.keepalive:
            return
        if self._write(f'M {l} {r}\n'):
            self._last, self._last_t = (l, r), now

    def stop(self):
        for _ in range(3):
            self._write('S\n')
        self._last = (0, 0)

    def ticks(self):
        return self._ticks

    def close(self):
        self.stop()
        self._running = False
        with self._lock:
            ser, self._ser, self._ready = self._ser, None, False
        try:
            if ser is not None:
                ser.close()
        except Exception:  # noqa: BLE001
            pass


class GpioMotors(Motors):
    """H-bridge wired directly on the Raspberry Pi GPIO (BCM numbering).

    Not used with the Arduino Mega set-up; kept for robots without a Mega.
    driver_type 'l298n'    : pins = [IN1, IN2, ENABLE(PWM)]
    driver_type 'dual_pwm' : pins = [FORWARD_PWM, REVERSE_PWM]
    """

    def __init__(self, driver_type, left_pins, right_pins, pwm_hz,
                 invert_left, invert_right, logger):
        from gpiozero import Device, DigitalOutputDevice, PWMOutputDevice
        try:  # the Pi 5 needs the lgpio back-end
            from gpiozero.pins.lgpio import LGPIOFactory
            Device.pin_factory = LGPIOFactory()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f'lgpio pin factory not used ({exc}); using the gpiozero default')

        self.driver_type = driver_type
        self.inv = (-1.0 if invert_left else 1.0, -1.0 if invert_right else 1.0)

        def build(pins):
            pins = [int(p) for p in pins]
            if driver_type == 'l298n':
                if len(pins) != 3:
                    raise ValueError('l298n needs 3 pins: [in1, in2, enable]')
                return (DigitalOutputDevice(pins[0]), DigitalOutputDevice(pins[1]),
                        PWMOutputDevice(pins[2], frequency=int(pwm_hz)))
            if driver_type == 'dual_pwm':
                if len(pins) != 2:
                    raise ValueError('dual_pwm needs 2 pins: [forward, reverse]')
                return (PWMOutputDevice(pins[0], frequency=int(pwm_hz)),
                        PWMOutputDevice(pins[1], frequency=int(pwm_hz)))
            raise ValueError(f'unknown driver_type {driver_type!r}')

        self.left = build(left_pins)
        self.right = build(right_pins)

    def _drive(self, side, duty):
        duty = max(-1.0, min(1.0, duty))
        if self.driver_type == 'l298n':
            in1, in2, en = side
            if duty > 0:
                in1.on(); in2.off(); en.value = duty
            elif duty < 0:
                in1.off(); in2.on(); en.value = -duty
            else:
                in1.off(); in2.off(); en.value = 0.0
        else:
            fwd, rev = side
            fwd.value = duty if duty > 0 else 0.0
            rev.value = -duty if duty < 0 else 0.0

    def set(self, left, right):
        self._drive(self.left, left * self.inv[0])
        self._drive(self.right, right * self.inv[1])

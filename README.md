<h1 align="center">⚡ Melek Chourabi · Electrical Engineering Portfolio</h1>
<h3 align="center">Embedded systems · Robotics · Electronics · Applied AI</h3>

<p align="center">
  <img src="https://img.shields.io/badge/ENIT-Electrical%20Engineering-1f6fb2?style=flat-square">
  <img src="https://img.shields.io/badge/ROS%202-22314E?style=flat-square&logo=ros&logoColor=white">
  <img src="https://img.shields.io/badge/Raspberry%20Pi-C51A4A?style=flat-square&logo=raspberry-pi&logoColor=white">
  <img src="https://img.shields.io/badge/Arduino-00979D?style=flat-square&logo=arduino&logoColor=white">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/YOLOv8-111111?style=flat-square">
  <img src="https://img.shields.io/badge/KiCad-314CB0?style=flat-square&logo=kicad&logoColor=white">
</p>

I am a final-year electrical engineering student at **ENIT** (École Nationale d'Ingénieurs de Tunis, Tunisia). I like projects where
electronics, firmware and software meet: robots, instrumentation, connected sensors and embedded vision. Each project below comes with its documentation,
and the code that can be tested without hardware has automated tests.

---

## 🚀 Projects

<table>
  <tr>
    <td width="50%" valign="top">
      <a href="https://github.com/melek2232/ros2-lidar-robot"><img src="assets/card-robot.png" alt="Robot control panel"></a>
      <h3>🤖 <a href="https://github.com/melek2232/ros2-lidar-robot">ROS 2 lidar robot</a></h3>
      <p>Raspberry Pi 5 + Arduino Mega + YDLIDAR X2. SLAM mapping, PC web panel, autonomous exploration and a safety layer between every command and the motors.</p>
      <p><sub>ROS 2 Jazzy · slam_toolbox · Nav2 · Python · C++ · Arduino · Docker<br>Screenshot: simulation. Tested offline; hardware validation in progress.</sub></p>
    </td>
    <td width="50%" valign="top">
      <a href="inventory-cart-rpi-yolo/README.md"><img src="assets/card-cart.png" alt="Inventory cart CAD"></a>
      <h3>🛒 <a href="inventory-cart-rpi-yolo/README.md">Intelligent inventory cart</a></h3>
      <p>SolidWorks-designed cart with a Raspberry Pi verifier: camera object counting (YOLOv8 / ONNX) cross-checked in real time with barcode scans.</p>
      <p><sub>Raspberry Pi 5 · ONNX Runtime · OpenCV · Tkinter · SolidWorks · pytest</sub></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="auto-ranging-voltmeter/README.md"><img src="assets/card-voltmeter.png" alt="Voltmeter schematic"></a>
      <h3>🔌 <a href="auto-ranging-voltmeter/README.md">Auto-ranging digital voltmeter</a></h3>
      <p>Arduino UNO + ADS1115 (16-bit) + CD4051 multiplexer. Automatic selection among 4 divider ratios (1:1 to 1:100), with hysteresis and over-range detection. Built during an internship at SAGEMCOM.</p>
      <p><sub>Arduino · I²C · analog front-end · Proteus</sub></p>
    </td>
    <td width="50%" valign="top">
      <a href="cable-cut-detection-pfa/README.md"><img src="assets/card-pfa.jpg" alt="Cable cut detection board"></a>
      <h3>⚠️ <a href="cable-cut-detection-pfa/README.md">Cable cut detection system</a></h3>
      <p>Detects the disappearance of a 25 kHz supervision signal and raises a buzzer + LED alarm. Two architectures compared: discrete analog and PIC12F675, with a KiCad PCB.</p>
      <p><sub>KiCad · PIC12F675 · analog design · oscilloscope measurements</sub></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="ble-mqtt-sensor-monitor/README.md"><img src="assets/card-mqtt.jpg" alt="Node-RED dashboard with live sensor data"></a>
      <h3>📡 <a href="ble-mqtt-sensor-monitor/README.md">Wireless sensor monitor (BLE + MQTT)</a></h3>
      <p>Arduino Nano 33 BLE Sense → BLE → Raspberry Pi gateway → Mosquitto → Node-RED dashboard. Motion, temperature, humidity and pressure at 1 Hz, with 70 minutes of logged data.</p>
      <p><sub>MQTT · Mosquitto · BLE · Node-RED · Python (bleak, paho) · Arduino</sub></p>
    </td>
    <td width="50%" valign="top"></td>
  </tr>
</table>

---

## 🛠️ Skills

| Domain | What I work with |
|---|---|
| 🤖 **Robotics** | ROS 2 (nodes, TF, launch, lifecycle), SLAM and navigation (slam_toolbox, Nav2), differential-drive kinematics, safety layers (dead-man, e-stop, obstacle stop) |
| 🔌 **Embedded / hardware** | Raspberry Pi (GPIO, camera), Arduino (I²C, PWM, serial protocols), H-bridge motor drivers, PIC12F675, ADCs and analog front-ends, digital logic (FSMs) |
| 💻 **Software** | Python (Tkinter, pyserial, pytest), C / C++ basics, computer vision (YOLOv8, ONNX Runtime), Docker, Git and CI |
| 📡 **Networks / IoT** | MQTT (Mosquitto, paho-mqtt, topics and QoS), Bluetooth Low Energy (GATT, notifications), Node-RED dashboards, JSON telemetry |
| 📐 **Design tools** | KiCad, Proteus, SolidWorks, LaTeX / TikZ, functional specifications (bête à cornes, pieuvre) |

---

## 🧭 What I am looking for

Internships and projects in **robotics, embedded systems and automation**. If one of these projects interests you, open an issue or reach me through my GitHub profile.

<p align="center"><sub>Repository layout: one folder per project, each with its own README. Run the tests of the cart app with
<code>cd inventory-cart-rpi-yolo/counter_app && python -m pytest -q tests</code>.</sub></p>

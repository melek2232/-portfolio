# ⚡ Cable Cut Detection System

> **Real-time embedded system for detecting cable interruption and triggering a local audible and visual alarm.**

<p align="center">
  <img src="images/final-prototype.png" width="600">
</p>

<p align="center">
  <b>Final assembled prototype</b>
</p>

---

## 📌 Overview

This project focuses on the **design, simulation, PCB development, and implementation of a cable-cut detection system** capable of continuously monitoring the integrity of a transmission cable.

The system uses a **25 kHz supervision signal** transmitted through the monitored cable. As long as the cable remains intact, the receiver detects the signal. When the signal disappears beyond a defined detection threshold, the system identifies a cable interruption and activates a **visual and audible alarm**.

The system was designed to operate both **without the cable being energized and under mains voltage**, while maintaining low power consumption for battery-powered operation.

---

## 🎯 Objectives

The main objectives of the project are:

- Detect cable interruption automatically and in real time
- Monitor the presence of a **25 kHz / 1 V supervision signal**
- Filter unwanted low-frequency disturbances
- Detect the disappearance of the supervision signal
- Trigger a **buzzer and LED alarm**
- Reduce false alarms
- Limit energy consumption for battery operation
- Design a low-cost solution using standard electronic components
- Compare a discrete analog/digital solution with a microcontroller-based solution
- Design and manufacture the corresponding PCB

---

# 🏗️ System Architecture

The system was developed using two different detection architectures sharing the same signal-conditioning stage.

### Common Signal-Conditioning Stage

```text
                 MONITORED CABLE
                        │
                        ▼
                ┌──────────────┐
                │   LC FILTER  │
                │     25 kHz   │
                └───────┬──────┘
                        │
                        ▼
                ┌──────────────┐
                │  GREINACHER  │
                │      ×4      │
                └───────┬──────┘
                        │
                 Conditioned Signal
                        │
              ┌─────────┴─────────┐
              │                   │
              ▼                   ▼
       ANALOG SOLUTION      PIC12F675 SOLUTION
```

The input signal is first filtered using an **LC high-pass filter** and then passed through a **Greinacher voltage quadrupler**.

The filter is designed to attenuate the 50 Hz component while allowing the 25 kHz supervision signal to pass.

---

# 🔧 Solution 1 — Analog / Discrete Architecture

The first solution implements the detection and alarm functions using standard analog and digital components without a programmable microcontroller.

### Functional Chain

```text
Cable
  │
  ▼
LC 25 kHz Filter
  │
  ▼
Greinacher ×4
  │
  ▼
2N7000
  │
  ▼
74HCT132
  │
  ▼
TLC555
  │
  ▼
2N2222
  │
  ├──────────────► 🔊 Buzzer
  │
  └──────────────► 💡 LED
```

### Complete Circuit

<p align="center">
  <img src="images/analog-schematic.png" width="950">
</p>

<p align="center">
  <b>Complete analog/discrete detection circuit</b>
</p>

### Main Components

| Component | Function |
|---|---|
| LC Filter | 25 kHz signal selection |
| Greinacher ×4 | Voltage multiplication |
| 2N7000 | Signal detection |
| 74HCT132 | Logic / timing stage |
| TLC555 | Monostable timing |
| 2N2222 | Alarm output switching |
| Buzzer | Audible alarm |
| LED | Visual alarm |

---

# 🧠 Solution 2 — PIC12F675 Embedded Architecture

The second solution integrates the detection logic into a **PIC12F675 microcontroller**.

The conditioned signal is stored using an RC stage and measured by the PIC's ADC. A programmable threshold determines whether the supervision signal is still present.

### Functional Chain

```text
Cable
  │
  ▼
LC Filter
  │
  ▼
Greinacher ×4
  │
  ▼
RC Signal Memory
  │
  ▼
Voltage Divider
  │
  ▼
PIC12F675 ADC
  │
  ▼
Threshold Detection
  │
  ▼
2N2222
  │
  ├──────────────► 🔊 Buzzer
  │
  └──────────────► 💡 LED
```

### Complete Schematic

<p align="center">
  <img src="images/digital-schematic.png" width="950">
</p>

<p align="center">
  <b>PIC12F675-based detection circuit</b>
</p>

---

## 💻 Firmware

The PIC12F675 firmware was developed using **XC8**.

The microcontroller continuously measures the conditioned signal using its ADC and compares the measured value with a predefined threshold.

The implemented detection threshold is:

```text
THRESHOLD = 85 ADC counts
```

Simplified detection logic:

```text
        ADC Measurement
               │
               ▼
       Compare with threshold
               │
          ┌────┴────┐
          │         │
       Signal     Signal
       Present     Absent
          │         │
          ▼         ▼
        Normal     Alarm
```

---

# 📐 Key Electrical Parameters

## Supervision Signal

| Parameter | Value |
|---|---:|
| Frequency | **25 kHz** |
| Amplitude | **1 V** |

## LC Filter

| Parameter | Value |
|---|---:|
| C1 | 100 nF |
| C2 | 100 nF |
| Equivalent capacitance | 50 nF |
| Inductance | 1 mH |
| Calculated cutoff frequency | **≈ 22.5 kHz** |

The calculated cutoff frequency is close to the target supervision frequency of 25 kHz.

---

# ⚡ Greinacher Voltage Quadrupler

The signal-conditioning stage uses a **Greinacher ×4 voltage multiplier**.

The circuit is constructed from two cascaded voltage-doubling stages.

Ideally:

```text
Vout ≈ 4 × Vpeak
```

In the practical circuit, **Schottky diodes** were used to reduce voltage losses caused by diode forward voltage.

---

# 🖥️ PCB Design

The PCB was designed using **KiCad**, starting from the electrical schematic and progressing to PCB routing and 3D visualization.

## PCB Layout

<p align="center">
  <img src="images/digital-pcb.png" width="950">
</p>

<p align="center">
  <b>PCB layout designed with KiCad</b>
</p>

## 3D PCB Model

<p align="center">
  <img src="images/digital-pcb-3d.png" width="700">
</p>

<p align="center">
  <b>3D visualization of the PCB</b>
</p>

The PCB design includes:

- PIC12F675
- Signal-conditioning stage
- Voltage multiplier
- Protection circuitry
- Alarm driver
- Power supply connections
- ICSP programming interface
- Mounting holes

---

# 🔬 Final Hardware

After schematic design, simulation, PCB design, and fabrication, the system was assembled as a physical prototype.

<p align="center">
  <img src="images/final-prototype.png" width="600">
</p>

<p align="center">
  <b>Final assembled electronic board</b>
</p>

The prototype demonstrates the transition from the theoretical design to a physical hardware implementation.

---

# 📈 Experimental Measurement

Experimental measurements were performed to verify the behavior of the designed circuit.

### Oscilloscope Measurement

<p align="center">
  <img src="images/oscilloscope.png" width="950">
</p>

<p align="center">
  <b>Oscilloscope measurement of the capacitor discharge</b>
</p>

The RC memory stage was analyzed theoretically and experimentally.

| Parameter | Theoretical | Measured |
|---|---:|---:|
| Discharge time | 402.4 s | 120 s |
| Time constant τ | 206.8 s | 61.7 s |
| Equivalent resistance | 440 kΩ | 131 kΩ |

The difference between theoretical and measured values is attributed to real-world effects such as component tolerances, capacitor leakage, input resistance of the following stage, and diode characteristics.

---

# 🧪 Development Workflow

The project followed a complete electronics development workflow:

```text
        Problem Definition
                │
                ▼
          System Design
                │
                ▼
       Analytical Calculations
                │
                ▼
        Circuit Simulation
        ┌───────┴────────┐
        │                │
       PSIM            PSpice
        │                │
        └───────┬────────┘
                ▼
          KiCad Design
                │
                ▼
           PCB Routing
                │
                ▼
         PCB Fabrication
                │
                ▼
          Hardware Assembly
                │
                ▼
      Experimental Validation
```

---

# 🛠️ Technologies & Tools

### Electronics

- Analog Electronics
- Digital Electronics
- Signal Conditioning
- LC Filtering
- Voltage Multipliers
- Transistor Switching
- ADC Measurement
- Embedded Systems
- Battery-Powered Electronics

### Microcontroller

- **PIC12F675**
- Embedded C
- XC8
- ADC
- GPIO
- ICSP

### Software

| Tool | Purpose |
|---|---|
| **KiCad** | Schematic and PCB design |
| **PSIM** | System and circuit simulation |
| **PSpice** | Detailed circuit simulation |
| **MPLAB IDE** | PIC firmware development |

---

# 📚 Skills Developed

Through this project, I developed practical experience in:

- Electronic system architecture
- Analog circuit design
- Digital circuit design
- Signal filtering
- Signal detection
- Voltage multiplier design
- Microcontroller programming
- ADC-based measurement
- Embedded C programming
- PIC12F675 development
- PCB design with KiCad
- PCB routing
- ICSP programming
- Circuit simulation
- Hardware debugging
- Experimental measurement
- Transition from theoretical design to physical implementation

---

# 🚀 Possible Future Improvements

Future versions of the system could include:

- Adjustable detection thresholds
- Improved false-alarm rejection
- Lower-power operating modes
- Battery-level monitoring
- More compact PCB design
- Remote alarm notification
- Wireless communication
- Cable fault localization
- Advanced digital signal processing

---

# 📁 Repository Structure

```text
cable-cut-detection-system/
│
├── README.md
│
├── images/
│   ├── final-prototype.png
│   ├── analog-schematic.png
│   ├── digital-schematic.png
│   ├── digital-pcb.png
│   ├── digital-pcb-3d.png
│   └── oscilloscope.png
│
├── hardware/
│   ├── analog/
│   │   ├── schematic/
│   │   └── pcb/
│   │
│   └── digital/
│       ├── schematic/
│       └── pcb/
│
├── firmware/
│   └── PIC12F675/
│       ├── src/
│       └── include/
│
├── simulations/
│   ├── PSIM/
│   └── PSpice/
│
└── docs/
    └── project-report.pdf
```

---

# 👨‍💻 Author

## Melek Chourabi

**Electrical Engineering Student**

Interested in:

`Embedded Systems` • `Electronics` • `Automation` • `Robotics` • `Control Systems`

---

⭐ **If you find this project interesting, feel free to explore the schematics, firmware, simulations, and PCB design files.**

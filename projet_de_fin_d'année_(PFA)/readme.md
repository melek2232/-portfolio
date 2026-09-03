
# ⚡ Cable Cut Detection System

> **Real-time embedded system for detecting cable interruption and triggering a local audible and visual alarm.**

## 📌 Overview

This project presents the **design, simulation, and implementation of an electronic cable-cut detection system** capable of continuously monitoring the integrity of a transmission cable.

The system uses a **25 kHz supervision signal** transmitted through the monitored cable. As long as the cable remains intact, the receiver detects this signal. If the signal disappears beyond a defined threshold, the system interprets this condition as a cable interruption and activates a **buzzer and LED alarm**.

The system was designed to operate both **without the cable being energized and when the cable is under mains voltage**, while maintaining low power consumption for battery-powered operation.

---

## 🎯 Project Objectives

The main objectives were to:

* Detect cable interruption automatically and in real time
* Monitor the presence of a **25 kHz / 1 V supervision signal**
* Distinguish the supervision signal from low-frequency disturbances
* Minimize false alarms
* Generate both **audible and visual alarms**
* Reduce power consumption to preserve battery life
* Develop a low-cost solution using commercially available components
* Compare an analog/discrete architecture with a microcontroller-based architecture

---

## 🏗️ System Architecture

The project was developed around two different architectures sharing the same input signal-conditioning stage.

### Common Input Stage

```text
              Monitored Cable
                    │
                    ▼
             ┌─────────────┐
             │  LC Filter  │
             │    25 kHz   │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │  Greinacher │
             │     ×4      │
             └──────┬──────┘
                    │
             Conditioned Signal
                    │
             ┌──────┴──────┐
             │             │
             ▼             ▼
      Analog Solution   PIC12F675
```

The input stage consists of an **LC high-pass filter** followed by a **Greinacher voltage quadrupler**. The filter selects the useful 25 kHz signal while attenuating the 50 Hz mains component and other low-frequency disturbances.

---

# 🔧 Solution 1 — Analog / Discrete Architecture

The first implementation avoids a programmable microcontroller and uses standard analog and digital integrated circuits.

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
 ├──────────► 🔊 Buzzer
 │
 └──────────► 💡 LED
```

### Main Components

| Component     | Function                      |
| ------------- | ----------------------------- |
| LC Filter     | 25 kHz signal selection       |
| Greinacher ×4 | Signal voltage multiplication |
| 2N7000        | Signal detection              |
| 74HCT132      | Logic / astable stage         |
| TLC555        | Monostable timing             |
| 2N2222        | Output switching              |
| Buzzer        | Audible alarm                 |
| LED           | Visual alarm                  |

The analog architecture combines the **2N7000 → 74HCT132 → TLC555 → 2N2222** stages to detect the loss of the supervision signal and drive the alarm.

---

# 🧠 Solution 2 — PIC12F675 Embedded Architecture

The second implementation integrates the detection and alarm-control logic into a **Microchip PIC12F675 microcontroller**.

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
 ├──────────► 🔊 Buzzer
 │
 └──────────► 💡 LED
```

The PIC continuously measures the conditioned signal through its ADC. A programmable threshold is then used to determine whether the cable is still transmitting the supervision signal.

### Firmware

The firmware was developed in **XC8** and configures the PIC12F675 ADC to monitor the signal level.

A detection threshold of **85 ADC counts** was used in the implementation.

---

# 📐 Key Design Parameters

### Supervision Signal

| Parameter |      Value |
| --------- | ---------: |
| Frequency | **25 kHz** |
| Amplitude |    **1 V** |

### LC Filter

| Parameter                   |          Value |
| --------------------------- | -------------: |
| C1                          |         100 nF |
| C2                          |         100 nF |
| Equivalent capacitance      |          50 nF |
| Inductance                  |           1 mH |
| Calculated cutoff frequency | **≈ 22.5 kHz** |

The calculated cutoff frequency is close to the 25 kHz target, allowing the circuit to reject the 50 Hz power component while passing the supervision signal. Simulation confirmed this filtering behavior.

### Greinacher Voltage Multiplier

The voltage multiplier consists of **two cascaded voltage doublers**, producing an ideal output approximately equal to:

```text
Vout ≈ 4 × Vpeak
```

Schottky diodes were selected to reduce the voltage losses associated with diode forward voltage.

---

# 💻 Technologies & Tools

### Electronics

* Analog electronics
* Digital electronics
* Signal conditioning
* LC filtering
* Voltage multipliers
* Transistor switching
* ADC measurement
* Battery-powered embedded systems

### Microcontroller

* **PIC12F675**
* XC8
* ADC
* GPIO
* ICSP programming

### Software

* **KiCad** — schematic and PCB design
* **PSIM** — system and filter simulation
* **PSpice** — component-level circuit simulation
* **MPLAB IDE** — PIC firmware development and debugging

These tools were used throughout the simulation, PCB design, firmware development, and implementation stages.

---

# 🔌 PCB & Hardware Design

The electronic boards were designed using **KiCad**, including:

* Complete schematic design
* PIC12F675 measurement circuitry
* Transistor output stage
* ICSP programming interface
* Component protection
* PCB implementation

The PIC programming interface uses **ICSP (In-Circuit Serial Programming)**, allowing the microcontroller to be programmed without removing it from the PCB.

### PCB

The project includes a physical implementation of the electronic detection system, moving from theoretical calculations and simulations to an actual PCB realization.

---

# 📊 Simulation & Validation

The design process followed three main stages:

```text
Theoretical Design
       │
       ▼
Circuit Simulation
       │
       ▼
PCB Implementation
       │
       ▼
Experimental Validation
```

The common input stages were dimensioned analytically and validated through **PSIM**, while **PSpice** was used for detailed component-level simulation.

The project also compared theoretical and measured behavior. For example, the RC memory circuit showed a difference between the theoretical discharge time (**≈ 402.4 s**) and the measured value (**≈ 120 s**), attributed to real component tolerances, leakage currents, input resistance, and diode behavior.

---

# 📁 Repository Structure

```text
cable-cut-detection-system/
│
├── README.md
│
├── docs/
│   └── project-report.pdf
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
└── images/
    ├── system-architecture.png
    ├── schematic.png
    └── pcb.png
```

---

# 🚀 What I Learned

This project allowed me to develop practical skills in:

* Electronic system architecture
* Analog and digital circuit design
* Signal filtering and conditioning
* Voltage multiplier design
* Embedded C programming
* PIC microcontroller programming
* ADC-based signal detection
* PCB design with KiCad
* Circuit simulation with PSIM and PSpice
* ICSP programming
* Hardware debugging
* Transition from theoretical calculations to physical implementation

---

# 🔮 Possible Improvements

Future versions could improve the system by introducing:

* Adjustable detection thresholds
* More advanced false-alarm filtering
* Lower-power operating modes
* Battery-level monitoring
* A more compact PCB
* Remote notification capability
* Cable fault localization
* More advanced digital signal processing

---

# 👨‍💻 Author

**Melek Chourabi**

Electrical Engineering Student
Interested in **Embedded Systems • Electronics • Automation • Robotics**

---

## 📜 Project Context

This project was developed as an engineering electronics project involving the **study, design, simulation, and realization of two cable-cut detection architectures**: a mixed analog/digital solution and a microcontroller-based solution.

---

⭐ If you find this project interesting, feel free to explore the schematics, firmware, simulations, and PCB files included in the repository.

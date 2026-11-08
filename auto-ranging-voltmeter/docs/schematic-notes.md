# Schematic Notes

Original schematic captured and simulated in **Proteus 8** (`stage.pdsprj`), exported as
[`schematic.png`](schematic.png) and embedded in the top-level README.

Note on the resistor labels as drawn in Proteus (`R1`–`R5`): R1 and R3 are the low-side
(`R_bas`) legs of the network, while R2, R4, and R5 form the switched high-side
(`R_haut`) legs selected through the CD4051 to produce the 1:1, 1:10, 1:50 and 1:100
ratios described below. If you re-derive exact values from your own build, update this
table to match your populated resistors.

## Bill of Materials

| Qty | Part | Notes |
|---|---|---|
| 1 | Arduino UNO | ATmega328P, 5 V, 16 MHz |
| 1 | ADS1115 breakout | 16-bit I²C ADC, PGA ±6.144 V → ±0.256 V |
| 1 | CD4051 breakout | 8-channel analog multiplexer |
| 1 | 10 kΩ resistor | R_bas, common to all dividers |
| 1 | 90 kΩ (or 91 kΩ E96) resistor | R_haut for 1:10 |
| 1 | 490 kΩ (or 470 kΩ + trim) resistor | R_haut for 1:50 |
| 1 | 990 kΩ (or 1 MΩ) resistor | R_haut for 1:100 |
| — | TVS diodes / series resistors / fuse | Input protection, size per your max input voltage |

## Pin Mapping

| Arduino UNO | Function |
|---|---|
| A4 | I²C SDA → ADS1115 SDA |
| A5 | I²C SCL → ADS1115 SCL |
| D2 | CD4051 select S0 |
| D3 | CD4051 select S1 |
| D4 | CD4051 select S2 (tied low in software — reserved for future channels) |
| 5V / GND | Power for ADS1115 and CD4051 |

CD4051 channel assignment used by the firmware:

| CD4051 channel | Divider ratio |
|---|---|
| X0 | 1:1 |
| X1 | 1:10 |
| X2 | 1:50 |
| X3 | 1:100 |
| X4–X7 | Free — available for additional measurement channels |

## ADS1115 Datasheet Reference (SBAS444A, TI)

Key limits pulled directly from the TI datasheet — these are what the "Protection" section above
is actually protecting against:

| Parameter | Absolute maximum | Why it matters here |
|---|---|---|
| Analog input voltage to GND | `GND − 0.3 V` to `VDD + 0.3 V` | The resistive divider must never let more than ~5.3 V reach AIN0 even during the 1:100-range fault window |
| Analog input current | 100 mA momentary / 10 mA continuous | Sets the minimum size of the series limiting resistor ahead of AIN0 |
| Supply voltage (VDD) | 2.0 V – 5.5 V | Arduino UNO's 5 V rail is within spec |
| Resolution | 16 bits, no missing codes | Matches the `ΔV_LSB = V_fs / 2^15` formula used throughout this project |
| PGA gain settings | 2/3, 1, 2, 4, 8, 16 → FS = ±6.144 V, ±4.096 V, ±2.048 V, ±1.024 V, ±0.512 V, ±0.256 V | Firmware uses `GAIN_TWOTHIRDS` (±6.144 V) for headroom above the nominal 100 V input range |
| Default I²C address | `1001000` (0x48) when `ADDR` is tied to GND | Matches `ads.begin()` with no address argument in the firmware |
| Max sample rate | 860 SPS | Firmware runs well below this (1 reading/second) — no timing margin concerns |

If the input can ever exceed the divider network's designed maximum (e.g. someone probes a
higher rail than 100 V on the 1:100 range), add a Schottky clamp diode pair to VDD/GND right at
the AIN0 pin, per the datasheet's own recommendation for input overdrive protection.

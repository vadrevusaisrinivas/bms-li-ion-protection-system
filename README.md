# Arduino-Based Li-ion Battery Protection & Monitoring System

**Author:** Sai Srinivas Vadrevu | ECE Graduate, ACE Engineering College, Hyderabad  
**Domain:** Battery Management Systems (BMS) | Embedded Systems | EV Electronics  

---

## Project Overview

A full-stack BMS prototype implementing the core algorithms and protection logic found in production EV battery packs. The system was designed on Arduino Uno hardware and validated through a Python simulation pipeline before hardware deployment.

### What it does

| Feature | Implementation |
|---|---|
| SOC Estimation | Coulomb counting (`SOC = SOC₀ − ∫I·dt / Q_nom`) |
| Voltage monitoring | Resistor-divider circuit → Arduino ADC |
| Thermal monitoring | DHT11 sensor → threshold comparison |
| Fault protection | Relay auto-disconnects on OV / UV / OT |
| Hysteresis recovery | Relay re-closes only when V and T recover to safe range |
| Data logging | Python (pyserial + pandas) → real-time CSV export |
| Validation | MATLAB/Simulink discharge model vs embedded algorithm |

---

## Protection Thresholds

| Parameter | Threshold | Action |
|---|---|---|
| Overvoltage | > 4.20 V | Relay OPEN (load disconnect) |
| Undervoltage | < 3.00 V | Relay OPEN |
| Overtemperature | > 45 °C | Relay OPEN |
| UV Recovery | ≥ 3.10 V | Relay re-closes |
| OT Recovery | ≤ 40 °C | Relay re-closes |

---

## Repository Structure
bms_project/
├── bms_simulator.py        # Python simulation (full BMS pipeline)
├── bms_arduino/
│   └── bms_arduino.ino     # Arduino firmware (hardware deployment)
├── bms_telemetry_log.csv   # 7200-row data log from simulation
├── bms_dashboard.png       # 4-panel telemetry dashboard
└── README.md

---

## Python Simulation (Laptop / No Hardware Required)

Simulates 2 hours of Li-ion discharge at 0.5C rate with full fault detection.

### Install dependencies

```bash
pip install matplotlib pandas numpy
```

### Run

```bash
python bms_simulator.py
```

### Output

- `bms_telemetry_log.csv` — 7200 rows of voltage, SOC%, temperature, fault flags, relay state
- `bms_dashboard.png` — 4-panel dashboard plot

---

## Arduino Firmware

Hardware: Arduino Uno + resistor-divider voltage sense + DHT11 + 5V relay module + 16x2 LCD

Flash `bms_arduino/bms_arduino.ino` via Arduino IDE.  
Serial monitor at 9600 baud streams live telemetry for pyserial capture.

---

## Technical Concepts Demonstrated

- **Coulomb counting** with SOC error accumulation awareness
- **OCV-SOC lookup table** derived from Li-ion NMC cell characterisation
- **Equivalent circuit model**: `V_terminal = OCV(SOC) − I × R_internal`
- **Thermal model**: `dT/dt = (I²R − k(T − T_amb)) / C_th`
- **Relay hysteresis** to prevent relay chatter at threshold boundaries
- **Real-time data acquisition** pipeline (Arduino → pyserial → pandas → CSV)
- **MATLAB/Simulink** model validation of embedded Coulomb counting algorithm

---

## Certifications (supporting this project)

- MATLAB Onramp — MathWorks (2025)
- Simulink Onramp — MathWorks (2025)
- Embedded Systems Onramp — MathWorks (2025)
- Pursuing: Battery Management Systems — University of Colorado, Coursera (Prof. Greg Plett)

---

## Contact

vadrevusaisrinivas15@gmail.com | 

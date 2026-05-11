"""
BMS Serial Data Logger
Author : Sai Srinivas Vadrevu
Purpose: Reads live telemetry from Arduino BMS over USB serial port,
         logs to CSV in real-time, and plots live graphs.

Hardware connection:
  Arduino Uno → USB → PC (appears as COM3 on Windows / /dev/ttyUSB0 on Linux)

Arduino serial output format (9600 baud):
  TIME_MS,VOLTAGE_V,SOC_PCT,TEMP_C,RELAY,FAULT

Usage:
  pip install pyserial matplotlib pandas
  python pyserial_logger.py

  Change PORT below to match your system:
    Windows : "COM3"  (check Device Manager)
    Linux   : "/dev/ttyUSB0"
    Mac     : "/dev/cu.usbmodem14101"
"""

import serial
import csv
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import pandas as pd
from datetime import datetime
import os

# ─────────────────────────────────────────────
# CONFIGURATION — change PORT to your COM port
# ─────────────────────────────────────────────
PORT     = "COM3"          # Windows default — change if needed
BAUD     = 9600
LOG_FILE = f"bms_live_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
MAX_PLOT_POINTS = 120      # Show last 2 minutes on live plot

# ─────────────────────────────────────────────
# DATA STORAGE
# ─────────────────────────────────────────────
timestamps  = []
voltages    = []
soc_values  = []
temps       = []
relay_state = []

# ─────────────────────────────────────────────
# OPEN SERIAL PORT + CSV FILE
# ─────────────────────────────────────────────
def open_serial():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=2)
        print(f"  Connected to {PORT} at {BAUD} baud")
        return ser
    except serial.SerialException as e:
        print(f"  ERROR: Could not open {PORT}")
        print(f"  → {e}")
        print(f"  → Check Device Manager for correct COM port")
        return None

def parse_line(line):
    """Parse one CSV line from Arduino serial output."""
    try:
        parts = line.strip().split(",")
        if len(parts) < 6 or parts[0] == "TIME_MS":
            return None   # skip header line
        return {
            "time_ms":   int(parts[0]),
            "voltage":   float(parts[1]),
            "soc":       float(parts[2]),
            "temp":      float(parts[3]),
            "relay":     int(parts[4]),
            "fault":     parts[5].strip()
        }
    except (ValueError, IndexError):
        return None

# ─────────────────────────────────────────────
# LIVE PLOT SETUP
# ─────────────────────────────────────────────
fig, axes = plt.subplots(3, 1, figsize=(10, 8), facecolor="#0d1117")
fig.suptitle("BMS Live Telemetry — Sai Srinivas Vadrevu",
             color="white", fontsize=13, fontweight="bold")

ax_v, ax_s, ax_t = axes
for ax in axes:
    ax.set_facecolor("#161b22")
    ax.tick_params(colors="#768390", labelsize=8)
    ax.grid(True, color="#21262d", linewidth=0.5)

line_v, = ax_v.plot([], [], color="#58a6ff", linewidth=1.8)
line_s, = ax_s.plot([], [], color="#3fb950", linewidth=1.8)
line_t, = ax_t.plot([], [], color="#e3b341", linewidth=1.8)

ax_v.set_ylabel("Voltage (V)", color="#adbac7", fontsize=9)
ax_s.set_ylabel("SOC (%)",     color="#adbac7", fontsize=9)
ax_t.set_ylabel("Temp (°C)",   color="#adbac7", fontsize=9)
ax_t.set_xlabel("Samples",     color="#adbac7", fontsize=9)

ax_v.axhline(4.20, color="#f85149", linestyle="--", linewidth=0.8, label="OV limit")
ax_v.axhline(3.00, color="#d29922", linestyle="--", linewidth=0.8, label="UV limit")
ax_v.legend(fontsize=8, facecolor="#21262d", edgecolor="#30363d", labelcolor="#adbac7")
ax_t.axhline(45.0, color="#f85149", linestyle="--", linewidth=0.8, label="OT limit")
ax_t.legend(fontsize=8, facecolor="#21262d", edgecolor="#30363d", labelcolor="#adbac7")

plt.tight_layout(rect=[0, 0, 1, 0.95])

# ─────────────────────────────────────────────
# ANIMATION UPDATE FUNCTION
# ─────────────────────────────────────────────
ser = None
csv_file = None
csv_writer = None

def update(frame):
    global ser, csv_writer, csv_file

    if ser is None or not ser.is_open:
        return line_v, line_s, line_t

    try:
        raw = ser.readline().decode("utf-8", errors="ignore")
        data = parse_line(raw)
        if data is None:
            return line_v, line_s, line_t

        # Append to lists
        timestamps.append(len(timestamps))
        voltages.append(data["voltage"])
        soc_values.append(data["soc"])
        temps.append(data["temp"])
        relay_state.append(data["relay"])

        # Write to CSV
        csv_writer.writerow([
            data["time_ms"], data["voltage"], data["soc"],
            data["temp"], data["relay"], data["fault"]
        ])
        csv_file.flush()   # write immediately, don't buffer

        # Console output
        status = "RELAY:ON " if data["relay"] else "RELAY:OFF"
        print(f"  V={data['voltage']:.3f}V | SOC={data['soc']:.1f}% | "
              f"T={data['temp']:.1f}°C | {status} | {data['fault']}")

        # Update plots (last N points only)
        x = timestamps[-MAX_PLOT_POINTS:]
        line_v.set_data(x, voltages[-MAX_PLOT_POINTS:])
        line_s.set_data(x, soc_values[-MAX_PLOT_POINTS:])
        line_t.set_data(x, temps[-MAX_PLOT_POINTS:])

        for ax in axes:
            ax.relim()
            ax.autoscale_view()

    except Exception as e:
        print(f"  Read error: {e}")

    return line_v, line_s, line_t

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  BMS pyserial Logger — Sai Srinivas Vadrevu")
    print("=" * 50)
    print(f"  Port    : {PORT}")
    print(f"  Log file: {LOG_FILE}")
    print(f"  Press Ctrl+C to stop and save")
    print("=" * 50)

    ser = open_serial()

    if ser:
        csv_file   = open(LOG_FILE, "w", newline="")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["TIME_MS","VOLTAGE_V","SOC_PCT","TEMP_C","RELAY","FAULT"])

        try:
            ani = animation.FuncAnimation(fig, update, interval=1000, blit=False)
            plt.show()
        except KeyboardInterrupt:
            print(f"\n  Stopped. Data saved to {LOG_FILE}")
        finally:
            ser.close()
            csv_file.close()
            df = pd.read_csv(LOG_FILE)
            print(f"  Total rows logged : {len(df)}")
            print(f"  Duration          : {len(df)} seconds")
            print(f"  Min voltage       : {df['VOLTAGE_V'].min():.3f} V")
            print(f"  Max temperature   : {df['TEMP_C'].max():.1f} °C")
    else:
        print("\n  No Arduino connected — running in demo mode")
        print("  (Connect Arduino and change PORT to use live logging)")

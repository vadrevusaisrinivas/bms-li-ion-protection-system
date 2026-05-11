"""
Arduino-Based Li-ion Battery Protection & Monitoring System
--- Software Simulation (Laptop Version) ---
Author: Sai Srinivas Vadrevu
Description:
    Simulates a full BMS pipeline:
    - Li-ion cell discharge model (OCV lookup + internal resistance)
    - Coulomb counting for real-time SOC% estimation
    - Overvoltage / Undervoltage / Overtemperature fault detection
    - Relay (load disconnect) logic with hysteresis
    - Thermal model (temperature rises with current, cools at rest)
    - CSV data logging (mimics pyserial data capture from Arduino)
    - 4-panel plot output (voltage, SOC, temperature, fault flags)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import os

# ─────────────────────────────────────────────
# 1. CELL PARAMETERS (Li-ion 18650 typical)
# ─────────────────────────────────────────────
Q_NOM       = 3.0       # Ah — nominal capacity
R_INT       = 0.075     # Ohms — internal resistance
CURRENT     = 1.5       # A — constant discharge current (0.5C rate)
DT          = 1.0       # seconds — simulation timestep

# Protection thresholds
V_MAX       = 4.20      # V — overvoltage cutoff
V_MIN       = 3.00      # V — undervoltage cutoff
T_MAX       = 45.0      # °C — overtemperature cutoff
V_RECOVER   = 3.10      # V — voltage to re-close relay after undervoltage
T_RECOVER   = 40.0      # °C — temperature to re-close relay after overtemp
T_AMBIENT   = 25.0      # °C — ambient temperature

# Simulation duration
SIM_SECONDS = 7200      # 2 hours = full discharge at 0.5C

# ─────────────────────────────────────────────
# 2. OCV vs SOC LOOKUP TABLE
#    (Typical Li-ion NMC cell, derived from
#     Plett's Battery Management Systems course)
# ─────────────────────────────────────────────
SOC_POINTS = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
OCV_POINTS = np.array([3.00, 3.30, 3.50, 3.60, 3.68, 3.73, 3.80, 3.88, 3.95, 4.07, 4.20])

def ocv_from_soc(soc):
    """Interpolate OCV from SOC using lookup table."""
    return float(np.interp(soc, SOC_POINTS, OCV_POINTS))

# ─────────────────────────────────────────────
# 3. THERMAL MODEL
#    Temperature rises due to I²R heating,
#    cools toward ambient via Newton's law.
# ─────────────────────────────────────────────
THERMAL_MASS   = 800.0   # J/°C — cell + holder thermal mass
COOLING_COEFF  = 2.5     # W/°C — natural convection cooling

def update_temperature(T, I_effective, dt):
    """
    dT/dt = (I²R - k*(T - T_amb)) / C_th
    I_effective = 0 when relay is open (no current)
    """
    heat_gen  = (I_effective ** 2) * R_INT
    heat_loss = COOLING_COEFF * (T - T_AMBIENT)
    dT = (heat_gen - heat_loss) * dt / THERMAL_MASS
    return T + dT

# ─────────────────────────────────────────────
# 4. MAIN SIMULATION LOOP
# ─────────────────────────────────────────────
def run_simulation():
    print("=" * 55)
    print("  Li-ion BMS Simulator — Sai Srinivas Vadrevu")
    print("=" * 55)
    print(f"  Cell capacity  : {Q_NOM} Ah")
    print(f"  Discharge rate : {CURRENT} A ({CURRENT/Q_NOM:.2f}C)")
    print(f"  Thresholds     : V>{V_MAX}V | V<{V_MIN}V | T>{T_MAX}°C")
    print(f"  Duration       : {SIM_SECONDS//3600} hrs {(SIM_SECONDS%3600)//60} min")
    print("=" * 55)

    # State variables
    soc         = 1.0           # 100% charged
    temperature = T_AMBIENT     # start at ambient
    relay_closed = True         # relay ON = load connected
    charge_removed = 0.0        # Ah — for Coulomb counting

    # Fault flags
    fault_overvoltage    = False
    fault_undervoltage   = False
    fault_overtemperature = False

    # Log storage
    records = []

    for t in range(SIM_SECONDS):
        # Effective current (zero if relay open / load disconnected)
        I_eff = CURRENT if relay_closed else 0.0

        # --- Coulomb Counting (SOC estimation) ---
        charge_removed += I_eff * (DT / 3600.0)   # convert seconds to hours
        soc = max(0.0, 1.0 - (charge_removed / Q_NOM))

        # --- Voltage model ---
        ocv = ocv_from_soc(soc)
        v_terminal = ocv - (I_eff * R_INT)

        # --- Thermal model ---
        temperature = update_temperature(temperature, I_eff, DT)

        # --- Fault detection ---
        fault_overvoltage     = v_terminal > V_MAX
        fault_undervoltage    = v_terminal < V_MIN
        fault_overtemperature = temperature > T_MAX

        any_fault = fault_overvoltage or fault_undervoltage or fault_overtemperature

        # --- Relay logic with hysteresis ---
        if any_fault:
            relay_closed = False
        else:
            # Re-close only when conditions recover
            if not relay_closed:
                v_ok = v_terminal >= V_RECOVER
                t_ok = temperature <= T_RECOVER
                if v_ok and t_ok:
                    relay_closed = True

        # --- Log every second ---
        records.append({
            "time_s":              t,
            "time_min":            round(t / 60.0, 2),
            "voltage_V":           round(v_terminal, 4),
            "soc_pct":             round(soc * 100, 2),
            "temperature_C":       round(temperature, 3),
            "relay_closed":        int(relay_closed),
            "fault_overvoltage":   int(fault_overvoltage),
            "fault_undervoltage":  int(fault_undervoltage),
            "fault_overtemp":      int(fault_overtemperature),
            "current_A":           round(I_eff, 3),
        })

        # Console output every 10 minutes
        if t % 600 == 0:
            status = "RELAY:ON " if relay_closed else "RELAY:OFF"
            fault_str = ""
            if fault_undervoltage:    fault_str += "[UV] "
            if fault_overvoltage:     fault_str += "[OV] "
            if fault_overtemperature: fault_str += "[OT] "
            if not fault_str:         fault_str = "OK"
            print(f"  t={t//60:3d}min | V={v_terminal:.3f}V | SOC={soc*100:5.1f}% "
                  f"| T={temperature:.1f}°C | {status} | {fault_str}")

    print("=" * 55)
    print("  Simulation complete.")
    return pd.DataFrame(records)

# ─────────────────────────────────────────────
# 5. CSV EXPORT (mimics pyserial logger)
# ─────────────────────────────────────────────
def export_csv(df, path="bms_telemetry_log.csv"):
    df.to_csv(path, index=False)
    print(f"  CSV exported → {path}  ({len(df)} rows)")
    return path

# ─────────────────────────────────────────────
# 6. PLOTTING (4-panel dashboard)
# ─────────────────────────────────────────────
def plot_results(df, save_path="bms_dashboard.png"):
    fig = plt.figure(figsize=(14, 10), facecolor="#0d1117")
    fig.suptitle(
        "Li-ion BMS Simulation Dashboard\n"
        "Sai Srinivas Vadrevu | Arduino-Based BMS Project",
        fontsize=14, color="white", fontweight="bold", y=0.98
    )

    gs = gridspec.GridSpec(4, 1, hspace=0.55, top=0.91, bottom=0.07,
                           left=0.09, right=0.97)

    style = dict(linewidth=1.8)
    tick_color = "#768390"
    label_color = "#adbac7"
    grid_color = "#21262d"

    def style_ax(ax, title):
        ax.set_facecolor("#161b22")
        ax.set_title(title, color="white", pad=6, fontsize=11)
        ax.tick_params(colors=tick_color, labelsize=8)
        ax.grid(True, color=grid_color, linewidth=0.5)
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")

    t = df["time_min"]

    # Panel 1 — Voltage
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(t, df["voltage_V"], color="#58a6ff", **style, label="Terminal V")
    ax1.axhline(V_MAX, color="#f85149", linestyle="--", linewidth=1, label=f"OV limit ({V_MAX}V)")
    ax1.axhline(V_MIN, color="#d29922", linestyle="--", linewidth=1, label=f"UV limit ({V_MIN}V)")
    ax1.set_ylabel("Voltage (V)", color=label_color, fontsize=9)
    style_ax(ax1, "Terminal Voltage vs Time")
    ax1.legend(fontsize=8, loc="upper right",
               facecolor="#21262d", edgecolor="#30363d", labelcolor=label_color)

    # Panel 2 — SOC
    ax2 = fig.add_subplot(gs[1])
    ax2.plot(t, df["soc_pct"], color="#3fb950", **style)
    ax2.axhline(20, color="#d29922", linestyle="--", linewidth=1, label="Low SOC warning (20%)")
    ax2.set_ylabel("SOC (%)", color=label_color, fontsize=9)
    style_ax(ax2, "State of Charge (Coulomb Counting)")
    ax2.legend(fontsize=8, loc="upper right",
               facecolor="#21262d", edgecolor="#30363d", labelcolor=label_color)

    # Panel 3 — Temperature
    ax3 = fig.add_subplot(gs[2])
    ax3.plot(t, df["temperature_C"], color="#e3b341", **style)
    ax3.axhline(T_MAX, color="#f85149", linestyle="--", linewidth=1, label=f"OT limit ({T_MAX}°C)")
    ax3.set_ylabel("Temp (°C)", color=label_color, fontsize=9)
    style_ax(ax3, "Cell Temperature (Thermal Model)")
    ax3.legend(fontsize=8, loc="upper right",
               facecolor="#21262d", edgecolor="#30363d", labelcolor=label_color)

    # Panel 4 — Fault flags + relay
    ax4 = fig.add_subplot(gs[3])
    ax4.fill_between(t, df["fault_undervoltage"],  alpha=0.7, color="#d29922", label="Undervoltage fault", step="post")
    ax4.fill_between(t, df["fault_overvoltage"],   alpha=0.7, color="#f85149", label="Overvoltage fault",  step="post")
    ax4.fill_between(t, df["fault_overtemp"],      alpha=0.7, color="#bc8cff", label="Overtemp fault",     step="post")
    ax4.plot(t, df["relay_closed"], color="#58a6ff", linewidth=1.2,
             linestyle=":", label="Relay closed")
    ax4.set_ylabel("Fault / Relay", color=label_color, fontsize=9)
    ax4.set_xlabel("Time (minutes)", color=label_color, fontsize=9)
    style_ax(ax4, "Fault Detection & Relay State")
    ax4.set_ylim(-0.05, 1.3)
    ax4.legend(fontsize=8, loc="upper right",
               facecolor="#21262d", edgecolor="#30363d", labelcolor=label_color, ncol=2)

    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    print(f"  Dashboard saved → {save_path}")
    return save_path

# ─────────────────────────────────────────────
# 7. SUMMARY STATS (what you tell the interviewer)
# ─────────────────────────────────────────────
def print_summary(df):
    print("\n" + "=" * 55)
    print("  SIMULATION SUMMARY (tell this in interview)")
    print("=" * 55)
    discharge_end = df[df["soc_pct"] <= 5]
    if not discharge_end.empty:
        end_t = discharge_end.iloc[0]["time_min"]
        print(f"  Discharge time to 5% SOC : {end_t:.1f} min")
    faults_uv = df["fault_undervoltage"].sum()
    faults_ot = df["fault_overtemp"].sum()
    relay_open = (df["relay_closed"] == 0).sum()
    print(f"  UV fault events (seconds): {faults_uv}")
    print(f"  OT fault events (seconds): {faults_ot}")
    print(f"  Relay open time (seconds): {relay_open}")
    print(f"  Peak temperature          : {df['temperature_C'].max():.2f}°C")
    print(f"  Min voltage observed      : {df['voltage_V'].min():.4f}V")
    print(f"  Total data points logged  : {len(df)}")
    print("=" * 55)
    print("\n  FILES GENERATED:")
    print("   bms_telemetry_log.csv  — your data logger output")
    print("   bms_dashboard.png      — your 4-panel dashboard")
    print("\n  Upload both to GitHub. Screenshot the dashboard.")
    print("  In the interview, say:")
    print('  "I simulated 2 hours of Li-ion discharge at 0.5C,')
    print('   logging voltage, SOC, temperature, and fault states')
    print('   every second — 7200 data points — then validated')
    print('   the Coulomb counting algorithm against the OCV-SOC')
    print('   lookup table derived from Plett\'s BMS course."')
    print("=" * 55)

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path  = os.path.join(out_dir, "bms_telemetry_log.csv")
    plot_path = os.path.join(out_dir, "bms_dashboard.png")

    df = run_simulation()
    export_csv(df, csv_path)
    plot_results(df, plot_path)
    print_summary(df)

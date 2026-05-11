/*
 * Arduino-Based Li-ion Battery Protection & Monitoring System
 * Author  : Sai Srinivas Vadrevu
 * Hardware: Arduino Uno + DHT11 + Relay Module + 16x2 LCD (I2C)
 * 
 * Thresholds:
 *   Overvoltage     : > 4.20 V  → relay OPEN
 *   Undervoltage    : < 3.00 V  → relay OPEN
 *   Overtemperature : > 45 °C   → relay OPEN
 *   UV Recovery     : >= 3.10 V → relay re-closes
 *   OT Recovery     : <= 40 °C  → relay re-closes
 *
 * Serial output at 9600 baud (capture with Python pyserial):
 *   TIME_MS,VOLTAGE,SOC,TEMP,RELAY,FAULT
 */

#include <DHT.h>
#include <LiquidCrystal_I2C.h>

// ── Pin definitions ───────────────────────────────────────────
#define VOLTAGE_PIN     A0      // Resistor-divider output
#define DHT_PIN         7       // DHT11 data pin
#define RELAY_PIN       8       // Relay IN pin (LOW = relay ON)
#define DHT_TYPE        DHT11

// ── Hardware objects ─────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ── Voltage sense: resistor divider R1=100k, R2=47k ─────────
// V_battery = V_adc * (R1 + R2) / R2 * (5.0 / 1023.0)
const float R1 = 100000.0;
const float R2 = 47000.0;
const float V_REF = 5.0;
const float ADC_MAX = 1023.0;

// ── Cell parameters ──────────────────────────────────────────
const float Q_NOM    = 3.0;     // Ah — nominal capacity
const float V_MAX    = 4.20;    // Overvoltage threshold
const float V_MIN    = 3.00;    // Undervoltage threshold
const float T_MAX    = 45.0;    // Overtemperature threshold
const float V_RECOVER = 3.10;   // UV recovery voltage
const float T_RECOVER = 40.0;   // OT recovery temperature

// ── OCV-SOC lookup table (10 points, NMC cell) ───────────────
const int   OCV_POINTS = 11;
const float SOC_TBL[OCV_POINTS] = {0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0};
const float OCV_TBL[OCV_POINTS] = {3.00,3.30,3.50,3.60,3.68,3.73,3.80,3.88,3.95,4.07,4.20};

// ── State variables ──────────────────────────────────────────
float soc          = 1.0;           // Initial SOC = 100%
float chargeUsed   = 0.0;           // Ah consumed (Coulomb counting)
bool  relayClosed  = true;
unsigned long lastTime = 0;
bool  faultUV = false, faultOV = false, faultOT = false;

// ── Helpers ──────────────────────────────────────────────────
float readVoltage() {
  int raw = analogRead(VOLTAGE_PIN);
  float v_adc = raw * (V_REF / ADC_MAX);
  return v_adc * (R1 + R2) / R2;
}

float ocvFromSoc(float s) {
  // Linear interpolation on OCV-SOC table
  if (s <= 0.0) return OCV_TBL[0];
  if (s >= 1.0) return OCV_TBL[OCV_POINTS - 1];
  for (int i = 0; i < OCV_POINTS - 1; i++) {
    if (s >= SOC_TBL[i] && s <= SOC_TBL[i+1]) {
      float t = (s - SOC_TBL[i]) / (SOC_TBL[i+1] - SOC_TBL[i]);
      return OCV_TBL[i] + t * (OCV_TBL[i+1] - OCV_TBL[i]);
    }
  }
  return OCV_TBL[OCV_POINTS - 1];
}

// ── Setup ─────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  dht.begin();
  lcd.init();
  lcd.backlight();
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);   // Relay ON (active-low module)

  // Print CSV header for pyserial capture
  Serial.println("TIME_MS,VOLTAGE_V,SOC_PCT,TEMP_C,RELAY,FAULT");

  lcd.setCursor(0, 0);
  lcd.print("BMS v1.0 READY");
  lcd.setCursor(0, 1);
  lcd.print("SAI SRINIVAS");
  delay(2000);
  lcd.clear();

  lastTime = millis();
}

// ── Main loop ─────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();
  float dt_hr = (now - lastTime) / 3600000.0;  // ms → hours
  lastTime = now;

  // 1. Read sensors
  float voltage = readVoltage();
  float temp    = dht.readTemperature();
  if (isnan(temp)) temp = 25.0;   // fallback if DHT read fails

  // 2. Coulomb counting
  float current = relayClosed ? 1.5 : 0.0;   // A (or use ACS712 current sensor)
  chargeUsed += current * dt_hr;
  soc = max(0.0f, 1.0f - (chargeUsed / Q_NOM));

  // 3. Fault detection
  faultOV = (voltage > V_MAX);
  faultUV = (voltage < V_MIN);
  faultOT = (temp    > T_MAX);

  // 4. Relay control with hysteresis
  if (faultOV || faultUV || faultOT) {
    relayClosed = false;
    digitalWrite(RELAY_PIN, HIGH);   // Relay OFF
  } else if (!relayClosed) {
    if (voltage >= V_RECOVER && temp <= T_RECOVER) {
      relayClosed = true;
      digitalWrite(RELAY_PIN, LOW);  // Relay ON
    }
  }

  // 5. Build fault string
  String fault = "OK";
  if (faultOV) fault = "OV";
  else if (faultUV) fault = "UV";
  else if (faultOT) fault = "OT";

  // 6. Serial log (pyserial captures this)
  Serial.print(now);        Serial.print(",");
  Serial.print(voltage, 3); Serial.print(",");
  Serial.print(soc * 100, 1); Serial.print(",");
  Serial.print(temp, 1);    Serial.print(",");
  Serial.print(relayClosed ? "1" : "0"); Serial.print(",");
  Serial.println(fault);

  // 7. LCD display
  lcd.setCursor(0, 0);
  lcd.print("V:");
  lcd.print(voltage, 2);
  lcd.print("V SOC:");
  lcd.print((int)(soc * 100));
  lcd.print("%  ");

  lcd.setCursor(0, 1);
  lcd.print("T:");
  lcd.print((int)temp);
  lcd.print((char)223);   // degree symbol
  lcd.print("C ");
  lcd.print(relayClosed ? "RLY:ON " : "RLY:OFF");

  delay(1000);   // 1 Hz sampling
}

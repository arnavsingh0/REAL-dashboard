"""
REAL CubeSat telemetry field definitions.
Extracted verbatim from the notebook — these are the single source of truth
for beacon layout, scaling, and thresholds.

Each field tuple:
  (name, bit_start, bit_count, scale, offset, units, thresholds_dict)

Threshold keys:
  RL = Red Low, YL = Yellow Low, Nom = Nominal,
  YH = Yellow High, RH = Red High
  _signed = True  →  two's-complement interpretation
"""

# ── Beacon framing ──────────────────────────────────────────────────
SYNC_WORD = b"REAL"
HEALTH_BEACON_LENGTH = 189
HEALTH_BEACON_TRIM = 2
TIME_BEACON_LENGTH = 42
TIME_BEACON_TRIM = 2

# ── Time beacon fields ──────────────────────────────────────────────
TIME_FIELDS = [
    ("sync_word",            0,  32, 1.0, 0.0, "raw",         {}),
    ("last_uptime_s",       32,  32, 1.0, 0.0, "s",           {}),
    ("timeFine_sec",        64,  32, 1.0, 0.0, "s",           {}),
    ("timeFine_frac_raw",   96,  32, 1.0, 0.0, "lsb=2^-32 s", {}),
    ("time_onboard_s",     128,  32, 1.0, 0.0, "s",           {}),
    ("uptime_s",           160,  32, 1.0, 0.0, "s",           {}),
    ("mode_checkpoint_s",  192,  32, 1.0, 0.0, "s",           {}),
    ("gps_time_s",         224,  32, 1.0, 0.0, "s",           {}),
    ("tai_seconds",        256,  64, 1.0, 0.0, "s",           {}),
]

# ── Health beacon fields ────────────────────────────────────────────
HEALTH_FIELDS = [
    ('sync_word', 0, 32, 1.0, 0.0, 'raw', {}),
    ('bat_charging_status', 32, 1, 1.0, 0.0, 'raw', {}),
    ('5v_bat_current', 33, 10, 1.327547, 0.0, 'mA', {'RL': 3.75, 'YL': 4.0, 'Nom': 5.6, 'YH': 7.75, 'RH': 8.0}),
    ('3v3_bat_current', 43, 10, 1.327547, 0.0, 'mA', {'RL': 1.2, 'YL': 1.4, 'Nom': 2.65, 'YH': 2.85, 'RH': 3.0}),
    ('vbat_bat_current', 53, 10, 14.662757, 0.0, 'mA', {'Nom': 475.0, 'YH': 900.0, 'RH': 1300.0}),
    ('3v3_bat_voltage', 63, 10, 0.004311, 0.0, 'V', {'RL': 3.24, 'YL': 3.26, 'Nom': 3.33, 'YH': 3.355, 'RH': 3.37}),
    ('5v_bat_voltage', 73, 10, 0.005865, 0.0, 'V', {'RL': 4.935, 'YL': 4.95, 'Nom': 5.04, 'YH': 5.055, 'RH': 5.07}),
    ('vbat_bat_voltage', 83, 10, 0.008993, 0.0, 'V', {'RL': 7.2, 'YL': 7.4, 'Nom': 7.8, 'YH': 8.45, 'RH': 8.5}),
    ('bat_board_temperature', 93, 10, 0.372434, -273.15, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 50.0}),
    ('bat_cell_1_temperature', 103, 10, 0.3976, -238.57, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 50.0}),
    ('bat_cell_2_temperature', 113, 10, 0.3976, -238.57, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 50.0}),
    ('bat_cell_3_temperature', 123, 10, 0.3976, -238.57, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 50.0}),
    ('bat_cell_4_temperature', 133, 10, 0.3976, -238.57, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 50.0}),
    ('battery_heater_status', 143, 40, 1.0, 0.0, 'raw', {}),
    ('vbat_eps_voltage', 183, 10, 0.008978, 0.0, 'V', {'RL': 7.2, 'YL': 7.4, 'Nom': 7.8, 'YH': 8.45, 'RH': 8.5}),
    ('3v3_eps_voltage', 193, 10, 0.004311, 0.0, 'V', {'RL': 3.24, 'YL': 3.26, 'Nom': 3.33, 'YH': 3.355, 'RH': 3.37}),
    ('5v_eps_voltage', 203, 10, 0.005865, 0.0, 'V', {'RL': 4.935, 'YL': 4.95, 'Nom': 5.04, 'YH': 5.055, 'RH': 5.07}),
    ('12v_eps_voltage', 213, 10, 0.01349, 0.0, 'V', {'RL': 11.8, 'YL': 11.88, 'Nom': 12.08, 'YH': 12.12, 'RH': 12.2}),
    ('vbat_eps_current', 223, 10, 0.005237, 0.0, 'A', {'Nom': 0.6, 'YH': 0.925, 'RH': 1.1}),
    ('3v3_eps_current', 233, 10, 0.005237, 0.0, 'A', {'RL': 0.075, 'YL': 0.1, 'Nom': 0.135, 'YH': 0.5, 'RH': 0.675}),
    ('5v_eps_current', 243, 10, 0.005237, 0.0, 'A', {'RL': 0.0, 'YL': 0.005, 'Nom': 0.01, 'YH': 0.05, 'RH': 0.1}),
    ('12v_eps_current', 253, 10, 0.00682, 0.0, 'A', {'RL': 0.075, 'YL': 0.1, 'Nom': 0.135, 'YH': 0.275, 'RH': 0.425}),
    ('sw1_unused_voltage', 263, 10, 0.01349, 0.0, 'V', {}),
    ('sw2_unused_voltage', 273, 10, 0.01349, 0.0, 'V', {}),
    ('sw3_instrument_voltage', 283, 10, 0.008993, 0.0, 'V', {'Nom': 7.8, 'YH': 8.45, 'RH': 8.5}),
    ('sw4_li2_voltage', 293, 10, 0.008993, 0.0, 'V', {'RL': 7.2, 'YL': 7.4, 'Nom': 7.8, 'YH': 8.45, 'RH': 8.5}),
    ('sw5_uhf_temp_sensor_voltage', 303, 10, 0.005868, 0.0, 'V', {'Nom': 0.03, 'YH': 1.0, 'RH': 5.07}),
    ('sw6_unused_voltage', 313, 10, 0.005868, 0.0, 'V', {'YL': 0.012, 'Nom': 1.0, 'YH': 5.07}),
    ('sw7_unused_voltage', 323, 10, 0.005868, 0.0, 'V', {'YL': 0.012, 'Nom': 1.0, 'YH': 5.07}),
    ('sw8_xact_serial_voltage', 333, 10, 0.004311, 0.0, 'V', {'RL': 3.24, 'YL': 3.26, 'Nom': 3.34, 'YH': 3.355, 'RH': 3.37}),
    ('sw9_gps_voltage', 343, 10, 0.004311, 0.0, 'V', {'RL': 3.24, 'YL': 3.26, 'Nom': 3.31, 'YH': 3.355, 'RH': 3.37}),
    ('sw10_instrument_lvds_voltage', 353, 10, 0.004311, 0.0, 'V', {'Nom': 3.33, 'YH': 3.355, 'RH': 3.37}),
    ('sw1_unused_current', 363, 10, 0.001328, 0.0, 'A', {}),
    ('sw2_unused_current', 373, 10, 0.001328, 0.0, 'A', {}),
    ('sw3_instrument_current', 383, 10, 0.006239, 0.0, 'A', {'Nom': 0.012, 'YH': 0.44, 'RH': 0.45}),
    ('sw4_li2_current', 393, 10, 0.006239, 0.0, 'A', {'RL': 0.005, 'YL': 0.008, 'Nom': 0.012, 'YH': 0.15, 'RH': 0.16}),
    ('sw5_uhf_temp_sensor_current', 403, 10, 0.001328, 0.0, 'A', {'Nom': 0.003, 'YH': 0.01, 'RH': 0.015}),
    ('sw6_unused_current', 413, 10, 0.001328, 0.0, 'A', {'YL': 0.003, 'Nom': 0.01, 'YH': 0.015}),
    ('sw7_unused_current', 423, 10, 0.001328, 0.0, 'A', {'YL': 0.003, 'Nom': 0.01, 'YH': 0.015}),
    ('sw8_xact_serial_current', 433, 10, 0.001328, 0.0, 'A', {'RL': 0.02, 'YL': 0.022, 'Nom': 0.028, 'YH': 0.035, 'RH': 0.04}),
    ('sw9_gps_current', 443, 10, 0.001328, 0.0, 'A', {'Nom': 0.003, 'YH': 0.4, 'RH': 0.435}),
    ('sw10_instrument_lvds_current', 453, 10, 0.001328, 0.0, 'A', {'Nom': 0.003, 'YH': 0.014, 'RH': 0.015}),
    ('eps_mb_temperature', 463, 10, 0.372434, -273.15, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 60.0}),
    ('eps_db_temperature', 473, 10, 0.372434, -273.15, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 60.0}),
    ('sa1_salw_inner_voltage', 483, 10, 0.0322581, 0.0, 'V', {'RL': 0.5, 'YL': 0.75, 'Nom': 16.64, 'YH': 18.5, 'RH': 19.0}),
    ('sa2_salw_outer_voltage', 493, 10, 0.0322581, 0.0, 'V', {'RL': 0.5, 'YL': 0.75, 'Nom': 16.64, 'YH': 18.5, 'RH': 19.0}),
    ('sa4_sarw_inner_voltage', 503, 10, 0.0322581, 0.0, 'V', {'RL': 0.5, 'YL': 0.75, 'Nom': 16.91, 'YH': 18.5, 'RH': 19.0}),
    ('sa5_sarw_outer_voltage', 513, 10, 0.0322581, 0.0, 'V', {'RL': 0.5, 'YL': 0.75, 'Nom': 16.81, 'YH': 18.5, 'RH': 19.0}),
    ('sa1_salw_inner_current', 523, 10, 0.0009775, 0.0, 'A', {'RL': 0.0, 'YL': 0.02, 'Nom': 0.45, 'YH': 0.455, 'RH': 0.46}),
    ('sa2_salw_outer_current', 533, 10, 0.0009775, 0.0, 'A', {'RL': 0.0, 'YL': 0.02, 'Nom': 0.45, 'YH': 0.455, 'RH': 0.46}),
    ('sa4_sarw_inner_current', 543, 10, 0.0009775, 0.0, 'A', {'RL': 0.0, 'YL': 0.02, 'Nom': 0.45, 'YH': 0.455, 'RH': 0.46}),
    ('sa5_sarw_outer_current', 553, 10, 0.0009775, 0.0, 'A', {'RL': 0.0, 'YL': 0.02, 'Nom': 0.45, 'YH': 0.455, 'RH': 0.46}),
    ('sa1_salw_inner_temperature', 563, 10, 0.4963, -273.15, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 75.0, 'RH': 90.0}),
    ('sa2_salw_outer_temperature', 573, 10, 0.4963, -273.15, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 75.0, 'RH': 90.0}),
    ('sa4_sarw_inner_temperature', 583, 10, 0.4963, -273.15, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 75.0, 'RH': 90.0}),
    ('sa5_sarw_outer_temperature', 593, 10, 0.4963, -273.15, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 75.0, 'RH': 90.0}),
    ('curr_boot_image', 603, 8, 1.0, 0.0, 'raw', {}),
    ('image_valid', 611, 3, 1.0, 0.0, 'raw', {}),
    ('image_priority', 614, 96, 1.0, 0.0, 'raw', {}),
    ('image_is_stable', 710, 1, 1.0, 0.0, 'raw', {}),
    ('adc_enable', 713, 1, 1.0, 0.0, 'raw', {}),
    ('last_reset_cause', 714, 2, 1.0, 0.0, 'raw', {}),
    ('last_boot_count', 716, 32, 1.0, 0.0, 'raw', {}),
    ('version', 748, 32, 1.0, 0.0, 'raw', {}),
    ('interface_baud_rate', 780, 3, 1.0, 0.0, 'bps', {}),
    ('rx_rf_baud_rate', 783, 2, 1.0, 0.0, 'bps', {}),
    ('rx_modulation', 785, 2, 1.0, 0.0, 'raw', {}),
    ('rx_frequency', 787, 32, 1.0, 0.0, 'kHz', {}),
    ('tx_power_amp_level', 819, 8, 1.0, 0.0, 'raw', {}),
    ('tx_rf_baud_rate', 827, 2, 1.0, 0.0, 'bps', {}),
    ('tx_modulation', 829, 2, 1.0, 0.0, 'raw', {}),
    ('tx_frequency', 831, 32, 1.0, 0.0, 'kHz', {}),
    ('source_callsign', 863, 48, 1.0, 0.0, 'raw', {}),
    ('destination_callsign', 911, 48, 1.0, 0.0, 'raw', {}),
    ('rssi', 959, 8, 1.0, 0.0, 'dB', {}),
    ('vbat_obc_voltage', 967, 12, 0.003744404, 0.0, 'V', {'RL': 7.2, 'YL': 7.4, 'Nom': 7.8, 'YH': 8.45, 'RH': 8.5}),
    ('vbat_obc_current', 979, 12, 5.69231e-05, 0.0, 'A', {'RL': 0.03, 'YL': 0.032, 'Nom': 0.034, 'YH': 0.038, 'RH': 0.04}),
    ('vbat_plat_voltage', 991, 12, 0.003744404, 0.0, 'V', {'RL': 7.2, 'YL': 7.4, 'Nom': 7.8, 'YH': 8.45, 'RH': 8.5}),
    ('unused', 1003, 12, 1.0, 0.0, 'raw', {}),
    ('3v3_plat_voltage', 1015, 12, 0.000976801, 0.0, 'V', {'RL': 3.24, 'YL': 3.26, 'Nom': 3.29, 'YH': 3.355, 'RH': 3.37}),
    ('1v2_obc_voltage', 1027, 12, 0.000488401, 0.0, 'V', {'RL': 1.1, 'YL': 1.105, 'Nom': 1.2, 'YH': 1.205, 'RH': 1.3}),
    ('unused_2', 1039, 12, 1.0, 0.0, 'raw', {}),
    ('obc_temperature_1', 1051, 12, 0.048840049, -60.0, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 50.0}),
    ('3v3_obc_voltage', 1063, 12, 0.000976801, 0.0, 'V', {'RL': 3.24, 'YL': 3.26, 'Nom': 3.28, 'YH': 3.355, 'RH': 3.37}),
    ('3v3_obc_current', 1075, 12, 0.000180889, 0.0, 'A', {'RL': 0.07, 'YL': 0.075, 'Nom': 0.08, 'YH': 0.085, 'RH': 0.09}),
    ('3v3_memory_voltage', 1087, 12, 0.000976801, 0.0, 'V', {'RL': 3.24, 'YL': 3.26, 'Nom': 3.28, 'YH': 3.355, 'RH': 3.37}),
    ('3v3_memory_current', 1099, 12, 0.000180889, 0.0, 'A', {'RL': 0.045, 'YL': 0.05, 'Nom': 0.053, 'YH': 0.057, 'RH': 0.06}),
    ('vbat_periph_current', 1111, 12, 2.22e-06, 0.0, 'A', {'YL': 0.0, 'Nom': 0.007, 'YH': 0.01}),
    ('3v3_periph_current', 1123, 12, 2.22e-05, 0.0, 'A', {'Nom': 0.0, 'YH': 0.007, 'RH': 0.01}),
    ('2v5_periph_current', 1135, 12, 2.22e-06, 0.0, 'A', {'Nom': 0.0, 'YH': 0.007, 'RH': 0.01}),
    ('obc_temperature_2', 1147, 12, 0.048840049, -60.0, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 50.0}),
    ('obc_temperature_3', 1159, 12, 0.048840049, -60.0, 'degC', {'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 50.0}),
    ('3v3_gps_voltage', 1171, 12, 0.000717773, 0.0, 'V', {'Nom': 0.0, 'YH': 0.005, 'RH': 0.01}),
    ('3v3_gps_current', 1183, 12, 0.000125231, 0.0, 'A', {'Nom': 0.0, 'YH': 0.005, 'RH': 0.01}),
    ('2v5_obc_voltage', 1195, 12, 0.001085334, 0.0, 'V', {'RL': 2.4, 'YL': 2.405, 'Nom': 2.5, 'YH': 2.505, 'RH': 2.6}),
    ('2v5_periph_voltage', 1207, 12, 0.001085334, 0.0, 'V', {'RL': 2.4, 'YL': 2.405, 'Nom': 2.5, 'YH': 2.505, 'RH': 2.6}),
    ('vbat_periph_voltage', 1219, 12, 0.003744404, 0.0, 'V', {'RL': 7.3, 'YL': 7.7, 'Nom': 8.0, 'YH': 8.45, 'RH': 8.5}),
    ('3v3_periph_voltage', 1231, 12, 0.000976801, 0.0, 'V', {'RL': 3.24, 'YL': 3.26, 'Nom': 3.28, 'YH': 3.355, 'RH': 3.37}),
    ('unused_3', 1243, 12, 1.0, 0.0, 'raw', {}),
    ('system_mode', 1255, 3, 1.0, 0.0, 'raw', {}),
    ('startup_mode', 1258, 3, 1.0, 0.0, 'raw', {}),
    ('pass_in_progress', 1261, 1, 1.0, 0.0, 'raw', {}),
    ('digital_bus_voltage', 1262, 16, 0.00125, 0.0, 'V', {'RL': 4.75, 'YL': 4.8, 'Nom': 4.85, 'YH': 5.15, 'RH': 5.25}),
    ('wheel_bus_voltage', 1278, 16, 0.00125, 0.0, 'V', {'RL': 11.55, 'YL': 11.65, 'Nom': 11.875, 'YH': 12.1, 'RH': 12.2}),
    ('rod_bus_voltage', 1294, 16, 0.00125, 0.0, 'V', {'RL': 11.55, 'YL': 11.65, 'Nom': 11.875, 'YH': 12.1, 'RH': 12.2}),
    ('wheel_1_speed', 1310, 16, 0.4, 0.0, 'rpm', {'_signed': True}),
    ('wheel_2_speed', 1326, 16, 0.4, 0.0, 'rpm', {'_signed': True}),
    ('wheel_3_speed', 1342, 16, 0.4, 0.0, 'rpm', {'_signed': True}),
    ('adcs_mode', 1358, 8, 1.0, 0.0, 'raw', {}),
    ('wheel_1_current', 1366, 16, 0.001, 0.0, 'A', {'YH': 0.1, 'RH': 0.15}),
    ('wheel_2_current', 1382, 16, 0.001, 0.0, 'A', {'YH': 0.1, 'RH': 0.15}),
    ('wheel_3_current', 1398, 16, 0.001, 0.0, 'A', {'YH': 0.1, 'RH': 0.15}),
    ('imu_temp', 1414, 16, 0.005, 0.0, 'degC', {'_signed': True, 'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 60.0}),
    ('wheel_1_temperature', 1430, 16, 0.005, 0.0, 'degC', {'_signed': True, 'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 60.0}),
    ('wheel_2_temperature', 1446, 16, 0.005, 0.0, 'degC', {'_signed': True, 'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 60.0}),
    ('wheel_3_temperature', 1462, 16, 0.005, 0.0, 'degC', {'_signed': True, 'RL': -20.0, 'YL': -10.0, 'YH': 40.0, 'RH': 60.0}),
    ('unused_4', 1478, 16, 1.0, 0.0, 'raw', {}),
]


# ── Helper lookups ──────────────────────────────────────────────────
def field_units(fields: list, name: str) -> str:
    return next((f[5] for f in fields if f[0] == name), "")

def field_thresholds(fields: list, name: str) -> dict:
    meta = next((f[6] for f in fields if f[0] == name), {})
    return {k: v for k, v in meta.items() if k in ("RL", "YL", "Nom", "YH", "RH")}

def field_meta(fields: list) -> list[dict]:
    """Return JSON-serialisable metadata for every field."""
    out = []
    for f in fields:
        name, bit_start, bit_count, scale, offset, units, meta = f
        out.append({
            "name": name,
            "units": units,
            "thresholds": {k: v for k, v in meta.items() if k in ("RL", "YL", "Nom", "YH", "RH")},
            "signed": bool(meta.get("_signed")),
        })
    return out
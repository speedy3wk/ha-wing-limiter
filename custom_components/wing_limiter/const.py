"""Constants for the Wing Limiter integration."""

DOMAIN = "wing_limiter"

# OSC communication
DEFAULT_PORT = 2223
DEFAULT_SCAN_INTERVAL = 5
MAIN_COUNT = 4

# Config entry keys
CONF_SCAN_INTERVAL = "scan_interval"

# OSC address patterns — use .format(main_index) where main_index is 1..4
OSC_COMP_ON = "/main/{}/dyn/on"    # INT 0..1  — compressor switch
OSC_COMP_THR = "/main/{}/dyn/thr"  # FLOAT -60..0 dB — compressor threshold ("37" in spec is a footnote number, NOT part of the path)
OSC_MAIN_NAME = "/main/{}/name"     # STRING — main bus name (e.g. "Gastro", "Live")

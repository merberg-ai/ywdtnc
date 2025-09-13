monitor_enabled = False

def toggle_monitor(state):
    global monitor_enabled
    if state.lower() == 'on':
        monitor_enabled = True
        print("[MONITOR] Packet monitor enabled.")
    elif state.lower() == 'off':
        monitor_enabled = False
        print("[MONITOR] Packet monitor disabled.")
    else:
        print("[MONITOR] Unknown state. Use 'on' or 'off'.")

def simulate_monitor_output():
    if monitor_enabled:
        print("[AX.25] W6XYZ>APRS: Hello from the packet network")

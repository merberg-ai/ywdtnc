import urwid
import asyncio
import threading
import queue
import time

# External integration points
external_command_handler = None
log_queue = queue.Queue()

# UI State
current_callsign = "N0CALL"
monitor_enabled = False
logged_in_user = "anonymous"

def set_ui_state(callsign, monitor, user):
    global current_callsign, monitor_enabled, logged_in_user
    current_callsign = callsign
    monitor_enabled = monitor
    logged_in_user = user

# === Widgets ===

log_lines = urwid.SimpleListWalker([])
log_box = urwid.ListBox(log_lines)
input_edit = urwid.Edit("> ")
footer = urwid.Text("")

frame = urwid.Frame(
    header=urwid.Text("=== ywdtnc TNC-2 Interface ===", align='center'),
    body=log_box,
    footer=urwid.Pile([
        urwid.AttrMap(input_edit, 'input'),
        urwid.AttrMap(footer, 'footer')
    ])
)

# === Functions ===

def log(message):
    timestamp = time.strftime("%H:%M:%S")
    log_lines.append(urwid.Text(f"[{timestamp}] {message}"))
    log_box.set_focus(len(log_lines) - 1)

def handle_input(key):
    if key in ('ctrl c', 'ctrl d', 'q', 'Q'):
        raise urwid.ExitMainLoop()

def on_enter_input(edit, text):
    command = text.strip()
    if command:
        log(f"> {command}")
        input_edit.edit_text = ""
        if external_command_handler:
            external_command_handler(command)

def update_footer():
    footer_text = f"User: {logged_in_user} | Monitor: {'ON' if monitor_enabled else 'OFF'} | Callsign: {current_callsign}"
    footer.set_text(footer_text)

def periodic_footer(loop, user_data=None):
    update_footer()
    loop.set_alarm_in(1, periodic_footer)

def background_log_printer(loop, user_data=None):
    try:
        while True:
            msg = log_queue.get_nowait()
            log(msg)
    except queue.Empty:
        pass
    loop.set_alarm_in(0.5, background_log_printer)

def launch_ui(command_handler, initial_callsign="N0CALL"):
    global external_command_handler, current_callsign
    external_command_handler = command_handler
    current_callsign = initial_callsign
    update_footer()

    loop = urwid.MainLoop(
        frame,
        palette=[
            ('input', 'light gray', 'dark blue'),
            ('footer', 'black', 'light gray'),
        ],
        unhandled_input=handle_input
    )

    urwid.connect_signal(input_edit, 'change', lambda edit, text: None)
    urwid.connect_signal(input_edit, 'postchange', on_enter_input)

    loop.set_alarm_in(1, periodic_footer)
    loop.set_alarm_in(0.5, background_log_printer)
    loop.run()

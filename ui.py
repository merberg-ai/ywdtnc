import urwid
import queue
import threading

log_queue = queue.Queue()
_ui_state = {
    "callsign": "N0CALL",
    "monitor": False,
    "user": "anonymous"
}

def set_ui_state(callsign, monitor, user):
    _ui_state["callsign"] = callsign
    _ui_state["monitor"] = monitor
    _ui_state["user"] = user

def launch_ui(command_handler, callsign):
    def update_status():
        return f"Callsign: {_ui_state['callsign']} | Monitor: {'ON' if _ui_state['monitor'] else 'OFF'} | User: {_ui_state['user']}"

    def on_input(key):
        if key == "enter":
            command = edit.edit_text.strip()
            if command:
                command_handler(command)
                edit.set_edit_text("")
                edit.set_edit_pos(0)

    def handle_logs():
        while True:
            try:
                msg = log_queue.get(timeout=0.1)
                text.set_text(text.text + "\n" + msg)
                loop.draw_screen()
            except queue.Empty:
                continue

    text = urwid.Text("Welcome to ywdtnc!", align='left')
    edit = urwid.Edit("> ")
    footer = urwid.Text(update_status())

    pile = urwid.Pile([
        text,
        urwid.Divider(),
        edit,
        urwid.Divider(),
        footer
    ])

    loop = urwid.MainLoop(
        urwid.Filler(pile, valign='top'),
        unhandled_input=on_input
    )

    # Background log updater
    threading.Thread(target=handle_logs, daemon=True).start()
    loop.run()

import urwid

status_line = urwid.Text("")
input_edit = urwid.Edit("> ")
output_box = urwid.Text("Welcome to ywdtnc\n")
loop = None
command_queue = None

def set_ui_state(callsign, monitor_enabled, user):
    status_line.set_text(f"{callsign} | MONITOR: {'ON' if monitor_enabled else 'OFF'} | USER: {user}")

def on_input(key):
    if key == "enter":
        command = input_edit.edit_text.strip()
        if command:
            output_box.set_text(output_box.text + f"\n> {command}")
            loop.draw_screen()
            input_edit.set_edit_text("")
            command_queue.put_nowait(command)

def launch_ui(cmd_queue, callsign):
    global loop, command_queue
    command_queue = cmd_queue
    set_ui_state(callsign, False, "anonymous")
    pile = urwid.Pile([
        urwid.LineBox(output_box),
        urwid.Divider(),
        urwid.LineBox(input_edit),
        urwid.Divider(),
        urwid.LineBox(status_line)
    ])
    fill = urwid.Filler(pile, valign="top")
    loop = urwid.MainLoop(fill, unhandled_input=on_input)
    loop.run()

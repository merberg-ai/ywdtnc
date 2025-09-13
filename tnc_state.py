    # ----------------- RX/Monitor -----------------
    async def rx_loop(self):
        if not self.kiss:
            return
        async for port_id, payload in self.kiss.recv_frames():
            parsed = parse_ax25(payload)
            if not parsed:
                continue

            ctl = parsed["ctl"]
            path = f" VIA {','.join(parsed['path'])}" if parsed["path"] else ""

            # --- Monitor output ---
            if self.monitor_on:
                label = None
                seq_info = ""
                if ctl == CTL_UI:
                    label = "UI"
                elif ctl == CTL_SABM:
                    label = "SABM"
                elif ctl == CTL_UA:
                    label = "UA"
                elif ctl == CTL_DISC:
                    label = "DISC"
                elif ctl == CTL_DM:
                    label = "DM"
                else:
                    # Interpret I and S frames
                    if ctl & 0x01 == 0:
                        # I frame: low bit 0, N(S) bits 7–1, N(R) bits 7–1
                        ns = (ctl >> 1) & 0x07
                        nr = (parsed["info"][0] >> 1) & 0x07 if parsed["info"] else 0
                        label = "I"
                        seq_info = f" N(S)={ns} N(R)={nr}"
                    elif ctl & 0x03 == 0x01:
                        # S frame
                        s_type = (ctl >> 2) & 0x03
                        nr = (ctl >> 5) & 0x07
                        if s_type == 0:
                            label = "RR"
                        elif s_type == 1:
                            label = "RNR"
                        elif s_type == 2:
                            label = "REJ"
                        else:
                            label = "S?"
                        seq_info = f" N(R)={nr}"
                    else:
                        label = f"CTL=0x{ctl:02X}"

                header = f"\nM: {parsed['src']} > {parsed['dest']}{path} {label}{seq_info}"

                if parsed["pid"] is not None and ctl == CTL_UI:
                    header += f" PID=0x{parsed['pid']:02X}"

                print(header)

                # Try decoding info field if present
                if parsed["info"]:
                    try:
                        text = parsed["info"].decode("utf-8")
                        if all(32 <= ord(ch) < 127 or ch in "\r\n\t" for ch in text):
                            print("   " + text.replace("\r", "\\r").replace("\n", "\\n"))
                        else:
                            raise UnicodeDecodeError("utf-8", b"", 0, 1, "non-printable")
                    except Exception:
                        print("   [data] " + parsed["info"].hex())

                # Restore prompt
                print("cmd: ", end="", flush=True)

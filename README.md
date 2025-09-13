# MFJ-1270 Python Emulator (MVP 0.2)

A Python CLI that emulates the MFJ-1270 TNC-2 family, speaking KISS to Direwolf.

## Features
- Command/Converse modes
- Persistent config (`mfj1270.ini`)
- UI frames (UNPROTO/CONVERSE)
- Beacon
- Basic LAPB handshake (SABM/UA/DISC/DM)
- Commands: MYCALL, UNPROTO, MONITOR, TXDELAY, BEACON, CONNECT, DISCONNECT, CONVERSE, HELP, QUIT

## Quick start
```bash
./run.sh
```

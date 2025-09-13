# ywdtnc

**Version:** 1.0  
**Author:** kj6ywd  
**Description:** A Python-based CLI emulator for TAPR TNC-2 systems that connects to KISS TNCs via TCP (e.g., Direwolf).

## Features

- First-run config wizard (MYCALL, sysop credentials, Direwolf IP/port)
- TAPR TNC-2 style command interface
- KISS TCP client (default: 127.0.0.1:8001)
- CLI interface to view/set config

## Usage

```bash
python app.py
```

Available commands:
- `SHOW`
- `SET <KEY> <VALUE>`
- `SAVE`
- `RESET`
- `HELP`

## Requirements

```bash
pip install -r requirements.txt
```

## Note

This project is under development. AX.25 frame handling coming soon.
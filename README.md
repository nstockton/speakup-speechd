# speakup-speechd

**A modern Python bridge between [Speakup](https://linux-speakup.org/) and [Speech Dispatcher](https://github.com/brailcom/speechd).**

`speakup-speechd` provides a clean, robust interface that connects the Speakup kernel screen reader (via the softsynth device) to Speech Dispatcher. It is a modern replacement for older bridges such as `speechd-up`, with support for UTF-8, SSML handling, and index marks.

## Features

- Automatic preference for UTF-8 (`/dev/softsynthu`) with fallback to legacy Latin-1 (`/dev/softsynth`)
- Full support for the Speakup softsynth protocol (including index marks for cursor tracking)
- SSML output with correct entity escaping
- Support for all common Speakup commands (rate, pitch, volume, punctuation, etc.)
- Relative and absolute parameter adjustments
- Optional INI configuration for default language, output module, and voice
- Efficient I/O using `epoll` and incremental UTF-8 decoding
- Robust logging, error handling, and graceful degradation
- Runs as a lightweight systemd service

## Prerequisites

- Python 3
- `python3-speechd` (or the equivalent package providing the `speechd` Python module)
- Speakup with the `speakup_soft` kernel module loaded
- Speech Dispatcher installed and running

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/nstockton/speakup-speechd.git
   cd speakup-speechd
   ```

2. Run the provided installer script (requires root privileges):
   ```bash
   sudo ./install.sh
   ```

   This script copies the Python program into place and installs the systemd service unit file.

3. Enable and start the service:
   ```bash
   sudo systemctl enable speakup-speechd.service --now
   ```

Once started, the bridge runs in the background and Speakup will automatically use Speech Dispatcher through it.

## Usage

The bridge is primarily intended to run as a systemd service. For manual testing, listing modules/voices, or debugging, you can run it directly from the command line.

### Command Line Arguments

| Option                        | Short form | Description |
|-------------------------------|------------|-----------|
| `--config FILE`               | `-c`       | Path to a configuration INI file |
| `--list-modules`              | `-lm`      | List available Speech Dispatcher output modules and exit |
| `--list-voices [LANGUAGE]`    | `-lv`      | List available synthesis voices (optionally filtered by language) and exit |
| `--debug`                     | `-d`       | Show debug-level messages |
| `--quiet`                     | `-q`       | Show only warnings and errors (default is INFO level) |

**Examples:**

```bash
# List all available output modules
speakup-speechd --list-modules

# List English voices only
speakup-speechd --list-voices en

# Run with debug logging
speakup-speechd --debug
```

## Configuration (Optional)

The installer script typically places a sample configuration file (exact path depends on `install.sh`). You can set default Speech Dispatcher settings in the configuration file under the `[speech-dispatcher]` section:

```ini
[speech-dispatcher]
language = en
module = espeak-ng
voice=English (America)+Benjamin
```

## License

This program is free software; you can redistribute it and/or modify it under the terms of the **GNU General Public License** as published by the Free Software Foundation; version 2 of the License (GPL-2.0-only).

The full license text is available in the [LICENSE](LICENSE) file in the root of this repository.

## Authors

Copyright (C) 2026 [Nick Stockton](https://github.com/nstockton)

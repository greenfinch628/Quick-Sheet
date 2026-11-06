#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then
    exec env -u WAYLAND_DISPLAY .venv/bin/python main.py
fi
exec env -u WAYLAND_DISPLAY /usr/bin/python3 main.py

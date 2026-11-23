"""Application metadata and per-user recovery storage."""
import os
from pathlib import Path
import shutil
import sys

APP_NAME = 'Quick-Sheet'
WINDOW_CLASS = 'Quicksheet'
APP_ID = 'com.greenfinch628.QuickSheet'
VERSION = (Path(__file__).resolve().parent / 'VERSION').read_text(encoding='utf-8').strip()


def default_state_path():
    legacy = Path(__file__).resolve().parent / '.mini-session.json'
    if sys.platform == 'win32':
        target = Path(os.environ.get('APPDATA') or Path.home() / 'AppData/Roaming') / APP_NAME / 'session.json'
        candidates = [legacy]
    elif sys.platform == 'linux':
        target = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'quick-sheet/session.json'
        candidates = [legacy, Path.home() / 'Applications/quick-sheet/.mini-session.json']
    else:
        return legacy
    # Keep the original recovery file and any existing per-user session.
    if not target.exists():
        for source in candidates:
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with target.open('xb') as out, source.open('rb') as inp:
                        shutil.copyfileobj(inp, out)
                except FileExistsError:
                    pass
                break
    return target

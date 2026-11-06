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
    if sys.platform != 'linux':
        return Path(__file__).resolve().parent / '.mini-session.json'
    target = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'quick-sheet/session.json'
    # Copy rather than move: retain the original recovery data and repository.
    if not target.exists():
        candidates = [Path(__file__).resolve().parent / '.mini-session.json',
                      Path.home() / 'Applications/quick-sheet/.mini-session.json']
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

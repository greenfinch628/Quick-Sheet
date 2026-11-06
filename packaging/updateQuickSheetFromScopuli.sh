#!/usr/bin/env bash
# Standalone Fedora installer/updater, safe to copy into ~/bin/Applications-scripts.
set -Eeuo pipefail
exec /usr/bin/python3 - "$@" <<'PY'
import ast
import hashlib
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import rpm


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def output(*args):
    return run(*args, capture_output=True, text=True).stdout.strip()


def metadata(path):
    fields = output('rpm', '-qp', '--qf', '%{NAME}\n%{EPOCHNUM}\n%{VERSION}\n%{RELEASE}\n%{ARCH}', str(path)).splitlines()
    if len(fields) != 5 or fields[0] != 'quick-sheet' or fields[4] != 'noarch' or not fields[3].endswith('.fc44'):
        raise RuntimeError(f'Unexpected RPM metadata: {path}')
    run('rpm', '-K', str(path))
    return tuple(fields[1:4])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migrate(home):
    source = home / 'Applications/quick-sheet/.mini-session.json'
    target = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share')) / 'quick-sheet/session.json'
    if source.is_file() and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation ensures that existing recovery data is never overwritten.
        with source.open('rb') as inp, target.open('xb') as out:
            shutil.copyfileobj(inp, out)
        if digest(source) != digest(target):
            raise RuntimeError('Recovery data copy failed verification')
        print(f'Preserved session/settings: {target} (original retained)')
    elif source.is_file():
        print(f'Existing session retained: {target}; original also retained: {source}')


def cleanup(home):
    backup = home / '.local/share/quick-sheet/migration-backups' / time.strftime('%Y%m%d-%H%M%S')
    launcher = home / '.local/share/applications/Quick-Sheet.desktop'
    if launcher.is_file():
        text = launcher.read_text()
        entries = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
        expected = str(home / 'Applications/quick-sheet/launch.sh')
        if entries.get('Exec') in (expected, f'"{expected}"'):
            print(f'Obsolete manual launcher: {launcher}\n  Backup: {backup / launcher.name}')
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(launcher, backup / launcher.name)
            launcher.unlink()
        else:
            print(f'Keeping customized launcher for review: {launcher}')
    for name in ('quick-sheet', 'Quick-Sheet'):
        link = home / 'bin' / name
        if link.is_symlink() and link.resolve() == home / 'Applications/quick-sheet/launch.sh':
            backup.mkdir(parents=True, exist_ok=True)
            (backup / f'{name}.symlink.txt').write_text(os.readlink(link))
            print(f'Removing obsolete manual command link: {link} (target retained)')
            link.unlink()
    if os.environ.get('DBUS_SESSION_BUS_ADDRESS') and shutil.which('gsettings'):
        favorites = ast.literal_eval(output('gsettings', 'get', 'org.gnome.shell', 'favorite-apps'))
        if 'Quick-Sheet.desktop' in favorites:
            updated = list(dict.fromkeys('com.greenfinch628.QuickSheet.desktop' if x == 'Quick-Sheet.desktop' else x for x in favorites))
            backup.mkdir(parents=True, exist_ok=True)
            (backup / 'favorite-apps.txt').write_text(repr(favorites))
            run('gsettings', 'set', 'org.gnome.shell', 'favorite-apps', repr(updated))
            print('Updated pinned GNOME launcher identity.')
    if shutil.which('update-desktop-database'):
        run('update-desktop-database', str(home / '.local/share/applications'))
    print('Source repository, original session, icons, spreadsheets, and user files retained.')


def main():
    if os.geteuid() == 0:
        raise RuntimeError('Run as your normal user; sudo is used only for RPM installation.')
    if 'ID=fedora' not in Path('/etc/os-release').read_text():
        raise RuntimeError('This updater supports Fedora only.')
    home = Path.home()
    local = socket.gethostname().split('.')[0].lower() == 'scopuli'
    host = os.environ.get('QUICK_SHEET_SOURCE_HOST', 'scopuli')
    remote_dir = 'Applications/quick-sheet/packages/fedora-44'
    installed_result = subprocess.run(['rpm', '-q', '--qf', '%{EPOCHNUM}\n%{VERSION}\n%{RELEASE}', 'quick-sheet'], capture_output=True, text=True)
    installed = tuple(installed_result.stdout.splitlines()) if installed_result.returncode == 0 else None
    manual = (home / 'Applications/quick-sheet/launch.sh').exists() or (home / '.local/share/applications/Quick-Sheet.desktop').exists()
    print('Installation: ' + ('RPM ' + '-'.join(installed) if installed else 'manual' if manual else 'not installed'), flush=True)
    with tempfile.TemporaryDirectory(prefix='quick-sheet-update-') as folder:
        cache = Path(folder)
        if local:
            candidates = list((home / remote_dir).glob('quick-sheet-*.noarch.rpm'))
        else:
            names = output('ssh', host, f"find ~/{remote_dir} -maxdepth 1 -type f -name 'quick-sheet-*.noarch.rpm' -printf '%f\\n'").splitlines()
            candidates = []
            for name in names:
                if not re.fullmatch(r'quick-sheet-[0-9][0-9A-Za-z.+~_-]*\.noarch\.rpm', name):
                    raise RuntimeError(f'Unexpected remote filename: {name!r}')
                run('scp', f'{host}:{remote_dir}/{name}', str(cache / name))
                candidates.append(cache / name)
        if not candidates:
            raise RuntimeError('No available Quick-Sheet Fedora RPMs found on Scopuli.')
        best, available = None, None
        for candidate in candidates:
            evr = metadata(candidate)
            if available is None or rpm.labelCompare(evr, available) > 0:
                best, available = candidate, evr
        print(f'Available: {best.name}', flush=True)
        # Do not snapshot a session while an old process can still change it.
        processes = subprocess.run(['pgrep', '-u', str(os.getuid()), '-af', r'python[^ ]* .*main\.py'], capture_output=True, text=True)
        for line in processes.stdout.splitlines():
            pid = line.split()[0]
            try:
                cwd = Path(f'/proc/{pid}/cwd').resolve()
                cmd = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode()
            except (FileNotFoundError, PermissionError):
                continue
            if cwd == home / 'Applications/quick-sheet' or '/usr/share/quick-sheet/main.py' in cmd or str(home / 'Applications/quick-sheet/main.py') in cmd:
                raise RuntimeError('Close Quick-Sheet normally, then rerun this updater so its latest session is preserved.')
        migrate(home)
        if installed and rpm.labelCompare(installed, available) >= 0:
            print('Installed version is current or newer; no reinstall needed.')
        else:
            run('sudo', 'dnf', 'install', '-y', str(best))
            verified = tuple(output('rpm', '-q', '--qf', '%{EPOCHNUM}\n%{VERSION}\n%{RELEASE}', 'quick-sheet').splitlines())
            if verified != available:
                raise RuntimeError('Installed version does not match the selected RPM.')
        cleanup(home)
        print(output('rpm', '-q', 'quick-sheet'))
        print('Quick-Sheet is ready in Show Apps.')


try:
    main()
except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as error:
    print(f'ERROR: {error}', file=sys.stderr)
    if isinstance(error, subprocess.CalledProcessError) and error.stderr:
        print(error.stderr.strip(), file=sys.stderr)
    sys.exit(1)
PY

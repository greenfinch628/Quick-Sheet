#!/usr/bin/env python3
"""Build distribution-native packages; retain and validate existing releases."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'VERSION').read_text().strip()
if not re.fullmatch(r'\d+\.\d+\.\d+', VERSION):
    raise SystemExit('VERSION must contain a numeric major.minor.patch version')
PACKAGE_REVISION = 2
RPM_RELEASE = f'{PACKAGE_REVISION}.fc44'
DEB_RELEASE = f'{PACKAGE_REVISION}ubuntu26.04.1'
ID = 'com.greenfinch628.QuickSheet'
SOURCES = ['main.py', 'app_info.py', 'context_menu.py', 'dialogs.py', 'fileio.py',
           'formulas.py', 'move_refs.py', 'selection_drag.py', 'sheet.py', 'VERSION']


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def package_path(kind):
    return ROOT / 'packages' / ('fedora-44' if kind == 'rpm' else 'ubuntu-26.04') / (
        f'quick-sheet-{VERSION}-{RPM_RELEASE}.noarch.rpm' if kind == 'rpm' else
        f'quick-sheet_{VERSION}-{DEB_RELEASE}_all.deb')


def valid(kind, path):
    if not path.is_file():
        return False
    try:
        if kind == 'rpm':
            info = run('rpm', '-qp', '--qf', '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}', str(path), capture_output=True, text=True).stdout
            run('rpm', '-K', str(path), capture_output=True)
            return info == f'quick-sheet {VERSION}-{RPM_RELEASE} noarch'
        info = run('dpkg-deb', '-f', str(path), 'Package', 'Version', 'Architecture', capture_output=True, text=True).stdout
        run('dpkg-deb', '--contents', str(path), capture_output=True)
        return info.splitlines() == ['Package: quick-sheet', f'Version: {VERSION}-{DEB_RELEASE}', 'Architecture: all']
    except subprocess.CalledProcessError:
        return False


def build(kind):
    dest = package_path(kind)
    if valid(kind, dest):
        print(f'Valid package already exists: {dest}')
        return
    if dest.exists():
        raise SystemExit(f'Refusing to overwrite invalid existing package: {dest}; inspect it first')
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='quick-sheet-build-') as folder:
        work = Path(folder)
        stage = work / 'stage'
        app = stage / 'usr/share/quick-sheet'
        app.mkdir(parents=True)
        for name in SOURCES:
            shutil.copy2(ROOT / name, app / name)
        shutil.copytree(ROOT / 'assets', app / 'assets')
        for source, target in [
            ('packaging/quick-sheet', 'usr/bin/quick-sheet'),
            ('Quick-Sheet.desktop', f'usr/share/applications/{ID}.desktop'),
            ('assets/Quick-Sheet.svg', f'usr/share/icons/hicolor/scalable/apps/{ID}.svg'),
            ('assets/Quick-Sheet.png', f'usr/share/icons/hicolor/512x512/apps/{ID}.png')]:
            target = stage / target
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, target)
        os.chmod(stage / 'usr/bin/quick-sheet', 0o755)
        if kind == 'deb':
            (stage / 'DEBIAN').mkdir()
            (stage / 'DEBIAN/control').write_text(f'''Package: quick-sheet
Version: {VERSION}-{DEB_RELEASE}
Architecture: all
Maintainer: Bob Czys <greenfinch628@users.noreply.github.com>
Depends: python3, python3-tk, python3-openpyxl (>= 3.1.5)
Section: editors
Priority: optional
Description: Quick single-sheet spreadsheet
 Spreadsheet with formulas, formatting, session recovery, and Excel import/export.
''')
            built = work / dest.name
            run('dpkg-deb', '--root-owner-group', '-Zzstd', '--build', str(stage), str(built))
        else:
            spec = work / 'quick-sheet.spec'
            spec.write_text(f'''%global debug_package %{{nil}}
Name: quick-sheet
Version: {VERSION}
Release: {RPM_RELEASE}
Summary: Quick single-sheet spreadsheet
License: LicenseRef-No-License
URL: https://github.com/greenfinch628/Quick-Sheet
BuildArch: noarch
Requires: python3, python3-tkinter, python3-openpyxl >= 3.1.5
%description
Spreadsheet with formulas, formatting, session recovery, and Excel import/export.
The source repository has no declared distribution license.
%prep
%build
%install
mkdir -p %{{buildroot}}
cp -a {stage}/. %{{buildroot}}/
%files
/usr/bin/quick-sheet
/usr/share/quick-sheet
/usr/share/applications/{ID}.desktop
/usr/share/icons/hicolor/scalable/apps/{ID}.svg
/usr/share/icons/hicolor/512x512/apps/{ID}.png
''')
            run('rpmbuild', '-bb', '--define', f'_topdir {work}/rpmbuild', str(spec))
            built = next((work / 'rpmbuild/RPMS').rglob('*.rpm'))
        if not valid(kind, built):
            raise SystemExit(f'Built package failed validation: {built}')
        # Never replace a package from an earlier build, including a concurrent one.
        with dest.open('xb') as out, built.open('rb') as inp:
            shutil.copyfileobj(inp, out)
    print(f'Created {dest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('format', choices=['rpm', 'deb'])
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        raise SystemExit(0 if valid(args.format, package_path(args.format)) else 1)
    build(args.format)

"""Focused identity, About, packaging, and non-destructive session migration checks."""
import importlib.util
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
import app_info
import test_app


class ReleaseUITests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown

    def test_identity_and_about_from_help_menu(self):
        app = self.app
        self.assertEqual(app.winfo_class(), 'Quicksheet')
        labels = [app.menubar.entrycget(i, 'label') for i in range(app.menubar.index('end') + 1) if app.menubar.type(i) == 'cascade']
        self.assertEqual(labels, ['File', 'Edit', 'Search', 'Format', 'Data', 'Tools', 'Help'])
        menu = app.nametowidget(app.menubar.entrycget(app.menubar.index('end'), 'menu'))
        self.assertEqual(menu.entrycget(0, 'label'), 'About Quick-Sheet')
        menu.invoke(0)
        app.update()
        win = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
        self.assertEqual(win.title(), 'About Quick-Sheet')
        texts = [w.cget('text') for w in win.winfo_children() if 'text' in w.keys()]
        self.assertIn(app_info.APP_NAME, texts)
        self.assertIn(f'Version {app_info.VERSION}', texts)
        win.destroy()


class ReleaseStorageTests(unittest.TestCase):
    def test_legacy_session_copy_preserves_source_and_existing_target(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            source = home / 'Applications/quick-sheet/.mini-session.json'
            source.parent.mkdir(parents=True)
            source.write_text('{"sheet": "preserve me"}')
            with patch('app_info.Path.home', return_value=home), patch.dict(os.environ, {'XDG_DATA_HOME': str(home / 'data')}), patch('app_info.__file__', str(home / 'installed/app_info.py')):
                target = app_info.default_state_path()
                self.assertEqual(target.read_bytes(), source.read_bytes())
                target.write_text('newer settings')
                self.assertEqual(app_info.default_state_path().read_text(), 'newer settings')
                self.assertEqual(source.read_text(), '{"sheet": "preserve me"}')

    def test_packaging_and_app_share_version(self):
        path = Path(__file__).parent / 'packaging/build.py'
        spec = importlib.util.spec_from_file_location('quick_sheet_build', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.VERSION, app_info.VERSION)
        self.assertIn(app_info.VERSION, module.package_path('rpm').name)
        self.assertIn(app_info.VERSION, module.package_path('deb').name)


if __name__ == '__main__':
    unittest.main()

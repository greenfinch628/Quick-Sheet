"""Exercise the standalone updater's migration logic without touching the real home."""
import ast
import contextlib
import io
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = (Path(__file__).parent / 'packaging/updateQuickSheetFromScopuli.sh').read_text()
        source = script.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        tree = ast.parse(source)
        tree.body = [node for node in tree.body if not isinstance(node, ast.Try)]
        # rpm is only required by the install path, not these file migration checks.
        with patch.dict('sys.modules', {'rpm': types.ModuleType('rpm')}):
            cls.module = types.ModuleType('updater')
            exec(compile(tree, '<updater>', 'exec'), cls.module.__dict__)

    def test_migration_copies_settings_and_never_replaces_existing(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            home = Path(folder)
            source = home / 'Applications/quick-sheet/.mini-session.json'
            source.parent.mkdir(parents=True)
            source.write_text('unsaved spreadsheet, fonts, recent files')
            self.module.migrate(home)
            target = home / '.local/share/quick-sheet/session.json'
            self.assertEqual(source.read_bytes(), target.read_bytes())
            target.write_text('newer session')
            self.module.migrate(home)
            self.assertEqual(target.read_text(), 'newer session')
            self.assertTrue(source.exists())

    def test_cleanup_only_recognized_launcher_and_symlink_with_backup(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), patch.object(self.module.shutil, 'which', return_value=None), contextlib.redirect_stdout(io.StringIO()):
            home = Path(folder)
            repo = home / 'Applications/quick-sheet'
            repo.mkdir(parents=True)
            (repo / 'launch.sh').write_text('source remains')
            user_file = repo / 'my-spreadsheet.mini'
            user_file.write_text('my data')
            launcher = home / '.local/share/applications/Quick-Sheet.desktop'
            launcher.parent.mkdir(parents=True)
            launcher.write_text(f'[Desktop Entry]\nExec={repo}/launch.sh\n')
            (home / 'bin').mkdir()
            link = home / 'bin/quick-sheet'
            link.symlink_to(repo / 'launch.sh')
            self.module.cleanup(home)
            self.assertFalse(launcher.exists())
            self.assertFalse(link.is_symlink())
            self.assertTrue(list(home.glob('.local/share/quick-sheet/migration-backups/*/Quick-Sheet.desktop')))
            self.assertEqual(user_file.read_text(), 'my data')
            self.assertTrue((repo / 'launch.sh').exists())
            launcher.write_text('[Desktop Entry]\nExec=custom-command\n')
            self.module.cleanup(home)
            self.assertTrue(launcher.exists())


if __name__ == '__main__':
    unittest.main()

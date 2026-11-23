"""Preference persistence and precision regression checks (Tk display required)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from main import App
from fileio import read_sheet, write_sheet, read_workbook, write_workbook


class DecimalPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name)/'session.json'
        self.app = App(state_path=self.state)
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.temp.cleanup()

    def restart(self):
        self.app.destroy()
        self.app = App(state_path=self.state)
        self.app.update()

    def test_defaults_live_changes_precision_and_restart(self):
        a = self.app
        self.assertEqual(a.default_decimal_places, 2)
        for r, (raw, expected) in enumerate([('12','12.00'),('12.3','12.30'),('12.345','12.35'),('0','0.00'),('-7.456','-7.46')]):
            a.sheet.set(r, 0, raw)
            self.assertEqual(a.sheet.display(r, 0), expected)
        a.sheet.set(0, 1, '=A3*1000')
        before = json.dumps(a.sheet.dump(), sort_keys=True)
        for precision, expected in [(0,'12'), (3,'12.345'), (2,'12.35'), (10,'12.3450000000')]:
            a.set_default_decimal_places(precision)
            self.assertEqual(a.sheet.display(2, 0), expected)
            self.assertEqual(a.sheet.value(0, 1), 12345)
            self.assertEqual(json.dumps(a.sheet.dump(), sort_keys=True), before)
        self.restart()
        self.assertEqual(self.app.default_decimal_places, 10)
        self.assertEqual(self.app.sheet.raw(2, 0), '12.345')
        self.app.new()
        self.assertEqual(self.app.default_decimal_places, 10)

    def test_validation_and_missing_preferences(self):
        self.app.persist_session()
        original = json.loads(self.state.read_text())
        for invalid in [None, -1, 11, True, '3', 3.5, {}, []]:
            data = dict(original, default_decimal_places=invalid)
            self.state.write_text(json.dumps(data))
            self.restart()
            self.assertEqual(self.app.default_decimal_places, 2)
        original.pop('default_decimal_places')
        self.state.write_text(json.dumps(original))
        self.restart()
        self.assertEqual(self.app.default_decimal_places, 2)
        for invalid in [-1, 11, True, '3', 3.5]:
            with self.assertRaises(ValueError): self.app.set_default_decimal_places(invalid)

    def test_explicit_formats_sheets_undo_and_file_roundtrips(self):
        a = self.app
        a.sheet.set(0, 0, '1.23456789')
        a.sheet.styles['A1'] = {'decimals':4}
        a.sheet.set(0, 1, '0012')
        a.sheet.styles['B1'] = {'format':'Text'}
        a.sheet.set(0, 2, '2026-11-23')
        a.sheet.styles['C1'] = {'format':'Date'}
        original = a.workbook_data()
        a.add_worksheet()
        a.sheet.set(0, 0, '7.12345678')
        a.set_default_decimal_places(3)
        a.select_worksheet(0)
        self.assertEqual(a.sheet.display(0, 0), '1.2346')
        self.assertEqual(a.sheet.display(0, 1), '0012')
        self.assertEqual(a.sheet.display(0, 2), '2026-11-23')
        path = Path(self.temp.name)/'book.qsheet'
        write_workbook(original, path)
        a.load_workbook(read_workbook(path))
        self.assertEqual(a.workbook_data(), original)
        self.assertEqual(a.default_decimal_places, 3)
        a.sheet.set(1, 0, '9.87654321')
        a.checkpoint()
        a.sheet.set(1, 0, '4.1')
        a.undo()
        self.assertEqual(a.sheet.display(1, 0), '9.877')
        a.redo()
        self.assertEqual(a.sheet.display(1, 0), '4.100')
        for ext in ['.mini', '.xlsx', '.csv', '.tsv']:
            path = Path(self.temp.name)/('sheet'+ext)
            write_sheet(a.sheet, path)
            restored = read_sheet(path)
            if ext in ('.mini', '.xlsx'):
                self.assertEqual(restored.value(0, 0), 1.23456789)
            else:
                self.assertEqual(restored.raw(0, 0), '1.2346')
        a.add_worksheet()
        a.sheet.set(0, 0, '8.7654')
        self.assertEqual(a.sheet.display(0, 0), '8.765')

    def test_preferences_dialog(self):
        a = self.app
        a.preferences()
        win = next(w for w in a.winfo_children() if w.winfo_class() == 'Toplevel')
        control = next(w for w in win.winfo_children() if w.winfo_class() == 'TSpinbox')
        button = next(w for w in win.winfo_children() if w.winfo_class() == 'TButton')
        control.delete(0, 'end'); control.insert(0, '11')
        with patch.object(a.dialogs, 'showerror') as error:
            button.invoke()
            error.assert_called_once()
        self.assertEqual(a.default_decimal_places, 2)
        control.delete(0, 'end'); control.insert(0, '3')
        button.invoke()
        self.assertEqual(a.default_decimal_places, 3)

    def test_excel_zero_precision_and_corrupted_session(self):
        import openpyxl
        path = Path(self.temp.name)/'explicit.xlsx'
        workbook = openpyxl.Workbook()
        workbook.active['A1'] = 12.345
        workbook.active['A1'].number_format = '0'
        workbook.save(path)
        workbook.close()
        sheet = read_sheet(path)
        sheet.default_decimal_places = 3
        self.assertEqual(sheet.display(0, 0), '12')
        self.assertEqual(sheet.value(0, 0), 12.345)
        self.state.write_text('{broken json')
        self.app.destroy()
        with patch('main.Dialogs.showerror', create=True) as error:
            self.app = App(state_path=self.state)
            self.app.update()
            self.assertEqual(self.app.default_decimal_places, 2)
            error.assert_called_once()

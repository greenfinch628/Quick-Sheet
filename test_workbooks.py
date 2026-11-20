import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from main import App
from sheet import Sheet
from fileio import read_workbook, write_workbook, validate_workbook


class WorkbookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.state=Path(self.temp.name)/'session.json'
        self.app=App(state_path=self.state)
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.temp.cleanup()

    def test_isolation_history_duplicate_and_delete(self):
        a=self.app
        a.checkpoint(); a.sheet.set(0,0,'first'); a.changed()
        a.select(5,3)
        a.add_worksheet()
        a.update()
        self.assertEqual(len(a.worksheets),2)
        self.assertEqual(a.sheet.raw(0,0),'')
        a.checkpoint(); a.sheet.set(0,0,'second')
        a.select_worksheet(0)
        self.assertEqual(a.active,(5,3))
        self.assertEqual(a.sheet.raw(0,0),'first')
        a.undo()
        self.assertEqual(a.sheet.raw(0,0),'')
        a.redo()
        a.add_worksheet(True)
        self.assertEqual(a.sheet.raw(0,0),'first')
        a.sheet.set(0,0,'copy')
        a.select_worksheet(0)
        self.assertEqual(a.sheet.raw(0,0),'first')
        with patch.object(a.dialogs,'askyesno',return_value=True): a.delete_worksheet()
        self.assertEqual(a.sheet.raw(0,0),'copy')
        self.assertEqual(len(a.worksheets),2)

    def test_native_and_session_roundtrip(self):
        a=self.app
        a.sheet.set(0,0,'=1+2')
        a.sheet.styles['A1']={'bold':True}
        a.add_worksheet()
        a.sheet.set(0,0,'two')
        a.select(7,2)
        path=Path(self.temp.name)/'book.qsheet'
        write_workbook(a.workbook_data(),path)
        data=read_workbook(path)
        a.load_workbook(data,str(path))
        self.assertEqual(a.sheet.raw(0,0),'two')
        a.select_worksheet(0)
        self.assertEqual(a.sheet.raw(0,0),'=1+2')
        self.assertTrue(a.sheet.styles['A1']['bold'])
        a.select(9,4)
        a.add_worksheet()
        a.sheet.set(0,0,'three')
        a.persist_session()
        a.destroy()
        self.app=App(state_path=self.state)
        self.app.update()
        self.assertEqual(len(self.app.worksheets),3)
        self.assertEqual(self.app.sheet.raw(0,0),'three')
        self.app.select_worksheet(0)
        self.assertEqual(tuple(self.app.active),(9,4))

    def test_export_preserves_workbook_dirty_and_path(self):
        a=self.app
        a.add_worksheet()
        path=Path(self.temp.name)/'out.csv'
        with patch.object(a.dialogs,'asksaveasfilename',return_value=str(path)), patch.object(a.dialogs,'askyesno',return_value=True):
            self.assertFalse(a.save(True))
        self.assertTrue(path.exists())
        self.assertTrue(a.dirty)
        self.assertIsNone(a.path)

    def test_rename_and_reorder(self):
        a=self.app
        a.add_worksheet()
        with patch('main.simpledialog.askstring',return_value='Budget'):
            a.rename_worksheet()
        a.update()
        a._tab_drag=1
        with patch.object(a.tabs,'index',return_value=0):
            a.tab_release(SimpleNamespace(x=1,y=1))
        a.update()
        self.assertEqual(a.worksheets[0]['name'],'Budget')
        self.assertEqual(a.sheet_index,0)

    def test_invalid_envelopes(self):
        a=self.app
        data=a.workbook_data()
        for key,value in [('version',2),('active',100),('worksheets',[])]:
            with self.assertRaises(ValueError): validate_workbook(dict(data,**{key:value}))
        data['worksheets']*=2
        with self.assertRaises(ValueError): validate_workbook(data)

if __name__=='__main__': unittest.main()

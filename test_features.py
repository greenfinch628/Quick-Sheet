import unittest
from datetime import date
from formulas import translate
from sheet import Sheet

class FormulaTests(unittest.TestCase):
    def test_functions_and_lazy_if(self):
        s=Sheet()
        for r,v in enumerate(['2','4','text','']): s.set(r,0,v)
        cases={'SUM(A1:A4,3)':9,'AVERAGE(A1:A4)':3,'MIN(A1:A4)':2,'MAX(A1:A4)':4,'COUNT(A1:A4)':2,'COUNTA(A1:A4)':3,'IF(A1=2,"Mixed Case",1/0)':'Mixed Case','ROUND(-2.5,0)':-3,'ABS(-7)':7,'2^3':8,'$A$1+A$2+$A1':8}
        for expr,expected in cases.items():
            with self.subTest(expr=expr):
                s.set(0,1,'='+expr)
                self.assertEqual(s.value(0,1),expected)
        s.set(0,1,'=TODAY()')
        self.assertEqual(s.value(0,1),(date.today()-date(1899,12,30)).days)
        s.set(0,1,'=NOW()')
        self.assertGreaterEqual(s.value(0,1),(date.today()-date(1899,12,30)).days)
    def test_translation_preserves_literals_and_absolute_axes(self):
        self.assertEqual(translate('=A1+$B$2+C$3+$D4+IF(A1=1,"A1",0)',2,3),'=D3+$B$2+F$3+$D6+IF(D3=1,"A1",0)')
        self.assertEqual(translate('=A1',-1,0),'=#REF!')
    def test_security_and_errors(self):
        s=Sheet()
        for expr in ['=__import__("os")','=A1','=AVERAGE(C1:C2)','=2^1000000','=SUM.__class__']:
            s.set(0,0,expr)
            self.assertEqual(s.display(0,0),'#ERROR')

class StructureTests(unittest.TestCase):
    def test_insert_delete_and_absolute_references(self):
        s=Sheet(); s.set(0,0,'5'); s.set(1,1,'=$A$1+A1'); s.styles['A1']={'bold':True}
        s.structural_edit(0,0)
        self.assertEqual(s.raw(2,1),'=$A$2+A2')
        self.assertEqual(s.value(2,1),10)
        self.assertTrue(s.styles['A2']['bold'])
        s.structural_edit(0,1,delete=True)
        self.assertEqual(s.display(1,1),'#ERROR')
    def test_column_dimensions_and_filters_move(self):
        s=Sheet(); s.filters={'1':'x'}; s.col_widths={'1':180}
        s.structural_edit(1,0)
        self.assertEqual(s.filters,{'2':'x'})
        self.assertEqual(s.col_widths,{'2':180})

import test_app
class EditingFormattingTests(unittest.TestCase):
    setUp=test_app.AppTests.setUp
    tearDown=test_app.AppTests.tearDown
    def test_fill_copy_structure_style_and_sizing(self):
        a=self.app
        a.sheet.set(0,0,'2'); a.sheet.set(0,1,'=A1+$A$1')
        a.select(0,1); a.select(2,1,True); a.fill()
        self.assertEqual(a.sheet.raw(2,1),'=A3+$A$1')
        a.undo(); self.assertEqual(a.sheet.raw(2,1),'')
        a.select(0,1); a.copy(); a.select(0,2); a.paste()
        self.assertEqual(a.sheet.raw(0,2),'=B1+$A$1')
        a.apply_style(bold=True,italic=True,alignment='right',foreground='#123456')
        a.fmt.set('Percentage'); a.format_cells()
        self.assertTrue(a.sheet.styles['C1']['bold'])
        a.sheet.col_widths={'0':200}; a.sheet.row_heights={'0':50}; a.draw()
        from types import SimpleNamespace
        self.assertEqual(a.hit(SimpleNamespace(x=a.GUTTER+201,y=a.H+51)),(1,1))
        a.select(0,0); a.structure(0)
        self.assertEqual(a.sheet.raw(1,2),'=B2+$A$2')
    def test_percentage_dates_and_style_roundtrip(self):
        s=Sheet(); s.set(0,0,'0.125'); s.styles['A1']={'format':'Percentage','decimals':1}
        self.assertEqual(s.display(0,0),'12.5%')
        s.set(0,1,'2026-10-23'); s.styles['B1']={'format':'Date'}
        self.assertEqual(s.display(0,1),'2026-10-23')
        s.col_widths={'0':200}; s.row_heights={'0':50}
        restored=Sheet.from_data(s.dump())
        self.assertEqual(restored.col_widths,{'0':200})

class FileTests(unittest.TestCase):
    def test_delimited_and_xlsx_roundtrip(self):
        import tempfile
        from pathlib import Path
        from fileio import write_sheet,read_sheet
        with tempfile.TemporaryDirectory() as folder:
            s=Sheet(); s.set(0,0,'00123'); s.styles['A1']={'format':'Text','bold':True,'background':'#abcdef'}
            s.set(0,1,'3'); s.set(1,1,'=SUM(B1,2)'); s.styles['B1']={'format':'Currency','decimals':2}
            s.set(2,0,'two\tfields\nand lines'); s.col_widths={'0':200}; s.row_heights={'0':50}; s.table=True
            for ext in ('.mini','.xlsx'):
                target=Path(folder)/('data'+ext); write_sheet(s,target); restored=read_sheet(target)
                self.assertEqual(restored.raw(0,0),'00123'); self.assertEqual(restored.value(1,1),5)
                self.assertTrue(restored.styles['A1']['bold']); self.assertEqual(restored.styles['A1']['background'],'#abcdef')
                self.assertEqual(restored.col_widths['0'],200); self.assertEqual(restored.row_heights['0'],50)
            for ext in ('.csv','.tsv'):
                target=Path(folder)/('data'+ext); write_sheet(s,target); restored=read_sheet(target)
                self.assertEqual(restored.raw(2,0),'two\tfields\nand lines')
                self.assertEqual(restored.raw(0,1),'$3.00'); self.assertEqual(restored.raw(1,1),'5')
    def test_failed_save_preserves_original(self):
        import tempfile
        from pathlib import Path
        from fileio import write_sheet
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'old.mini'; path.write_text('original')
            with patch('fileio.json.dumps',side_effect=ValueError('failure')):
                with self.assertRaises(ValueError): write_sheet(Sheet(),path)
            self.assertEqual(path.read_text(),'original')

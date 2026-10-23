"""Custom Auto Sum: running total in B1/B2 while entering column A."""
import json
import tempfile
import unittest
from pathlib import Path
import test_app
from fileio import read_sheet,write_sheet
from sheet import Sheet


class AutoSumModelTests(unittest.TestCase):
    def test_running_range_edits_blanks_text_and_tail_deletion(self):
        s=Sheet(); self.assertEqual(s.start_autosum(),0)
        self.assertEqual(s.raw(0,1),'=AUTOSUM(A1:A1)'); self.assertEqual(s.value(0,1),0)
        s.set(0,0,'10'); s.set(1,0,'-2.5'); s.set(4,0,'3')
        self.assertEqual(s.raw(0,1),'=AUTOSUM(A1:A5)'); self.assertEqual(s.value(0,1),10.5)
        s.set(0,0,'20'); self.assertEqual(s.value(0,1),20.5)
        s.set(4,0,''); self.assertEqual(s.raw(0,1),'=AUTOSUM(A1:A2)')
        s.set(3,0,'note'); self.assertEqual(s.value(0,1),17.5)
        s.set(3,0,''); s.set(1,0,''); s.set(0,0,'')
        self.assertEqual(s.raw(0,1),'=AUTOSUM(A1:A1)'); self.assertEqual(s.value(0,1),0)

    def test_frozen_anchor_existing_data_and_reactivation(self):
        s=Sheet(); s.set(0,0,'100'); s.set(1,0,'5'); s.set(2,0,'6'); s.set(0,1,'Header')
        s.table=True; self.assertEqual(s.start_autosum(),1)
        self.assertEqual(s.raw(1,1),'=AUTOSUM(A2:A3)'); self.assertEqual(s.value(1,1),11)
        self.assertEqual(s.raw(0,1),'Header')
        s.set(0,0,'200'); self.assertEqual(s.value(1,1),11)
        s.table=False; s.start_autosum()
        self.assertEqual(s.raw(1,1),''); self.assertEqual(s.value(0,1),211)
        self.assertEqual(s.raw(0,0),'200')

    def test_manual_overwrite_stops_tracking_and_other_columns_do_not_extend(self):
        s=Sheet(); s.start_autosum(); s.set(0,0,'7'); s.set(30,2,'99')
        self.assertEqual(s.raw(0,1),'=AUTOSUM(A1:A1)'); self.assertEqual(s.value(0,1),7)
        s.set(0,1,'manual'); s.set(1,0,'8')
        self.assertEqual(s.raw(0,1),'manual')

    def test_custom_function_only_uses_designated_a_b_anchors(self):
        for row,col,formula in [(0,2,'=AUTOSUM(A1:A2)'),(2,1,'=AUTOSUM(A1:A2)'),(0,1,'=AUTOSUM(C1:C2)'),(0,1,'=AUTOSUM(A1:B2)'),(1,1,'=AUTOSUM(A1:A2)')]:
            with self.subTest(formula=formula,row=row,col=col):
                s=Sheet(); s.set(row,col,formula)
                self.assertEqual(s.display(row,col),'#ERROR')

    def test_empty_arguments_normalize_to_a_range(self):
        for row in (0,1):
            s=Sheet(); s.set(row,1,'=AUTOSUM()')
            self.assertEqual(s.raw(row,1),f'=AUTOSUM(A{row+1}:A{row+1})')
            self.assertEqual(s.value(row,1),0)

    def test_native_roundtrip_keeps_live_behavior_excel_exports_standard_sum(self):
        s=Sheet(); s.table=True; s.start_autosum(); s.set(1,0,'2'); s.set(2,0,'3')
        with tempfile.TemporaryDirectory() as folder:
            native=Path(folder)/'total.mini'; write_sheet(s,native); restored=read_sheet(native)
            restored.set(3,0,'4')
            self.assertEqual(restored.raw(1,1),'=AUTOSUM(A2:A4)'); self.assertEqual(restored.value(1,1),9)
            clone=Sheet.from_data(json.loads(json.dumps(restored.dump())))
            clone.set(4,0,'1'); self.assertEqual(clone.value(1,1),10)
            excel=Path(folder)/'total.xlsx'; write_sheet(clone,excel); imported=read_sheet(excel)
            self.assertEqual(imported.raw(1,1),'=SUM(A2:A5)'); self.assertEqual(imported.value(1,1),10)


class AutoSumAppTests(unittest.TestCase):
    setUp=test_app.AppTests.setUp
    tearDown=test_app.AppTests.tearDown

    def test_menu_starts_entry_in_a_and_follows_enter_paste_undo_redo(self):
        a=self.app; a.select(30,3); a.top=20; a.left=2
        a.sheet.filters={'0':'hidden'}; a.sheet.styles['B1']={'format':'Text'}
        self.assertEqual(a.function_menu.entrycget(0,'label'),'Auto Sum')
        a.function_menu.invoke(0)
        self.assertEqual(a.active,(0,0)); self.assertEqual((a.top,a.left),(0,0))
        self.assertFalse(a.sheet.filters); self.assertEqual(a.sheet.value(0,1),0)
        for row,number,total in [(0,'10',10),(1,'20',30)]:
            a.edit(number); a.finish_edit(move=True)
            self.assertEqual(a.active,(row+1,0))
            self.assertEqual(a.sheet.raw(0,1),f'=AUTOSUM(A1:A{row+1})')
            self.assertEqual(a.sheet.value(0,1),total)
        a.undo(); self.assertEqual(a.sheet.raw(1,0),''); self.assertEqual(a.sheet.value(0,1),10)
        a.redo(); self.assertEqual(a.sheet.value(0,1),30)
        a.clipboard_clear(); a.clipboard_append('3\n4'); a.paste()
        self.assertEqual(a.sheet.raw(0,1),'=AUTOSUM(A1:A4)'); self.assertEqual(a.sheet.value(0,1),37)
        a.select(3,0); a.cut()
        self.assertEqual(a.sheet.raw(0,1),'=AUTOSUM(A1:A3)'); self.assertEqual(a.sheet.value(0,1),33)

    def test_frozen_start_session_restore_and_formula_bar_entry(self):
        a=self.app; a.sheet.table=True; a.table_var.set(True)
        a.sheet.set(0,0,'100'); a.sheet.set(0,1,'Total')
        a.function_menu.invoke(0)
        self.assertEqual(a.active,(1,0)); self.assertEqual(a.sheet.raw(1,1),'=AUTOSUM(A2:A2)')
        for number in ('5','6'): a.edit(number); a.finish_edit(move=True)
        self.assertEqual(a.sheet.value(1,1),11); self.assertEqual(a.sheet.raw(0,1),'Total')
        a.close(); self.app=test_app.App(state_path=self.state); self.app.update(); a=self.app
        a.select(3,0); a.formula.insert(0,'7'); a.formula_commit()
        self.assertEqual(a.sheet.raw(1,1),'=AUTOSUM(A2:A4)'); self.assertEqual(a.sheet.value(1,1),18)

    def test_activation_is_undoable_and_clear_sheet_removes_mode(self):
        a=self.app; a.sheet.set(0,1,'previous')
        a.function_menu.invoke(0); a.undo()
        self.assertEqual(a.sheet.raw(0,1),'previous')
        a.redo(); self.assertEqual(a.sheet.raw(0,1),'=AUTOSUM(A1:A1)')
        a.clear_sheet(); a.sheet.set(0,0,'5')
        self.assertEqual(a.sheet.raw(0,1),'')

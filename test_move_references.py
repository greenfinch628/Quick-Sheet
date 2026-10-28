"""Only formulas dragged with their source cells update their references."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sheet import Sheet
from fileio import read_sheet, write_sheet
import test_drag_moves


class MoveReferenceTests(unittest.TestCase):
    def numbers(self):
        s=Sheet()
        s.cells={'A1':'2','A2':'3','A3':'5','A4':'=SUM(A1:A3)','Z1':'=SUM(A1:A3)'}
        return s

    def test_total_alone_keeps_range_and_does_not_add_numbers_above_destination(self):
        for frozen in (False,True):
            with self.subTest(frozen=frozen):
                s=self.numbers(); s.table=frozen; s.set(6,2,'1000')
                s.move_block((3,0,3,0),(8,2))
                self.assertEqual(s.raw(8,2),'=SUM(A1:A3)')
                self.assertEqual(s.value(8,2),10)
                self.assertEqual(s.raw(0,25),'=SUM(A1:A3)')

    def test_block_with_data_and_total_updates_only_dragged_formula(self):
        s=self.numbers(); s.set(4,2,'1000')
        s.move_block((0,0,3,0),(5,2))
        self.assertEqual(s.raw(8,2),'=SUM(C6:C8)')
        self.assertEqual(s.value(8,2),10)
        self.assertEqual(s.raw(0,25),'=SUM(A1:A3)')
        self.assertEqual(s.value(0,25),0)
        s.set(6,2,'7')
        self.assertEqual(s.value(8,2),14)

    def test_data_alone_leaves_stationary_totals_and_ranges_unchanged(self):
        s=self.numbers()
        s.move_block((0,0,2,0),(6,3))
        self.assertEqual(s.raw(3,0),'=SUM(A1:A3)')
        self.assertEqual(s.raw(0,25),'=SUM(A1:A3)')
        self.assertEqual(s.value(3,0),0)
        s.set(0,0,'99')
        self.assertEqual(s.value(3,0),99)

    def test_row_and_column_reorders_leave_formulas_outside_source_unchanged(self):
        s=Sheet()
        for row in range(7): s.set(row,0,str(row+1))
        s.set(0,1,'=SUM(A2:A4)')
        s.move_axis(0,2,1,6)
        self.assertEqual(s.raw(0,1),'=SUM(A2:A4)')
        self.assertEqual(s.value(0,1),11)
        s=Sheet()
        for col in range(7): s.set(1,col,str(col+1))
        s.set(0,0,'=SUM(B2:D2)')
        s.move_axis(1,2,1,6)
        self.assertEqual(s.raw(0,0),'=SUM(B2:D2)')
        self.assertEqual(s.value(0,0),11)

    def test_formula_shifted_by_row_insertion_but_not_dragged_keeps_range(self):
        s=self.numbers()
        s.move_axis(0,0,1,7)
        self.assertEqual(s.raw(2,0),'=SUM(A1:A3)')
        self.assertEqual(s.raw(6,0),'2')

    def test_whole_rows_with_total_follow_up_and_down_moves(self):
        for before in (0,9):
            with self.subTest(before=before):
                s=Sheet()
                s.cells={'A2':'2','A3':'3','A4':'=SUM(A2:A3)','Z20':'=SUM(A2:A3)'}
                first=s.move_axis(0,1,3,before)
                self.assertEqual(s.raw(first+2,0),f'=SUM(A{first+1}:A{first+2})')
                self.assertEqual(s.value(first+2,0),5)
                self.assertEqual(s.raw(19,25),'=SUM(A2:A3)')

    def test_whole_columns_with_total_update_only_dragged_formula(self):
        s=Sheet(); s.cells={'B2':'2','B3':'3','B4':'=SUM(B2:B3)','Z1':'=SUM(B2:B3)'}
        s.move_axis(1,1,1,5)
        self.assertEqual(s.raw(3,4),'=SUM(E2:E3)')
        self.assertEqual(s.value(3,4),5)
        self.assertEqual(s.raw(0,25),'=SUM(B2:B3)')

    def test_total_row_alone_keeps_original_range(self):
        s=self.numbers()
        s.move_axis(0,3,1,9)
        self.assertEqual(s.raw(8,0),'=SUM(A1:A3)')
        self.assertEqual(s.value(8,0),10)

    def test_partial_range_in_dragged_formula_excludes_intervening_numbers(self):
        s=self.numbers()
        s.move_block((1,0,3,0),(8,3))
        self.assertEqual(s.raw(10,3),'=SUM((A1:A1,D9:D10))')
        self.assertEqual(s.value(10,3),10)
        s.set(6,3,'1000'); s.set(1,0,'9999')
        self.assertEqual(s.value(10,3),10)
        self.assertEqual(s.raw(0,25),'=SUM(A1:A3)')

    def test_two_dimensional_partial_range_in_dragged_formula_keeps_exact_cells(self):
        s=Sheet()
        for row in range(3):
            for col in range(4): s.set(row,col,str(row*4+col+1))
        s.set(3,1,'=SUM(A1:D3)')
        s.set(5,4,'1000')
        s.move_block((1,1,3,2),(6,5))
        self.assertEqual(s.value(8,5),78)
        s.set(1,1,'9999'); s.set(2,2,'9999')
        self.assertEqual(s.value(8,5),78)
        s.set(7,6,'20')
        self.assertEqual(s.value(8,5),87)

    def test_moved_absolute_reversed_ranges_quoted_and_text_cells(self):
        s=self.numbers()
        s.set(3,1,'=IF($A1=2,SUM($A$3:$A$1),"A1:A3")')
        s.set(4,1,'=A$1+$A$2+$A3')
        s.set(4,0,'=SUM(A1:A3)'); s.styles['A5']={'format':'Text'}
        s.move_block((0,0,4,1),(5,3))
        self.assertEqual(s.raw(8,4),'=IF($D6=2,SUM($D$8:$D$6),"A1:A3")')
        self.assertEqual(s.raw(9,4),'=D$6+$D$7+$D8')
        self.assertEqual(s.value(8,4),10)
        self.assertEqual(s.value(9,4),10)
        self.assertEqual(s.raw(9,3),'=SUM(A1:A3)')
        self.assertEqual(s.value(9,3),'=SUM(A1:A3)')

    def test_split_range_inside_if_preserves_argument_boundaries(self):
        s=self.numbers()
        s.set(3,0,'=SUM(IF(TRUE,A1:A3,A1:A3),2)')
        s.move_block((1,0,3,0),(9,3))
        self.assertEqual(s.value(11,3),12)

    def test_split_ranges_survive_second_move_and_file_roundtrips(self):
        s=self.numbers()
        s.move_block((1,0,3,0),(9,3))
        self.assertEqual(s.value(11,3),10)
        s.move_block((9,3,11,3),(12,4))
        self.assertEqual(s.value(14,4),10)
        self.assertIn('E13:E14',s.raw(14,4))
        with tempfile.TemporaryDirectory() as folder:
            for suffix in ('.mini','.xlsx'):
                with self.subTest(suffix=suffix):
                    path=Path(folder)/('moved'+suffix)
                    write_sheet(s,path)
                    restored=read_sheet(path)
                    self.assertEqual(restored.raw(14,4),s.raw(14,4))
                    self.assertEqual(restored.value(14,4),10)


class MoveReferenceIntegrationTests(unittest.TestCase):
    setUp=test_drag_moves.DragMoveTests.setUp
    tearDown=test_drag_moves.DragMoveTests.tearDown
    select_block=test_drag_moves.DragMoveTests.select_block
    point=test_drag_moves.DragMoveTests.point
    mouse=test_drag_moves.DragMoveTests.mouse
    start=test_drag_moves.DragMoveTests.start
    move=test_drag_moves.DragMoveTests.move

    def test_mouse_move_sum_references_and_undo_redo_are_one_transaction(self):
        a=self.app
        a.sheet.cells={'A1':'2','A2':'3','A3':'=SUM(A1:A2)','Z1':'=SUM(A1:A2)'}
        before=copy.deepcopy(a.sheet.dump())
        self.select_block((0,0),(2,0))
        self.start(self.point(0,0)); target=self.point(5,3)
        self.move(target); self.mouse('<ButtonRelease-1>',target)
        self.assertEqual(a.sheet.raw(7,3),'=SUM(D6:D7)')
        self.assertEqual(a.sheet.raw(0,25),'=SUM(A1:A2)')
        self.assertEqual(a.sheet.value(7,3),5)
        self.assertEqual(a.formula.get(),'=SUM(D6:D7)')
        self.assertEqual(len(a.undo_stack),1)
        a.undo(); self.assertEqual(a.sheet.dump(),before)
        a.redo(); self.assertEqual(a.sheet.value(7,3),5)

    def test_dragging_numbers_leaves_total_in_place_with_original_range(self):
        a=self.app
        a.sheet.cells={'A1':'2','A2':'3','A3':'=SUM(A1:A2)'}
        self.select_block((0,0),(1,0))
        self.start(self.point(0,0)); target=self.point(5,3)
        self.move(target); self.mouse('<ButtonRelease-1>',target)
        self.assertEqual(a.sheet.raw(2,0),'=SUM(A1:A2)')
        self.assertEqual(a.sheet.value(2,0),0)
        self.assertEqual(a.sheet.raw(5,3),'2')
        a.undo(); self.assertEqual(a.sheet.value(2,0),5)

    def test_cancelled_overwrite_leaves_formulas_and_ranges_unchanged(self):
        a=self.app
        a.sheet.cells={'A1':'2','A2':'=SUM(A1:A1)','D6':'occupied'}
        before=copy.deepcopy(a.sheet.dump())
        self.select_block((0,0),(1,0))
        self.start(self.point(0,0)); target=self.point(5,3)
        self.move(target)
        with patch.object(a.dialogs,'askyesno',return_value=False):
            self.mouse('<ButtonRelease-1>',target)
        self.assertEqual(a.sheet.dump(),before)
        self.assertEqual(a.undo_stack,[])


if __name__=='__main__': unittest.main()

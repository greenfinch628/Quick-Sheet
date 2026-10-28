"""Sparse move semantics and selection-border mouse workflows."""
import copy
import unittest
from unittest.mock import patch
from sheet import Sheet, address
import test_app


class MoveModelTests(unittest.TestCase):
    def test_overlapping_block_moves_contents_styles_and_blanks(self):
        s=Sheet()
        s.cells={'A1':'one','B1':'=A1','A2':'two','B2':'three','C2':'replace','C3':'replace too','Z99':'keep'}
        s.styles={'A1':{'bold':True},'B2':{'format':'Currency'},'C2':{'italic':True}}
        self.assertTrue(s.block_move_conflicts((0,0,1,1),(1,1)))
        self.assertTrue(s.move_block((0,0,1,1),(1,1)))
        self.assertEqual(s.cells,{'B2':'one','C2':'=B2','B3':'two','C3':'three','Z99':'keep'})
        self.assertEqual(s.styles,{'B2':{'bold':True},'C3':{'format':'Currency'}})
        s.cells={'A1':'one','B1':'two'}; s.styles={}
        self.assertFalse(s.block_move_conflicts((0,0,0,1),(0,1)))
        s.move_block((0,0,0,1),(0,1))
        self.assertEqual(s.cells,{'B1':'one','C1':'two'})

    def test_blank_source_cells_clear_destination_but_preserve_unrelated_data(self):
        s=Sheet(); s.cells={'A1':'one','D4':'erase','E4':'erase','A20':'keep'}
        s.styles={'E4':{'bold':True}}
        s.move_block((0,0,0,1),(3,3))
        self.assertEqual(s.cells,{'D4':'one','A20':'keep'})
        self.assertEqual(s.styles,{})

    def test_rows_reorder_in_both_directions_with_sizes_and_far_columns(self):
        s=Sheet()
        for row in range(6): s.set(row,30,str(row))
        s.row_heights={'1':40,'3':70}; s.styles={'AE2':{'bold':True}}
        self.assertEqual(s.move_axis(0,1,2,5),3)
        self.assertEqual([s.raw(r,30) for r in range(6)],['0','3','4','1','2','5'])
        self.assertEqual(s.row_heights,{'3':40,'1':70})
        self.assertEqual(s.styles,{'AE4':{'bold':True}})
        self.assertEqual(s.move_axis(0,3,2,1),1)
        self.assertEqual([s.raw(r,30) for r in range(6)],[str(r) for r in range(6)])
        self.assertEqual(s.row_heights,{'1':40,'3':70})

    def test_columns_reorder_metadata_filters_and_far_rows(self):
        s=Sheet(); s.table=True
        for col in range(6): s.set(500,col,str(col))
        s.col_widths={'1':200,'4':80}; s.column_decimals={'1':3,'3':2}
        s.filters={'1':'chosen','5':'other'}
        s.styles={'B501':{'bold':True}}
        s.move_axis(1,1,2,5)
        self.assertEqual([s.raw(500,c) for c in range(6)],['0','3','4','1','2','5'])
        self.assertEqual(s.col_widths,{'3':200,'2':80})
        self.assertEqual(s.column_decimals,{'3':3,'1':2})
        self.assertEqual(s.filters,{'3':'chosen','5':'other'})
        self.assertEqual(s.styles,{'D501':{'bold':True}})
        self.assertTrue(s.table)
        s.move_axis(1,3,2,0)
        self.assertEqual([s.raw(500,c) for c in range(6)],['1','2','0','3','4','5'])

    def test_noops_invalid_inputs_and_sparse_move_beyond_extent(self):
        s=Sheet(); s.set(0,0,'value')
        before=copy.deepcopy(s.dump())
        self.assertFalse(s.move_block((0,0,0,0),(0,0)))
        self.assertEqual(s.move_axis(0,0,1,1),0)
        self.assertEqual(s.dump(),before)
        with self.assertRaises(ValueError): s.move_axis(2,0,1,2)
        with self.assertRaises(ValueError): s.move_block((0,0,0,0),(-1,0))
        s.move_axis(0,0,1,1000)
        self.assertEqual(s.cells,{'A1000':'value'})

    def test_moved_formula_retains_references_to_sources_left_in_place(self):
        s=Sheet(); s.cells={'A1':'5','B1':'=$A$1+A1','Z9':'=A1'}
        s.move_axis(1,1,1,4)
        self.assertEqual(s.raw(0,3),'=$A$1+A1')
        self.assertEqual(s.raw(8,25),'=A1')


class DragMoveTests(unittest.TestCase):
    setUp=test_app.AppTests.setUp
    tearDown=test_app.AppTests.tearDown

    def select_block(self, first=(0,0), last=(1,1)):
        a=self.app
        a.select(*first); a.select(*last,extend=True)
        a.canvas.focus_force(); a.update()

    def point(self,row,col,edge='top'):
        x,y,w,h=self.app.cell_rect(row,col)
        return (int(x+20),int(y+1)) if edge=='top' else (int(x+1),int(y+12))

    def mouse(self,sequence,point,**kwargs):
        self.event_time=getattr(self,'event_time',1000)+1000
        self.app.canvas.event_generate(sequence,x=point[0],y=point[1],time=self.event_time,**kwargs)

    def start(self,point):
        self.mouse('<Button-1>',point)
        self.assertIsNotNone(self.app.selection_drag.state)

    def move(self,target):
        self.mouse('<B1-Motion>',target)
        self.assertTrue(self.app.canvas.find_withtag('move_preview'))

    def test_block_preview_move_styles_and_single_undo_redo(self):
        a=self.app
        a.sheet.set(0,0,'a'); a.sheet.set(1,1,'b')
        a.sheet.styles['A1']={'bold':True}
        self.select_block()
        before=copy.deepcopy(a.sheet.dump()); history=len(a.undo_stack)
        self.start(self.point(0,0)); target=self.point(4,3)
        self.move(target)
        self.assertEqual(a.sheet.dump(),before)
        self.mouse('<ButtonRelease-1>',target)
        self.assertEqual(a.sheet.raw(4,3),'a'); self.assertEqual(a.sheet.raw(5,4),'b')
        self.assertEqual(a.sheet.raw(0,0),'')
        self.assertEqual(a.sheet.styles['D5'],{'bold':True})
        self.assertEqual(a.bounds(),(4,3,5,4))
        self.assertEqual(len(a.undo_stack),history+1)
        self.assertIsNone(a.selection_drag.timer)
        self.assertFalse(a.canvas.find_withtag('move_preview'))
        a.undo(); self.assertEqual(a.sheet.dump(),before)
        a.redo(); self.assertEqual(a.sheet.raw(4,3),'a')

    def test_overwrite_refusal_and_confirmation(self):
        a=self.app
        a.sheet.set(0,0,'source'); a.sheet.set(4,3,'destination')
        self.select_block(); before=copy.deepcopy(a.sheet.dump())
        for answer in (False,True):
            self.select_block(); self.start(self.point(0,0)); target=self.point(4,3)
            self.move(target)
            with patch.object(a.dialogs,'askyesno',return_value=answer) as ask:
                self.mouse('<ButtonRelease-1>',target)
            ask.assert_called_once()
            if not answer:
                self.assertEqual(a.sheet.dump(),before)
                self.assertEqual(a.undo_stack,[]); self.assertFalse(a.dirty)
        self.assertEqual(a.sheet.raw(4,3),'source')

    def test_overlap_does_not_prompt_for_its_own_source(self):
        a=self.app; a.sheet.set(0,0,'one'); a.sheet.set(0,1,'two')
        self.select_block((0,0),(0,1)); self.start(self.point(0,0))
        target=self.point(0,1); self.move(target)
        with patch.object(a.dialogs,'askyesno') as ask:
            self.mouse('<ButtonRelease-1>',target)
            ask.assert_not_called()
        self.assertEqual([a.sheet.raw(0,c) for c in range(3)],['','one','two'])

    def test_rows_insert_and_shift_with_full_row_data(self):
        a=self.app
        for row in range(6): a.sheet.set(row,30,str(row))
        a.sheet.row_heights={'1':40}
        a.select_header(0,1,preserve=False); a.select_header(0,2,extend=True)
        a.canvas.focus_force(); a.update()
        self.start(self.point(1,0)); target=self.point(5,0); self.move(target)
        with patch.object(a.dialogs,'askyesno') as ask:
            self.mouse('<ButtonRelease-1>',target); ask.assert_not_called()
        self.assertEqual([a.sheet.raw(r,30) for r in range(6)],['0','3','4','1','2','5'])
        self.assertEqual(a.sheet.row_heights,{'3':40})
        self.assertEqual((a.bounds()[0],a.bounds()[2]),(3,4))
        self.assertEqual(a._header_axis,0)
        a.undo(); self.assertEqual([a.sheet.raw(r,30) for r in range(6)],[str(r) for r in range(6)])

    def test_columns_insert_and_shift_full_columns_and_precision(self):
        a=self.app
        for col in range(6): a.sheet.set(500,col,str(col))
        a.sheet.col_widths={'1':150}; a.sheet.column_decimals={'1':3}
        a.select_header(1,1,preserve=False); a.select_header(1,2,extend=True)
        a.canvas.focus_force(); a.update()
        self.start(self.point(0,1,edge='left')); target=self.point(0,5,edge='left')
        self.move(target); self.mouse('<ButtonRelease-1>',target)
        self.assertEqual([a.sheet.raw(500,c) for c in range(6)],['0','3','4','1','2','5'])
        self.assertEqual(a.sheet.col_widths,{'3':150})
        self.assertEqual(a.sheet.column_decimals,{'3':3})
        self.assertEqual((a.bounds()[1],a.bounds()[3]),(3,4))
        self.assertEqual(a._header_axis,1)

    def test_escape_outside_drop_and_no_motion_leave_history_untouched(self):
        a=self.app; a.sheet.set(0,0,'keep')
        self.select_block(); before=copy.deepcopy(a.sheet.dump())
        a.redo_stack=['preserve']
        self.start(self.point(0,0)); self.move(self.point(4,3))
        a.canvas.event_generate('<Escape>')
        self.assertIsNone(a.selection_drag.state)
        self.assertIsNone(a.selection_drag.timer)
        self.assertEqual(a.sheet.dump(),before)
        self.start(self.point(0,0)); self.move(self.point(4,3))
        self.mouse('<ButtonRelease-1>',(-20,-20))
        self.start(self.point(0,0)); self.mouse('<ButtonRelease-1>',self.point(0,0))
        self.assertEqual(a.sheet.dump(),before)
        self.assertFalse(a.dirty); self.assertEqual(a.undo_stack,[])
        self.assertEqual(a.redo_stack,['preserve'])

    def test_drag_inside_cells_still_selects_and_shift_border_extends(self):
        a=self.app; self.select_block()
        self.mouse('<Button-1>',(a.GUTTER+30,a.H+14))
        self.assertIsNone(a.selection_drag.state)
        self.mouse('<B1-Motion>',(a.GUTTER+2*a.W+30,a.H+3*a.H+14))
        self.assertEqual(a.bounds(),(0,0,3,2))
        self.mouse('<ButtonRelease-1>',(a.GUTTER+2*a.W+30,a.H+3*a.H+14))
        self.mouse('<Button-1>',self.point(0,0),state=1)
        self.assertIsNone(a.selection_drag.state)

    def test_stationary_pointer_edge_scrolls_and_escape_stops_timer(self):
        a=self.app; self.select_block()
        self.start(self.point(0,0))
        target=(a.canvas.winfo_width()-2,a.canvas.winfo_height()-2)
        self.move(target)
        old_target=a.selection_drag.state['target']
        timer=a.selection_drag.timer; a.after_cancel(timer); a.selection_drag.timer=None
        a.selection_drag.scroll()
        self.assertGreater(a.top,0); self.assertGreater(a.left,0)
        self.assertNotEqual(a.selection_drag.state['target'],old_target)
        a.canvas.event_generate('<Escape>')
        self.assertIsNone(a.selection_drag.timer)
        self.assertEqual(a.sheet.cells,{})

    def test_noop_row_and_empty_block_moves_preserve_history(self):
        a=self.app; a.sheet.set(0,0,'keep')
        a.redo_stack=['preserve']
        a.select_header(0,1,preserve=False); a.select_header(0,2,extend=True)
        a.canvas.focus_force(); a.update()
        self.start(self.point(1,0)); target=self.point(2,0)
        self.move(target); self.mouse('<ButtonRelease-1>',target)
        self.select_block((3,3),(4,4))
        self.start(self.point(3,3)); target=self.point(6,5)
        self.move(target); self.mouse('<ButtonRelease-1>',target)
        self.assertEqual(a.sheet.cells,{'A1':'keep'})
        self.assertFalse(a.dirty); self.assertEqual(a.undo_stack,[])
        self.assertEqual(a.redo_stack,['preserve'])

    def test_keyboard_shortcuts_cancel_pending_move_before_changing_data(self):
        a=self.app; a.sheet.set(0,0,'cut me')
        self.select_block(); self.start(self.point(0,0)); self.move(self.point(4,3))
        a.canvas.event_generate('<Control-x>')
        self.assertIsNone(a.selection_drag.state)
        self.assertIsNone(a.selection_drag.timer)
        self.assertEqual(a.sheet.raw(0,0),'')
        self.assertEqual(a.sheet.raw(4,3),'')

    def test_resize_still_takes_priority_and_focus_loss_cancels_move(self):
        a=self.app; self.select_block()
        x=a.GUTTER+a.column_width(0)
        self.mouse('<Button-1>',(x,8))
        self.mouse('<B1-Motion>',(x+40,8)); self.mouse('<ButtonRelease-1>',(x+40,8))
        self.assertEqual(a.column_width(0),a.W+40)
        self.start(self.point(0,0)); self.move(self.point(4,3))
        with patch.object(a,'focus_get',return_value=None):
            a.dismiss_context_if_unfocused()
        self.assertIsNone(a.selection_drag.state)
        self.assertIsNone(a.selection_drag.timer)


if __name__=='__main__': unittest.main()

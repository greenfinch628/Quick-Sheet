"""Shared Windows/Fedora menu workflows."""
import tkinter as tk
import unittest
import test_app


class MenuFeatureTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown

    def cell_menu(self, row, col):
        a = self.app
        x, y, width, height = a.cell_rect(row, col)
        a.canvas.event_generate('<Button-3>', x=int(x+width/2), y=int(y+height/2))
        a.update()
        return a._context_menu

    def invoke(self, menu, label):
        index = next(i for i, entry in enumerate(menu.entries) if entry[0] == label)
        menu.invoke(index)
        self.assertFalse(menu.winfo_ismapped())

    def test_sum_all_above_across_gaps_recalculates_and_supports_undo(self):
        a = self.app
        for row, value in [(0, '10'), (2, '-3'), (3, 'heading'), (5, '2.5')]:
            a.sheet.set(row, 1, value)
        a.sheet.set(0, 0, '1000')
        menu = self.cell_menu(6, 1)
        self.invoke(menu, 'Sum')
        self.assertEqual(a.sheet.raw(6, 1), '=SUM(B1:B6)')
        self.assertEqual(a.sheet.value(6, 1), 9.5)
        self.assertEqual(a.formula.get(), '=SUM(B1:B6)')
        self.assertEqual(a.active, (6, 1))
        self.assertTrue(a.dirty)
        a.undo(); self.assertEqual(a.sheet.raw(6, 1), '')
        a.redo(); self.assertEqual(a.sheet.value(6, 1), 9.5)
        a.sheet.set(1, 1, '4')
        self.assertEqual(a.sheet.value(6, 1), 13.5)

    def test_sum_empty_column_and_first_row_produce_zero_without_cycles(self):
        a = self.app
        self.invoke(self.cell_menu(5, 2), 'Sum')
        self.assertEqual(a.sheet.raw(5, 2), '=SUM(C1:C5)')
        self.assertEqual(a.sheet.value(5, 2), 0)
        self.invoke(self.cell_menu(0, 2), 'Sum')
        self.assertEqual(a.sheet.value(0, 2), 0)
        self.assertEqual(a.sheet.value(5, 2), 0)

    def test_sum_uses_clicked_cell_inside_selection(self):
        a = self.app
        a.sheet.set(0, 0, '5'); a.sheet.set(4, 0, 'old value')
        a.select(0, 0); a.select(6, 1, True)
        menu = self.cell_menu(4, 0)
        self.assertEqual(a.active, (6, 1))
        self.invoke(menu, 'Sum')
        self.assertEqual(a.sheet.raw(4, 0), '=SUM(A1:A4)')
        self.assertEqual(a.sheet.value(4, 0), 5)
        self.assertEqual(a.sheet.raw(6, 1), '')
        a.undo(); self.assertEqual(a.sheet.raw(4, 0), 'old value')

    def test_sum_excludes_frozen_first_row_and_includes_filtered_rows(self):
        a = self.app
        a.sheet.table = True; a.table_var.set(True)
        a.sheet.set(0, 0, '10'); a.sheet.set(1, 0, '4'); a.sheet.set(2, 0, '6')
        menu = self.cell_menu(4, 0)
        a.sheet.filters = {'0': '4'}
        self.invoke(menu, 'Sum')
        self.assertEqual(a.sheet.raw(4, 0), '=SUM(A2:A4)')
        self.assertEqual(a.sheet.value(4, 0), 10)
        self.assertEqual(a.sheet.filters, {'0': '4'})

    def test_toolbar_sum_uses_active_cell_and_totals_across_gaps(self):
        a = self.app
        a.sheet.set(0, 1, '10'); a.sheet.set(2, 1, '4')
        a.sheet.set(5, 1, 'keep below')
        a.select(0, 0); a.select(4, 1, True)
        button = next(w for w in a.fmt.master.winfo_children()
                      if 'text' in w.keys() and w.cget('text') == 'Sum')
        button.invoke()
        self.assertEqual(a.sheet.raw(4, 1), '=SUM(B1:B4)')
        self.assertEqual(a.sheet.value(4, 1), 14)
        self.assertEqual(a.sheet.raw(4, 0), '')
        self.assertEqual(a.sheet.raw(5, 1), 'keep below')
        self.assertEqual(a.active, (4, 1))
        a.undo(); self.assertEqual(a.sheet.raw(4, 1), '')

    def test_sum_boundaries_and_existing_ranges_after_toggle(self):
        a = self.app
        a.sheet.set(0, 0, '100'); a.sheet.set(1, 0, '4'); a.sheet.set(3, 0, '6')
        self.invoke(self.cell_menu(5, 0), 'Sum')
        self.assertEqual(a.sheet.raw(5, 0), '=SUM(A1:A5)')
        self.assertEqual(a.sheet.value(5, 0), 110)
        a.toggle_first_row()
        self.assertEqual(a.sheet.raw(5, 0), '=SUM(A1:A5)')
        a.select(5, 0)
        button = next(w for w in a.fmt.master.winfo_children()
                      if 'text' in w.keys() and w.cget('text') == 'Sum')
        button.invoke()
        self.assertEqual(a.sheet.raw(5, 0), '=SUM(A2:A5)')
        self.assertEqual(a.sheet.value(5, 0), 10)
        a.toggle_first_row()
        self.assertEqual(a.sheet.raw(5, 0), '=SUM(A2:A5)')
        button.invoke()
        self.assertEqual(a.sheet.raw(5, 0), '=SUM(A1:A5)')
        self.assertEqual(a.sheet.value(5, 0), 110)

    def test_sum_at_frozen_boundary_returns_zero_without_header_or_self_reference(self):
        a = self.app
        a.toggle_first_row()
        a.sheet.set(0, 0, '100')
        self.invoke(self.cell_menu(1, 0), 'Sum')
        self.assertEqual(a.sheet.value(1, 0), 0)
        self.invoke(self.cell_menu(0, 1), 'Sum')
        self.assertEqual(a.sheet.value(0, 1), 0)

    def first_row_menu(self, body=False):
        a = self.app
        a.canvas.event_generate('<Button-1>', x=10, y=int(a.H+a.row_height(0)/2))
        if body:
            return self.cell_menu(0, 1)
        a.canvas.event_generate('<Button-3>', x=10, y=int(a.H+a.row_height(0)/2))
        a.update()
        return a._context_menu

    def test_first_row_header_freeze_and_undo_redo(self):
        a = self.app
        self.invoke(self.first_row_menu(), 'Freeze First Row')
        self.assertTrue(a.sheet.table)
        self.assertTrue(a.table_var.get())
        a.scroll_y('scroll', 3, 'units')
        self.assertEqual(a.visible_rows[0], 0)
        a.undo(); self.assertFalse(a.sheet.table); self.assertFalse(a.table_var.get())
        a.redo(); self.assertTrue(a.sheet.table); self.assertTrue(a.table_var.get())

    def test_selected_first_row_body_menu_toggles_freeze_and_undoes(self):
        a = self.app
        self.invoke(self.first_row_menu(body=True), 'Freeze First Row')
        self.assertTrue(a.sheet.table)
        history = len(a.undo_stack)
        self.invoke(self.first_row_menu(body=True), 'Unfreeze First Row')
        self.assertFalse(a.sheet.table)
        self.assertFalse(a.table_var.get())
        self.assertEqual(len(a.undo_stack), history+1)
        a.undo(); self.assertTrue(a.sheet.table); self.assertTrue(a.table_var.get())
        a.redo(); self.assertFalse(a.sheet.table); self.assertFalse(a.table_var.get())
        a.canvas.event_generate('<Button-3>', x=10, y=int(a.H+a.row_height(0)+a.row_height(1)/2))
        self.assertNotIn('Freeze First Row', [entry[0] for entry in a._context_menu.entries])

    def test_format_menu_order_commands_and_toolbar_removal(self):
        a = self.app
        titles = [a.menubar.entrycget(i, 'label') for i in range(a.menubar.index('end')+1)
                  if a.menubar.type(i) == 'cascade']
        self.assertEqual(titles, ['File', 'Edit', 'Search', 'Format', 'Data', 'Tools'])
        index = next(i for i in range(a.menubar.index('end')+1)
                     if a.menubar.type(i) == 'cascade' and a.menubar.entrycget(i, 'label') == 'Format')
        menu = a.nametowidget(a.menubar.entrycget(index, 'menu'))
        self.assertEqual([menu.entrycget(i, 'label') for i in range(menu.index('end')+1)], ['Style…', 'Size…'])
        toolbar_labels = [w.cget('text') for w in a.fmt.master.winfo_children() if 'text' in w.keys()]
        self.assertNotIn('Style…', toolbar_labels)
        self.assertNotIn('Size…', toolbar_labels)
        self.assertIn('Sum', toolbar_labels)
        menu.invoke(0); a.update()
        dialog = next(w for w in a.winfo_children() if isinstance(w, tk.Toplevel))
        self.assertEqual(dialog.title(), 'Cell style')
        dialog.destroy()
        menu.invoke(1); a.update()
        self.assertTrue(a.size_window.winfo_exists())
        a.size_window.cancel()


if __name__ == '__main__':
    unittest.main()

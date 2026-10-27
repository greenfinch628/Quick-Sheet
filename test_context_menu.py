"""Integration tests for menus that stay inside the application's window."""
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from context_menu import ContextMenu
import test_app


class ContextMenuTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown

    def open_cell(self, row=1, col=1):
        a = self.app
        x, y, width, height = a.cell_rect(row, col)
        a.canvas.event_generate('<Button-3>', x=int(x+width/2), y=int(y+height/2))
        a.update()
        menu = a._context_menu
        self.assertIsInstance(menu, ContextMenu)
        self.assertTrue(menu.winfo_ismapped())
        self.assertIs(menu.master, a)
        self.assertIsNone(a.grab_current())
        return menu

    def test_pointer_position_and_same_click_selects_another_cell(self):
        a = self.app
        menu = self.open_cell()
        x, y, width, height = a.cell_rect(1, 1)
        self.assertEqual(menu.winfo_rootx(), a.canvas.winfo_rootx()+int(x+width/2))
        self.assertEqual(menu.winfo_rooty(), a.canvas.winfo_rooty()+int(y+height/2))
        x, y, width, height = a.cell_rect(5, 5)
        a.canvas.event_generate('<Button-1>', x=int(x+width/2), y=int(y+height/2))
        a.update()
        self.assertFalse(menu.winfo_ismapped())
        self.assertEqual(a.active, (5, 5))

    def test_right_click_replaces_menu_and_selects_new_cell(self):
        first = self.open_cell()
        position = first.winfo_x(), first.winfo_y()
        second = self.open_cell(4, 4)
        self.assertFalse(first.winfo_exists())
        self.assertNotEqual(position, (second.winfo_x(), second.winfo_y()))
        self.assertEqual(self.app.active, (4, 4))

    def test_escape_then_keyboard_selection_and_editing(self):
        a = self.app
        menu = self.open_cell()
        a.canvas.focus_force(); a.update()
        a.canvas.event_generate('<Escape>'); a.update()
        self.assertFalse(menu.winfo_ismapped())
        a.canvas.event_generate('<Right>')
        self.assertEqual(a.active, (1, 2))
        a.canvas.event_generate('<KeyPress>', keysym='q')
        self.assertEqual(a.editor.get(), 'q')
        a.update()
        a.editor.event_generate('<KP_Enter>')
        self.assertEqual(a.sheet.raw(1, 2), 'q')

    def test_command_hides_before_action_and_runs_once(self):
        a = self.app
        menu = self.open_cell()
        calls = []
        menu.entries[0] = ('Cut', lambda: calls.append(menu.winfo_ismapped()))
        label = menu.rows[0].winfo_children()[0]
        label.event_generate('<ButtonPress-1>')
        label.event_generate('<ButtonRelease-1>')
        self.assertEqual(calls, [0])

    def test_keyboard_menu_navigation_does_not_move_cell(self):
        a = self.app
        a.sheet.set(1, 1, 'copy me')
        menu = self.open_cell()
        a.canvas.focus_force(); a.update()
        a.canvas.event_generate('<Down>'); a.canvas.event_generate('<Down>')
        self.assertEqual(menu.active, 1)
        self.assertEqual(a.active, (1, 1))
        a.canvas.event_generate('<Return>')
        self.assertFalse(menu.winfo_ismapped())
        self.assertEqual(a.clipboard_get(), 'copy me\n')
        self.assertIsNone(a.editor)

    def test_window_unmapping_hides_menu_and_restore_keeps_it_hidden(self):
        a = self.app
        menu = self.open_cell()
        # Child unmaps must not be mistaken for minimizing the main window.
        a.context_unmapped(SimpleNamespace(widget=a.formula))
        self.assertTrue(menu.winfo_ismapped())
        a.withdraw(); a.update()
        self.assertEqual(menu.winfo_manager(), '')
        a.deiconify(); a.update()
        self.assertFalse(menu.winfo_ismapped())

    def test_window_resize_and_sheet_scroll_dismiss_menu(self):
        a = self.app
        menu = self.open_cell()
        a.geometry('950x620'); a.update()
        self.assertFalse(menu.winfo_ismapped())
        menu = self.open_cell()
        top = a.top
        a.canvas.event_generate('<Button-5>'); a.update()
        self.assertGreater(a.top, top)
        self.assertFalse(menu.winfo_ismapped())
        menu = self.open_cell(5, 1)
        a.scroll_x('scroll', 1, 'units')
        self.assertFalse(menu.winfo_ismapped())

    def test_filter_opening_click_survives_and_long_list_is_scrollable(self):
        a = self.app
        a.sheet.table = True
        for row in range(120):
            a.sheet.set(row, 0, 'value %03d' % row)
        a.draw(); a.update()
        arrow = a.canvas.coords(a.canvas.find_withtag('dropdown_0')[0])
        a.canvas.event_generate('<Button-1>', x=int(sum(arrow[::2])/3), y=int(sum(arrow[1::2])/3))
        a.update()
        menu = a._context_menu
        self.assertTrue(menu.winfo_ismapped())
        self.assertTrue(menu.scrollbar.winfo_ismapped())
        a.canvas.focus_force(); a.update()
        a.canvas.event_generate('<End>'); a.update()
        self.assertEqual(menu.active, len(menu.entries)-1)
        self.assertGreater(menu.viewport.yview()[0], 0)
        before = menu.viewport.yview()[0]
        menu.rows[-1].winfo_children()[0].event_generate('<MouseWheel>', delta=120)
        self.assertLess(menu.viewport.yview()[0], before)
        a.canvas.event_generate('<Return>')
        self.assertEqual(a.sheet.filters, {'0': 'value 119'})
        self.assertFalse(menu.winfo_ismapped())

    def test_formula_focus_selection_clipboard_and_keyboard_open(self):
        a = self.app
        a.formula.delete(0, 'end'); a.formula.insert(0, '=ABS(-9)')
        a.formula.selection_range(1, 4)
        a.formula.focus_force(); a.update()
        a.formula.event_generate('<Shift-F10>'); a.update()
        menu = a._context_menu
        self.assertTrue(menu.winfo_ismapped())
        self.assertIs(a.focus_get(), a.formula)
        menu.rows[1].winfo_children()[0].event_generate('<ButtonRelease-1>')
        self.assertEqual(a.clipboard_get(), 'ABS')
        self.assertFalse(menu.winfo_ismapped())

    def test_outside_entry_click_and_shortcut_dismiss_without_consuming_input(self):
        a = self.app
        menu = self.open_cell()
        a.formula.event_generate('<Button-1>', x=8, y=8); a.update()
        self.assertFalse(menu.winfo_ismapped())
        a.sheet.set(1, 1, 'shortcut')
        menu = self.open_cell()
        a.canvas.focus_force(); a.update()
        a.canvas.event_generate('<Control-x>')
        self.assertFalse(menu.winfo_ismapped())
        self.assertEqual(a.sheet.raw(1, 1), '')
        self.assertEqual(a.clipboard_get(), 'shortcut\n')

    def test_focus_leaving_window_dismisses_but_internal_focus_is_safe(self):
        a = self.app
        a.canvas.focus_force(); a.update()
        menu = self.open_cell()
        a.formula.focus_set(); a.update()
        self.assertTrue(menu.winfo_ismapped())
        other = tk.Toplevel(a)
        other.update(); other.focus_force(); a.update()
        self.assertFalse(menu.winfo_ismapped())
        other.destroy()

    def test_edges_long_labels_and_no_native_popups(self):
        a = self.app
        with patch.object(tk.Menu, 'tk_popup', side_effect=AssertionError('native popup')):
            self.open_cell()
            menu = a.new_context_menu()
            menu.add_command('A very long label '*100, lambda: None)
            menu.show(a.winfo_rootx()+a.winfo_width(), a.winfo_rooty()+a.winfo_height())
            a.update()
            self.assertGreaterEqual(menu.winfo_x(), 0)
            self.assertGreaterEqual(menu.winfo_y(), 0)
            self.assertLessEqual(menu.winfo_x()+menu.winfo_width(), a.winfo_width())
            self.assertLessEqual(menu.winfo_y()+menu.winfo_height(), a.winfo_height())


if __name__ == '__main__':
    unittest.main()

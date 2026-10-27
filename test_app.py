"""Desktop integration checks; requires a graphical desktop / Tk display."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from main import App


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.state=Path(self.temp.name)/'session.json'
        self.app=App(state_path=self.state)
        self.app.update()

    def tearDown(self):
        if self.app.winfo_exists(): self.app.destroy()
        self.temp.cleanup()

    def test_clipboard_range_cut_formats_and_undo(self):
        a=self.app
        a.sheet.set(0,0,'1')
        a.sheet.set(1,0,'two\nlines')
        a.sheet.styles['A1']={'format':'Currency','decimals':2}
        a.select(0,0)
        a.select(1,0,True)
        a.cut()
        self.assertEqual(a.sheet.raw(0,0),'')
        a.select(0,2)
        a.paste()
        self.assertEqual(a.sheet.raw(1,2),'two\nlines')
        self.assertEqual(a.sheet.display(0,2),'$1.00')
        a.undo()
        self.assertEqual(a.sheet.raw(0,2),'')
        a.undo()
        self.assertEqual(a.sheet.raw(0,0),'1')

    def test_single_cell_fill_selection_and_external_paste(self):
        a=self.app
        a.sheet.set(0,0,'yes')
        a.copy()
        a.select(0,1)
        a.select(3,1,True)
        a.paste()
        self.assertEqual([a.sheet.raw(r,1) for r in range(4)],['yes']*4)
        a.clipboard_clear()
        a.clipboard_append('a\tb\n3\t4')
        a.select(4,0)
        a.paste()
        self.assertEqual(a.sheet.raw(5,1),'4')

    def test_search_replace_literal_and_wrap(self):
        a=self.app
        a.sheet.set(0,0,'Apple apple')
        a.sheet.set(50,3,'APPLE')
        a.sheet.filters={'0':'hidden'}
        a.search_text='apple'
        self.assertTrue(a.find_next())
        self.assertEqual(a.active,(50,3))
        self.assertFalse(a.sheet.filters)
        self.assertTrue(a.find_next())
        self.assertEqual(a.active,(0,0))
        self.assertEqual(a.replace_matches('apple',r'fruit\1',True),2)
        self.assertEqual(a.sheet.raw(0,0),r'fruit\1 fruit\1')
        a.undo()
        self.assertEqual(a.sheet.raw(0,0),'Apple apple')

    def test_close_restores_unsaved_editor_and_view_without_prompt(self):
        a=self.app
        a.sheet.set(0,0,'Header')
        a.sheet.set(1,0,'27')
        a.sheet.table=True
        a.sheet.filters={'0':'27'}
        a.sheet.cell_size=14
        a.select(1,0)
        a.edit('28')
        a.left=2
        with patch('main.messagebox.askyesnocancel',side_effect=AssertionError('No close prompt')):
            a.close()
        self.app=App(state_path=self.state)
        self.app.update()
        b=self.app
        self.assertEqual(b.sheet.raw(1,0),'28')
        self.assertEqual(b.sheet.filters,{'0':'27'})
        self.assertEqual(b.sheet.cell_size,14)
        self.assertEqual(b.active,(1,0))
        self.assertEqual(b.left,2)
        self.assertTrue(b.dirty)
        self.assertTrue(b.undo_stack)

    def test_csv_comma_import_and_menu_structure(self):
        a=self.app
        path=Path(self.temp.name)/'data.csv'
        path.write_text('Name,Value\n"A, B",12\nsemi;colon,3\n',encoding='utf-8')
        with patch('main.filedialog.askopenfilename',return_value=str(path)):
            a.import_csv()
        self.assertEqual(a.sheet.raw(1,0),'A, B')
        self.assertEqual(a.sheet.raw(2,0),'semi;colon')
        self.assertEqual(list(csv.reader(io.StringIO(a.sheet.csv_text())))[1],['A, B','12'])
        titles=[a.menubar.entrycget(i,'label') for i in range(a.menubar.index('end')+1) if a.menubar.type(i)=='cascade']
        self.assertEqual(titles,['File','Edit','Search','Format','Data','Tools'])

    def test_shortcuts_context_menu_and_search_dialog(self):
        a=self.app
        a.sheet.set(0,0,'shortcut')
        a.canvas.focus_force()
        a.update()
        a.canvas.event_generate('<Control-x>')
        self.assertEqual(a.sheet.raw(0,0),'')
        a.select(1,0)
        a.canvas.event_generate('<Control-v>')
        self.assertEqual(a.sheet.raw(1,0),'shortcut')
        a.select(0,0)
        a.select(1,0,True)
        with patch('main.ContextMenu.show') as popup:
            a.context_menu(SimpleNamespace(num=3,x=a.GUTTER+10,y=2*a.H+5,x_root=10,y_root=10))
            popup.assert_called_once()
        self.assertEqual(a.bounds(),(0,0,1,0))
        a.search_dialog(True)
        a.update()
        self.assertTrue(a.search_window.winfo_exists())
        a.search_window.destroy()

    def test_fonts_centered_on_moved_app(self):
        a=self.app
        a.geometry('900x600+210+130')
        a.update()
        a.fonts()
        a.update()
        dialog=next(w for w in a.winfo_children() if w.winfo_class()=='Toplevel')
        x=a.winfo_rootx()+(a.winfo_width()-dialog.winfo_width())//2
        y=a.winfo_rooty()+(a.winfo_height()-dialog.winfo_height())//2
        self.assertEqual(dialog.geometry(),f'{dialog.winfo_width()}x{dialog.winfo_height()}+{x}+{y}')

    def test_window_location_restored_after_close(self):
        a=self.app
        a.geometry('900x600+240+160')
        a.update()
        geometry=a.geometry()
        a.close()
        self.app=App(state_path=self.state)
        self.app.update()
        self.assertEqual(self.app.geometry(),geometry)

    def test_frozen_header_arrow_opens_sort_menu(self):
        a=self.app
        a.sheet.table=True
        a.sheet.set(0,0,'A very long heading that must leave room for the arrow')
        a.sheet.set(1,0,'10')
        a.sheet.set(2,0,'2')
        a.draw()
        arrow=a.canvas.find_withtag('dropdown_0')[0]
        coords=a.canvas.coords(arrow)
        x=int(sum(coords[::2])/3)
        y=int(sum(coords[1::2])/3)
        menus=[]
        def capture(menu,*args): menus.append(menu)
        with patch('main.ContextMenu.show',new=capture):
            a.canvas.event_generate('<Button-1>',x=x,y=y)
        self.assertEqual(len(menus),1)
        menu=menus[0]
        self.assertEqual([menu.entrycget(i,'label') for i in range(4)],
                         ['Sort A–Z','Sort Z–A','Sort numbers ascending','Sort numbers descending'])
        menu.invoke(2)
        self.assertEqual(a.sheet.raw(0,0),'A very long heading that must leave room for the arrow')
        self.assertEqual(a.sheet.raw(1,0),'2')
        a.left=3
        a.top=25
        a.draw()
        arrow=a.canvas.find_withtag('dropdown_3')[0]
        coords=a.canvas.coords(arrow)
        with patch.object(a,'filter_menu') as popup:
            a.canvas.event_generate('<Button-1>',x=int(sum(coords[::2])/3),y=int(sum(coords[1::2])/3))
            self.assertEqual(popup.call_args.args[0],3)


if __name__=='__main__': unittest.main()

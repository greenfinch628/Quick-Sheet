"""Regression checks for the uncommitted UI update on Windows and Fedora."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tkinter as tk
import test_app
from sheet import Sheet
from fileio import read_sheet,write_sheet


class UIUpdateTests(unittest.TestCase):
    setUp=test_app.AppTests.setUp
    tearDown=test_app.AppTests.tearDown

    def assert_centered(self,win):
        self.app.update()
        expected_x=self.app.winfo_rootx()+(self.app.winfo_width()-win.winfo_width())//2
        expected_y=self.app.winfo_rooty()+(self.app.winfo_height()-win.winfo_height())//2
        self.assertLessEqual(abs(win.winfo_x()-expected_x),2)
        self.assertLessEqual(abs(win.winfo_y()-expected_y),2)

    def test_function_menu_order_and_nonaggregate_templates(self):
        a=self.app
        names=[a.function_menu.entrycget(i,'label') for i in range(a.function_menu.index('end')+1)]
        self.assertEqual(names,['Auto Sum','Sum','Average','Min','Max','Count','CountA','ABS','Today','Now'])
        for i in range(7,len(names)):
            name=names[i].upper()
            a.function_menu.invoke(i)
            self.assertEqual(a.formula.get(),'='+name+'()')
            self.assertEqual(a.formula.index('insert'),len(name)+2)
            self.assertEqual(a.sheet.raw(*a.active),'')
        a.formula_commit()
        self.assertTrue(a.sheet.raw(*a.active).startswith('=NOW('))

    def test_aggregate_functions_commit_contiguous_range_above_active_cell(self):
        a=self.app
        a.sheet.set(0,0,'100'); a.sheet.set(1,0,'2'); a.sheet.set(2,0,'4')
        a.sheet.table=True; a.select(3,0)
        for i,(name,expected) in enumerate([('SUM',6),('AVERAGE',3),('MIN',2),('MAX',4),('COUNT',2),('COUNTA',2)]):
            a.function_menu.invoke(i+1)
            self.assertEqual(a.sheet.raw(3,0),f'={name}(A2:A3)')
            self.assertEqual(a.sheet.value(3,0),expected)
            self.assertEqual(a.formula.get(),f'={name}(A2:A3)')
        a.undo(); self.assertEqual(a.sheet.raw(3,0),'=COUNT(A2:A3)')
        a.sheet.table=False; a.insert_function('SUM')
        self.assertEqual(a.sheet.raw(3,0),'=SUM(A1:A3)')
        a.sheet.set(1,0,''); a.insert_function('AVERAGE')
        self.assertEqual(a.sheet.raw(3,0),'=AVERAGE(A3:A3)')
        a.sheet.set(1,0,'text')
        a.insert_function('COUNT'); self.assertEqual(a.sheet.value(3,0),2)
        a.insert_function('COUNTA'); self.assertEqual(a.sheet.value(3,0),3)

    def test_empty_automatic_range_keeps_destination_unchanged(self):
        a=self.app; a.sheet.set(2,0,'keep'); a.select(2,0)
        self.assertFalse(a.insert_function('SUM'))
        self.assertEqual(a.sheet.raw(2,0),'keep'); self.assertFalse(a.undo_stack)
        a.sheet.table=True; a.sheet.set(0,0,'Header'); a.select(1,0)
        self.assertFalse(a.insert_function('AVERAGE')); self.assertEqual(a.sheet.raw(1,0),'')
        a.sheet.table=False; a.select(0,0)
        self.assertFalse(a.insert_function('SUM')); self.assertEqual(a.sheet.raw(0,0),'Header')

    def test_formula_bar_context_menu_edits_and_commits_entry(self):
        a=self.app; a.formula.focus_force(); a.update()
        a.formula.insert(0,'=ABS(-3)'); a.formula.selection_range(1,4)
        menus=[]
        def capture(menu,*args): menus.append(menu)
        with patch('main.ContextMenu.show',new=capture):
            a.formula.event_generate('<Button-3>',x=5,y=5)
        self.assertEqual(len(menus),1)
        menu=menus[0]
        self.assertEqual([menu.entrycget(i,'label') for i in range(4)],['Cut','Copy','Paste','Enter'])
        menu.invoke(1); self.assertEqual(a.clipboard_get(),'ABS')
        menu.invoke(0); self.assertEqual(a.formula.get(),'=(-3)')
        a.formula.icursor(1)
        menu.invoke(2); self.assertEqual(a.formula.get(),'=ABS(-3)')
        menu.invoke(3); self.assertEqual(a.sheet.raw(0,0),'=ABS(-3)'); self.assertEqual(a.sheet.value(0,0),3)
        a.undo(); self.assertEqual(a.sheet.raw(0,0),'')

    def test_all_custom_dialogs_and_future_dialog_centering(self):
        a=self.app; a.geometry('1000x650+215+130'); a.update()
        factories=[a.style_dialog,a.search_dialog,lambda:a.search_dialog(True),a.fonts,a.size_dialog,lambda:a.dialogs.window('Future dialog')]
        for factory in factories:
            existing=set(a.winfo_children()); factory(); a.update()
            windows=[w for w in a.winfo_children() if w not in existing and isinstance(w,tk.Toplevel)]
            self.assertEqual(len(windows),1)
            win=windows[0]; self.assert_centered(win)
            self.assertEqual(str(win.transient()),str(a))
            if hasattr(win,'cancel'): win.cancel()
            else: win.destroy()

    def test_common_dialogs_are_owned_by_app(self):
        a=self.app
        with patch('main.messagebox.showinfo',return_value='ok') as show:
            a.dialogs.showinfo('Title','Message'); self.assertIs(show.call_args.kwargs['parent'],a)
        with patch('main.filedialog.askopenfilename',return_value='') as show:
            a.open(); self.assertIs(show.call_args.kwargs['parent'],a)
        with patch('main.colorchooser.askcolor',return_value=(None,None)) as show:
            a.dialogs.askcolor('#ffffff'); self.assertIs(show.call_args.kwargs['parent'],a)

    def test_column_precision_live_entry_new_numbers_and_undo(self):
        a=self.app; s=a.sheet
        s.set(0,0,'12.345'); s.set(500,0,'7.25'); s.set(0,1,'3.14159')
        s.set(1,0,'00123'); s.styles['A2']={'format':'Text'}
        s.set(2,0,'2.5'); s.styles['A3']={'format':'Currency','decimals':1}
        self.assertEqual(a.dec.get(),0); self.assertEqual(s.display(0,0),'12')
        a.decimal_control.delete(0,'end'); a.decimal_control.insert(0,'2')
        a.after(400,a.quit); a.mainloop()
        self.assertEqual(s.display(0,0),'12.35'); self.assertEqual(s.display(500,0),'7.25')
        self.assertEqual(s.display(0,1),'3'); self.assertEqual(s.display(1,0),'00123')
        self.assertEqual(s.display(2,0),'$2.50')
        s.set(700,0,'6.5'); self.assertEqual(s.display(700,0),'6.50')
        self.assertEqual(s.raw(0,0),'12.345')
        a.undo(); self.assertEqual(a.sheet.display(0,0),'12'); self.assertEqual(a.dec.get(),0)
        a.redo(); self.assertEqual(a.sheet.display(0,0),'12.35'); self.assertEqual(a.dec.get(),2)
        a.dec.set(0); a.format_decimals()
        self.assertEqual(a.sheet.display(0,0),'12'); self.assertEqual(a.sheet.display(2,0),'$2')

    def test_precision_entry_follows_original_column_when_selection_changes(self):
        a=self.app; a.sheet.set(0,0,'1.234'); a.sheet.set(0,1,'2.345')
        a.dec.set(3); a.select(0,1)
        self.assertEqual(a.sheet.display(0,0),'1.234'); self.assertEqual(a.sheet.display(0,1),'2')
        self.assertEqual(a.dec.get(),0)

    def test_clear_sheet_resets_all_formatting_and_is_undoable(self):
        a=self.app; a.path='named.mini'
        a.sheet.set(0,0,'data'); a.sheet.styles['A1']={'bold':True,'background':'#abcdef'}
        a.sheet.column_decimals={'0':3}; a.sheet.col_widths={'0':200}; a.sheet.row_heights={'0':50}
        a.sheet.filters={'0':'data'}; a.sheet.table=True; a.sheet.cell_size=20
        before=json.dumps(a.sheet.dump(),sort_keys=True)
        a.clear_sheet()
        self.assertEqual(a.sheet.dump(),Sheet().dump()); self.assertEqual(a.path,'named.mini')
        self.assertTrue(a.dirty); self.assertEqual(a.dec.get(),0)
        a.undo(); self.assertEqual(json.dumps(a.sheet.dump(),sort_keys=True),before)
        a.redo(); self.assertEqual(a.sheet.dump(),Sheet().dump())

    def header_menu(self,x,y):
        menus=[]
        def capture(menu,*args): menus.append(menu)
        with patch('main.ContextMenu.show',new=capture):
            self.app.context_menu(SimpleNamespace(num=3,x=x,y=y,x_root=10,y_root=10))
        self.assertEqual(len(menus),1)
        return menus[0]

    def test_row_and_column_header_insert_both_sides_and_delete(self):
        a=self.app
        for r,value in enumerate(['one','two','three']): a.sheet.set(r,0,value)
        a.sheet.set(0,1,'b'); a.sheet.set(0,2,'c'); a.draw(); a.select(1,0)
        rowmenu=self.header_menu(10,a.H+a.row_height(0)+10)
        self.assertEqual([rowmenu.entrycget(i,'label') for i in range(3)],['Insert rows above','Insert rows below','Delete rows'])
        for index,expected in [(0,['one','','two','three']),(1,['one','two','','three']),(2,['one','three','',''])]:
            rowmenu.invoke(index)
            self.assertEqual([a.sheet.raw(r,0) for r in range(4)],expected)
            a.undo()
        # Switching from a row selection to a column must select only that column.
        colmenu=self.header_menu(a.GUTTER+a.column_width(0)+10,5)
        self.assertEqual(a.bounds()[1::2],(1,1))
        self.assertEqual([colmenu.entrycget(i,'label') for i in range(3)],['Insert columns left','Insert columns right','Delete columns'])
        for index,expected in [(0,['one','','b','c']),(1,['one','b','','c']),(2,['one','c','',''])]:
            colmenu.invoke(index)
            self.assertEqual([a.sheet.raw(0,c) for c in range(4)],expected)
            a.undo()

    def test_drag_sizes_undo_redo_and_no_op_preserves_history(self):
        a=self.app; a.sheet.set(0,0,'keep'); a.canvas.focus_force(); a.update()
        before=len(a.undo_stack)
        x=a.GUTTER+a.column_width(0)
        a.canvas.event_generate('<Button-1>',x=x,y=8)
        a.canvas.event_generate('<B1-Motion>',x=x+55,y=8)
        a.canvas.event_generate('<ButtonRelease-1>',x=x+55,y=8)
        self.assertEqual(a.column_width(0),180); self.assertEqual(len(a.undo_stack),before+1)
        a.undo(); self.assertEqual(a.column_width(0),125)
        redo=list(a.redo_stack)
        a.canvas.event_generate('<Button-1>',x=x,y=8)
        a.canvas.event_generate('<ButtonRelease-1>',x=x,y=8)
        self.assertEqual(a.redo_stack,redo)
        a.redo(); self.assertEqual(a.column_width(0),180)
        y=a.H+a.row_height(0)
        a.canvas.event_generate('<Button-1>',x=10,y=y)
        a.canvas.event_generate('<B1-Motion>',x=10,y=y+25)
        a.canvas.event_generate('<ButtonRelease-1>',x=10,y=y+25)
        self.assertEqual(a.row_height(0),a.H+25)
        a.undo(); self.assertEqual(a.row_height(0),a.H)
        self.assertEqual(a.sheet.raw(0,0),'keep')

    def test_size_dialog_preview_history_cancel_ok_and_global_undo(self):
        a=self.app; a.select(0,0); a.select(1,1,True)
        history=list(a.undo_stack); redo=list(a.redo_stack)
        win=a.size_dialog()
        self.assertEqual([w.cget('text') for w in win.buttons.winfo_children()],['Ok','Apply','Undo','Cancel'])
        for width,height in [(180,40),(220,60)]:
            win.width.set(str(width)); win.height.set(str(height)); self.assertTrue(win.apply())
        self.assertEqual(a.column_width(1),220); self.assertEqual(a.row_height(1),60)
        win.undo_preview(); self.assertEqual(a.column_width(1),180)
        win.undo_preview(); self.assertEqual(a.column_width(1),125)
        win.undo_preview(); self.assertEqual(a.undo_stack,history)
        win.width.set('200'); win.height.set('50'); win.apply(); win.cancel()
        self.assertEqual(a.sheet.col_widths,{}); self.assertEqual(a.sheet.row_heights,{})
        self.assertFalse(a.dirty); self.assertEqual(a.undo_stack,history); self.assertEqual(a.redo_stack,redo)
        win=a.size_dialog(); win.width.set('190'); win.height.set('55'); win.accept()
        self.assertFalse(win.winfo_exists()); self.assertEqual(a.column_width(1),190)
        a.undo(); self.assertEqual(a.column_width(1),125); self.assertEqual(a.row_height(1),a.H)
        a.redo(); self.assertEqual(a.column_width(1),190)

    def test_size_arrows_load_each_row_and_preserve_local_history(self):
        a=self.app
        a.sheet.set(0,1,'first'); a.sheet.set(1,1,'second'); a.sheet.set(2,1,'third')
        a.sheet.col_widths={'1':190}; a.sheet.row_heights={'0':35,'1':45,'2':55}
        a.select(0,1); original=a.sheet.dump(); original=json.dumps(original,sort_keys=True)
        win=a.size_dialog()
        self.assertEqual(win.cell_address.get(),'Cell B1'); self.assertEqual(win.cell_contents.get(),'first')
        self.assertIn('disabled',win.up_button.state())
        win.down_button.invoke()
        self.assertEqual(a.active,(1,1)); self.assertEqual(win.cell_address.get(),'Cell B2')
        self.assertEqual(win.cell_contents.get(),'second'); self.assertEqual(win.height.get(),'45')
        self.assertEqual(win.width.get(),'190'); self.assertFalse(win.history)
        win.height.set('70'); win.down_button.invoke()
        self.assertEqual(a.row_height(1),70); self.assertEqual(a.active,(2,1)); self.assertEqual(win.height.get(),'55')
        win.height.set('80'); win.apply()
        win.undo_preview(); self.assertEqual(a.active,(2,1)); self.assertEqual(win.height.get(),'55')
        win.undo_preview(); self.assertEqual(a.active,(1,1)); self.assertEqual(win.height.get(),'45')
        win.up_button.invoke(); self.assertEqual(a.active,(0,1)); self.assertEqual(win.cell_contents.get(),'first')
        win.down_button.invoke(); win.height.set('75'); win.apply(); win.cancel()
        self.assertEqual(a.active,(0,1)); self.assertEqual(json.dumps(a.sheet.dump(),sort_keys=True),original)
        self.assertFalse(a.undo_stack)

    def test_size_navigation_accepts_changes_on_multiple_rows_as_one_undo(self):
        a=self.app; a.select(0,0)
        win=a.size_dialog(); win.height.set('40'); win.down_button.invoke()
        win.height.set('50'); win.accept()
        self.assertEqual(a.row_height(0),40); self.assertEqual(a.row_height(1),50)
        self.assertEqual(len(a.undo_stack),1)
        a.undo(); self.assertEqual(a.sheet.row_heights,{})
        a.redo(); self.assertEqual(a.row_height(0),40); self.assertEqual(a.row_height(1),50)

    def test_size_invalid_values_keep_dialog_open(self):
        a=self.app; win=a.size_dialog(); win.width.set('invalid')
        with patch('main.messagebox.showerror') as error:
            self.assertFalse(win.apply()); error.assert_called_once()
        self.assertTrue(win.winfo_exists()); self.assertEqual(a.sheet.col_widths,{})
        win.cancel()

    @unittest.skipUnless(sys.platform=='win32','Windows native modal centering')
    def test_native_message_dialog_is_centered(self):
        import os
        import subprocess
        a=self.app; a.geometry('950x600+240+160'); a.update()
        owner=(a.winfo_rootx(),a.winfo_rooty(),a.winfo_width(),a.winfo_height())
        result=Path(self.temp.name)/'dialog.json'
        # Tk's native modal loop can hold the GIL: dismiss from a separate process.
        helper=r"""
import ctypes,json,sys,time
from pathlib import Path
from ctypes import wintypes
u=ctypes.WinDLL('user32')
u.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR];u.FindWindowW.restype=wintypes.HWND
u.IsWindowVisible.argtypes=[wintypes.HWND]
u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
u.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
u.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
u.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
u.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
@callback
def click_ok(hwnd,param):
    text=ctypes.create_unicode_buffer(128);name=ctypes.create_unicode_buffer(64)
    u.GetWindowTextW(hwnd,text,128);u.GetClassNameW(hwnd,name,64)
    if name.value=='Button' and text.value.replace('&','').lower()=='ok': u.PostMessageW(hwnd,0x00f5,0,0)
    return True
u.EnumChildWindows.argtypes=[wintypes.HWND,callback,wintypes.LPARAM]
for _ in range(500):
    hwnd=u.FindWindowW(None,'Quick-Sheet native centering regression')
    pid=wintypes.DWORD()
    if hwnd: u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    if hwnd and pid.value==int(sys.argv[1]) and u.IsWindowVisible(hwnd):
        time.sleep(0.3)
        rect=wintypes.RECT();u.GetWindowRect(hwnd,ctypes.byref(rect))
        Path(sys.argv[2]).write_text(json.dumps([rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top]))
        u.EnumChildWindows(hwnd,click_ok,0)
        break
    time.sleep(0.01)
"""
        worker=subprocess.Popen([getattr(sys,'_base_executable',sys.executable),'-c',helper,str(os.getpid()),str(result)],creationflags=subprocess.CREATE_NO_WINDOW)
        a.dialogs.showinfo('Quick-Sheet native centering regression','This automated check closes itself.')
        worker.wait(timeout=10)
        self.assertTrue(result.exists())
        x,y,w,h=json.loads(result.read_text())
        self.assertLessEqual(abs(x-(owner[0]+(owner[2]-w)//2)),2)
        self.assertLessEqual(abs(y-(owner[1]+(owner[3]-h)//2)),2)

    @unittest.skipUnless(sys.platform=='win32','Windows ICO integration')
    def test_windows_icon_and_process_identity(self):
        import ctypes
        value=ctypes.c_wchar_p()
        result=ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(value))
        self.assertEqual(result,0)
        try: self.assertEqual(value.value,'QuickSheet.Desktop')
        finally: ctypes.windll.ole32.CoTaskMemFree(value)
        user=ctypes.WinDLL('user32')
        user.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint]; user.GetAncestor.restype=ctypes.c_void_p
        user.SendMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]; user.SendMessageW.restype=ctypes.c_ssize_t
        hwnd=user.GetAncestor(self.app.winfo_id(),2)
        # Tk does not return the bitmap filename on Windows; inspect the native icons.
        self.assertTrue(user.SendMessageW(hwnd,0x007f,1,0))
        self.assertTrue(user.SendMessageW(hwnd,0x007f,0,0))


class PrecisionModelTests(unittest.TestCase):
    def test_precision_roundtrip_formats_and_column_structure(self):
        s=Sheet(); s.set(0,0,'1.125'); s.column_decimals={'0':3}; s.styles['A1']={'bold':True}
        s.set(1,0,'=A1*2')
        with tempfile.TemporaryDirectory() as folder:
            for ext in ('.mini','.xlsx'):
                path=Path(folder)/('precision'+ext); write_sheet(s,path); restored=read_sheet(path)
                self.assertEqual(restored.display(0,0),'1.125')
                self.assertEqual(restored.display(1,0),'2.250')
            s.structural_edit(1,0)
            self.assertEqual(s.column_decimals,{'1':3})
            self.assertEqual(s.display(1,1),'2.250')
            s.structural_edit(1,0,delete=True)
            self.assertEqual(s.column_decimals,{'0':3})
            s.structural_edit(1,0,delete=True)
            self.assertEqual(s.column_decimals,{})

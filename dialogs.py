"""Owned, centered dialogs. Use this service for new application dialogs too."""
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
from contextlib import contextmanager


class CenteredWindow(tk.Toplevel):
    def __init__(self, owner, title):
        super().__init__(owner)
        self.withdraw()
        self.owner=owner
        self.title(title)
        self.transient(owner)
        self.preferred_size=None
        self._showing=False
        self.after_idle(self.show)

    def show(self):
        if not self.winfo_exists() or self._showing: return
        self._showing=True
        try:
            self.update_idletasks()
            self.owner.update_idletasks()
            width,height=self.preferred_size or (self.winfo_reqwidth(),self.winfo_reqheight())
            x=self.owner.winfo_rootx()+(self.owner.winfo_width()-width)//2
            y=self.owner.winfo_rooty()+(self.owner.winfo_height()-height)//2
            self.geometry(f'{width}x{height}{x:+d}{y:+d}')
            self.deiconify()
        finally: self._showing=False


class Dialogs:
    """One entry point for custom, file, message, and color dialogs."""
    def __init__(self, owner):
        self.owner=owner
        self._mapped=None
        owner.bind_all('<Map>',self._mapped_native,add='+')

    def window(self,title): return CenteredWindow(self.owner,title)

    def _mapped_native(self,event):
        if self._mapped is None: return
        path=str(event.widget)
        try:
            if self.owner.tk.call('winfo','toplevel',path)!=path or path in self._mapped: return
            self._mapped.add(path)
            self.owner.after_idle(lambda:self._center_native_tk(path))
        except tk.TclError: pass

    def _center_native_tk(self,path):
        try:
            tkapp=self.owner.tk
            width=int(tkapp.call('winfo','reqwidth',path)); height=int(tkapp.call('winfo','reqheight',path))
            x=self.owner.winfo_rootx()+(self.owner.winfo_width()-width)//2
            y=self.owner.winfo_rooty()+(self.owner.winfo_height()-height)//2
            tkapp.call('wm','geometry',path,f'{width}x{height}{x:+d}{y:+d}')
        except tk.TclError: pass

    @contextmanager
    def _windows_centering(self):
        # Native Windows common dialogs do not produce Tk Map events.
        if sys.platform!='win32':
            yield; return
        # A Python CBT hook re-enters Tk's native modal loop unsafely on some
        # Python/Tk builds. A short-lived Win32 helper avoids that reentrancy.
        import os
        import subprocess
        import tempfile
        from pathlib import Path
        rect=[self.owner.winfo_rootx(),self.owner.winfo_rooty(),self.owner.winfo_width(),self.owner.winfo_height()]
        with tempfile.TemporaryDirectory(prefix='quick-sheet-dialog-') as folder:
            active=Path(folder)/'active'; active.touch()
            python=getattr(sys,'_base_executable',sys.executable)
            process=subprocess.Popen([python,str(Path(__file__).resolve()),'--center-native',str(os.getpid()),str(active),*map(str,rect)],creationflags=subprocess.CREATE_NO_WINDOW)
            try: yield
            finally:
                active.unlink(missing_ok=True)
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.terminate(); process.wait(timeout=2)

    def __getattr__(self,name):
        module=next((m for m in (messagebox,filedialog,colorchooser) if hasattr(m,name)),None)
        if module is None: raise AttributeError(name)
        def show(*args,**kwargs):
            kwargs['parent']=self.owner
            self.owner.update_idletasks()
            previous=self._mapped
            self._mapped=set()
            try:
                with self._windows_centering(): return getattr(module,name)(*args,**kwargs)
            finally: self._mapped=previous
        return show


class SizeDialog(CenteredWindow):
    """Modal dimension previews with dialog-local undo and a single app undo."""
    def __init__(self,app):
        super().__init__(app,'Cell size')
        self.app=app
        self.bounds=app.bounds()
        self.initial=self.snapshot()
        self.initial_selection=self.selection()
        self.initial_dirty=app.dirty
        import json
        self.initial_sheet=json.dumps(app.sheet.dump())
        self.history=[]
        self.cell_address=tk.StringVar()
        self.cell_contents=tk.StringVar()
        ttk.Label(self,textvariable=self.cell_address).grid(row=0,column=0,padx=12,pady=10,sticky='w')
        ttk.Entry(self,textvariable=self.cell_contents,state='readonly',width=18).grid(row=0,column=1,padx=12,pady=10)
        self.width=tk.StringVar()
        self.height=tk.StringVar()
        for i,(label,var) in enumerate([('Column width (pixels)',self.width),('Row height (pixels)',self.height)],1):
            ttk.Label(self,text=label).grid(row=i,column=0,padx=12,pady=10,sticky='w')
            ttk.Entry(self,textvariable=var,width=10).grid(row=i,column=1,padx=12,pady=10)
        arrows=ttk.Frame(self); arrows.grid(row=0,column=2,rowspan=3,padx=(0,12),pady=10,sticky='ns')
        self.up_button=ttk.Button(arrows,text='↑',width=3,command=lambda:self.move_row(-1))
        self.up_button.pack(side='top',pady=(0,6))
        self.down_button=ttk.Button(arrows,text='↓',width=3,command=lambda:self.move_row(1))
        self.down_button.pack(side='top')
        self.buttons=ttk.Frame(self); self.buttons.grid(row=3,column=0,columnspan=3,padx=12,pady=12)
        for label,command in [('Ok',self.accept),('Apply',self.apply),('Undo',self.undo_preview),('Cancel',self.cancel)]:
            button=ttk.Button(self.buttons,text=label,command=command); button.pack(side='left',padx=3)
            if label=='Undo': self.undo_button=button; button.state(['disabled'])
        self.load_cell()
        self.protocol('WM_DELETE_WINDOW',self.cancel)
        self.bind('<Escape>',lambda e:self.cancel())
        self.bind('<Return>',lambda e:self.accept())
        self.show()
        self.grab_set()

    def selection(self):
        return (self.app.active,self.app.anchor,self.app.top,self.app.left)

    def restore_selection(self,selection):
        active,anchor,top,left=selection
        self.app.top,self.app.left=top,left
        self.app.select(*active)
        self.app.anchor=anchor
        self.app.draw()
        self.bounds=self.app.bounds()

    def load_cell(self):
        from sheet import address
        row,col=self.app.active
        self.cell_address.set('Cell '+address(row,col))
        self.cell_contents.set(self.app.sheet.raw(row,col))
        self.width.set(str(self.app.column_width(col)))
        self.height.set(str(self.app.row_height(row)))
        self.loaded_dimensions=(self.width.get(),self.height.get())
        self.up_button.state(['disabled'] if row==0 else ['!disabled'])

    def move_row(self,step):
        row,col=self.app.active
        target=max(0,row+step)
        if target==row: return
        if (self.width.get(),self.height.get())!=self.loaded_dimensions and not self.apply(): return
        if target not in self.app.visible_rows:
            self.app.top=max(0,target-(1 if self.app.sheet.table else 0))
        self.app.select(target,col)
        self.bounds=self.app.bounds()
        self.load_cell()

    def snapshot(self): return (self.app.sheet.col_widths.copy(),self.app.sheet.row_heights.copy())

    def restore(self,snapshot):
        self.app.sheet.col_widths=snapshot[0].copy()
        self.app.sheet.row_heights=snapshot[1].copy()
        self.app.dirty=self.initial_dirty or snapshot!=self.initial
        self.app.refresh_title()
        self.app.draw()

    def apply(self):
        try:
            width,height=int(self.width.get()),int(self.height.get())
            if not 35<=width<=1000 or not 20<=height<=500: raise ValueError
        except ValueError:
            self.app.dialogs.showerror('Cell size','Enter a column width from 35 to 1000 and a row height from 20 to 500.')
            return False
        a,b,d,f=self.bounds
        if all(self.app.column_width(c)==width for c in range(b,f+1)) and all(self.app.row_height(r)==height for r in range(a,d+1)): return True
        self.history.append((self.snapshot(),self.selection()))
        for c in range(b,f+1): self.app.sheet.col_widths[str(c)]=width
        for r in range(a,d+1): self.app.sheet.row_heights[str(r)]=height
        self.app.changed()
        self.undo_button.state(['!disabled'])
        self.loaded_dimensions=(self.width.get(),self.height.get())
        return True

    def undo_preview(self):
        if not self.history: return
        snapshot,selection=self.history.pop()
        self.restore(snapshot)
        self.restore_selection(selection)
        self.load_cell()
        if not self.history: self.undo_button.state(['disabled'])

    def accept(self):
        if not self.apply(): return
        if self.snapshot()!=self.initial:
            self.app.undo_stack.append(self.initial_sheet)
            self.app.undo_stack=self.app.undo_stack[-100:]
            self.app.redo_stack.clear()
        self.grab_release(); self.destroy()

    def cancel(self):
        self.restore(self.initial)
        self.restore_selection(self.initial_selection)
        self.grab_release(); self.destroy()


def _center_windows_dialogs(pid,active,owner):
    """Run only in a helper process; never call Tk from a Win32 callback."""
    import ctypes
    import time
    from pathlib import Path
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes=[wintypes.HWND]
    user.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    parent=kernel.OpenProcess(0x00100000,False,pid)
    centered=set()
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    @callback_type
    def center(hwnd,param):
        process_id=wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd,ctypes.byref(process_id))
        if process_id.value!=pid or not user.IsWindowVisible(hwnd): return True
        name=ctypes.create_unicode_buffer(64); user.GetClassNameW(hwnd,name,64)
        if name.value!='#32770': return True
        rect=wintypes.RECT()
        if user.GetWindowRect(hwnd,ctypes.byref(rect)):
            size=(hwnd,rect.right-rect.left,rect.bottom-rect.top)
            if size not in centered:
                x=owner[0]+(owner[2]-size[1])//2; y=owner[1]+(owner[3]-size[2])//2
                user.SetWindowPos(hwnd,None,x,y,0,0,0x0015)
                centered.add(size)
        return True
    user.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    try:
        while Path(active).exists() and (not parent or kernel.WaitForSingleObject(parent,0)==0x102):
            user.EnumWindows(center,0)
            time.sleep(0.01)
    finally:
        if parent: kernel.CloseHandle(parent)


if __name__=='__main__' and sys.platform=='win32' and len(sys.argv)==8 and sys.argv[1]=='--center-native':
    _center_windows_dialogs(int(sys.argv[2]),sys.argv[3],list(map(int,sys.argv[4:])))

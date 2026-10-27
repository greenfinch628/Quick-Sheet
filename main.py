"""Quick-Sheet — launch with python main.py."""
import csv
import json
import io
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font, simpledialog, colorchooser
from sheet import Sheet, address, coordinates
from formulas import translate
from fileio import read_sheet, write_sheet
from dialogs import Dialogs, SizeDialog
import re


class App(tk.Tk):
    W, H, GUTTER = 125, 28, 52
    HEADER_BG = '#dce4ed'
    DROPDOWN_WIDTH = 24

    def __init__(self, state_path=None):
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('QuickSheet.Desktop')
        super().__init__(className='QuickSheet')
        self.withdraw()
        self._restored_geometry=None
        self._restored_maximized=False
        self.dialogs=Dialogs(self)
        icon_path=Path(__file__).resolve().parent/'assets'/'Quick-Sheet.png'
        if icon_path.exists():
            self.app_icon=tk.PhotoImage(file=str(icon_path))
            self.iconphoto(True,self.app_icon)
        if sys.platform=='win32':
            ico_path=str(Path(__file__).resolve().parent/'assets'/'Quick-Sheet.ico')
            self.iconbitmap(default=ico_path)
            self.iconbitmap(ico_path)
        self.geometry('1100x720')
        self.minsize(650, 400)
        self.sheet = Sheet()
        self.path = None
        self.dirty = False
        self.active = (0, 0)
        self.anchor = (0, 0)
        self.top = self.left = 0
        self.editor = None
        self.resize_state = None
        self._header_axis=None
        self.undo_stack = []
        self.redo_stack = []
        self.state_path = Path(state_path) if state_path else Path(__file__).resolve().parent / '.mini-session.json'
        self.internal_clipboard = None
        self.search_text = ''
        self.recent_files = []
        self.table_var = tk.BooleanVar()
        formatting = ttk.Frame(self, padding=(10, 2, 10, 8))
        formatting.pack(fill='x')
        ttk.Label(formatting, text='Cell Format').pack(side='left')
        self.fmt = ttk.Combobox(formatting, values=['General', 'Text', 'Decimal', 'Currency', 'Percentage', 'Date', 'Date/time'], state='readonly', width=12)
        self.fmt.set('General')
        self.fmt.pack(side='left', padx=6)
        self.fmt.bind('<<ComboboxSelected>>', lambda e: self.format_cells())
        ttk.Label(formatting, text='Decimals').pack(side='left')
        self._updating_decimals=False
        self._decimal_dirty=False
        self._decimal_after=None
        self.dec = tk.IntVar(value=0)
        self.dec.trace_add('write',self.schedule_decimals)
        self.decimal_control=ttk.Spinbox(formatting,from_=0,to=10,textvariable=self.dec,width=3,command=self.format_decimals)
        self.decimal_control.pack(side='left',padx=6)
        self.decimal_control.bind('<Return>',self.format_decimals)
        self.decimal_control.bind('<FocusOut>',self.format_decimals)
        ttk.Button(formatting, text='Σ Sum below selection', command=self.sum_below).pack(side='left', padx=10)
        ttk.Button(formatting,text='Style…',command=self.style_dialog).pack(side='left')
        ttk.Button(formatting,text='Size…',command=self.size_dialog).pack(side='left',padx=4)
        ttk.Button(formatting, text='Clear Sheet', command=self.clear_sheet).pack(side='right')
        formula = ttk.Frame(self, padding=(10, 0, 10, 8))
        formula.pack(fill='x')
        self.cell_label = ttk.Label(formula, width=8)
        self.cell_label.pack(side='left')
        functions=ttk.Menubutton(formula,text='Functions')
        self.function_menu=tk.Menu(functions,tearoff=False)
        for label in ('Auto Sum','Sum','Average','Min','Max','Count','CountA','ABS','Today','Now'):
            self.function_menu.add_command(label=label,command=lambda n=label.upper().replace(' ',''):self.insert_function(n))
        functions.configure(menu=self.function_menu)
        functions.pack(side='left',padx=(0,8))
        self.formula = ttk.Entry(formula)
        self.formula.pack(side='left', fill='x', expand=True)
        self.formula.bind('<Return>', self.formula_commit)
        self.formula.bind('<Button-3>',self.formula_context_menu)
        self.formula.bind('<Shift-F10>',self.formula_context_menu)
        frame = ttk.Frame(self)
        frame.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(frame, background='white', highlightthickness=0, takefocus=True)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.vscroll = ttk.Scrollbar(frame, orient='vertical', command=self.scroll_y)
        self.vscroll.grid(row=0, column=1, sticky='ns')
        self.hscroll = ttk.Scrollbar(frame, orient='horizontal', command=self.scroll_x)
        self.hscroll.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.status = ttk.Label(self, padding=8)
        self.status.pack(fill='x')
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.finish_resize)
        self.canvas.bind('<Motion>',self.resize_cursor)
        self.canvas.bind('<Double-1>', self.double_click)
        self.canvas.bind('<Key>', self.key)
        self.canvas.bind('<MouseWheel>', lambda e: self.scroll_y('scroll', -int(e.delta/120), 'units'))
        self.canvas.bind('<Button-4>', lambda e: self.scroll_y('scroll', -1, 'units'))
        self.canvas.bind('<Button-5>', lambda e: self.scroll_y('scroll', 1, 'units'))
        for shortcut, command in [('s', self.save), ('o', self.open), ('n', self.new), ('z', self.undo), ('y', self.redo)]:
            self.bind('<Control-'+shortcut+'>', lambda e, c=command: c())
        self.canvas.bind('<Control-c>', self.copy)
        self.canvas.bind('<Control-x>', self.cut)
        self.canvas.bind('<Control-v>', self.paste)
        self.canvas.bind('<Control-d>', lambda e: self.fill(False))
        self.canvas.bind('<Control-r>', lambda e: self.fill(True))
        self.canvas.bind('<Button-3>', self.context_menu)
        self.canvas.bind('<Shift-F10>', self.context_menu)
        self.bind('<Control-f>', lambda e: self.search_dialog())
        self.bind('<Control-h>', lambda e: self.search_dialog(True))
        self.bind('<F3>', lambda e: self.find_next())
        self.bind('<Control-Shift-S>', lambda e: self.save(True))
        self.build_menus()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.apply_fonts()
        self.select(0,0)
        # Settle menu geometry before restoring the saved client size on Windows.
        self.update_idletasks()
        self.restore_session()
        self.update_recent_menu()
        self.after(30000,self.recalculate_clock)
        self.deiconify()
        self.update_idletasks()
        if self._restored_geometry and not self._restored_maximized:
            self.geometry(self._restored_geometry)

    def recalculate_clock(self):
        self.draw()
        self.after(30000,self.recalculate_clock)

    def build_menus(self):
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)
        groups = [
            ('File', [('New', self.new, 'Ctrl+N'), ('Open…', self.open, 'Ctrl+O'),
                      ('Save', self.save, 'Ctrl+S'), ('Save as…', lambda: self.save(True), 'Ctrl+Shift+S'),
                      None, ('Close', self.close, '')]),
            ('Edit', [('Undo', self.undo, 'Ctrl+Z'), ('Redo', self.redo, 'Ctrl+Y'), None,
                      ('Cut', lambda: self.clipboard_action('cut'), 'Ctrl+X'),
                      ('Copy', lambda: self.clipboard_action('copy'), 'Ctrl+C'),
                      ('Paste', lambda: self.clipboard_action('paste'), 'Ctrl+V'), None,
                      ('Fill down', self.fill, 'Ctrl+D'), ('Fill right', lambda: self.fill(True), 'Ctrl+R'),
                      ('Insert rows', lambda: self.structure(0), ''), ('Delete rows', lambda: self.structure(0,True), ''),
                      ('Insert columns', lambda: self.structure(1), ''), ('Delete columns', lambda: self.structure(1,True), '')]),
            ('Search', [('Find…', self.search_dialog, 'Ctrl+F'), ('Find next', self.find_next, 'F3'),
                        ('Find and Replace…', lambda: self.search_dialog(True), 'Ctrl+H')]),
            ('Data', [('Import CSV…', self.import_csv, ''), ('Export CSV…', self.export, ''), ('Import TSV…', lambda:self.import_delimited('.tsv'), ''), None,
                      ('Sort A–Z', lambda: self.sort_column(self.active[1]), ''),
                      ('Sort Z–A', lambda: self.sort_column(self.active[1], True), ''),
                      ('Sort numbers ascending', lambda: self.sort_column(self.active[1], numeric=True), ''),
                      ('Sort numbers descending', lambda: self.sort_column(self.active[1], True, True), ''),
                      ('Clear filters', self.clear_filters, '')])]
        for title, items in groups:
            menu = tk.Menu(self.menubar, tearoff=False)
            self.menubar.add_cascade(label=title, menu=menu)
            for item in items:
                if item is None: menu.add_separator()
                else: menu.add_command(label=item[0], command=item[1], accelerator=item[2])
            if title == 'File':
                self.recent_menu=tk.Menu(menu,tearoff=False)
                menu.add_cascade(label='Recent files',menu=self.recent_menu)
            if title == 'Edit':
                menu.add_separator()
                settings = tk.Menu(menu, tearoff=False)
                settings.add_command(label='Fonts…', command=self.fonts)
                menu.add_cascade(label='Settings', menu=settings)
        tools = tk.Menu(self.menubar, tearoff=False)
        tools.add_checkbutton(label='Freeze First Row', variable=self.table_var,
                              command=self.table_toggle)
        self.menubar.add_cascade(label='Tools', menu=tools)

    def clipboard_action(self, action):
        widget = self.focus_get()
        if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox, ttk.Spinbox)):
            widget.event_generate({'cut':'<<Cut>>', 'copy':'<<Copy>>', 'paste':'<<Paste>>'}[action])
        else:
            getattr(self, action)()

    def context_menu(self, e):
        self.finish_edit()
        header=None
        if getattr(e,'num',None)==3:
            if e.y<self.H and e.x>=self.GUTTER:
                header=1; self.select_header(1,self.column_at(e.x))
            elif e.x<self.GUTTER and e.y>=self.H:
                row=self.row_at(e.y)
                if row is not None: header=0; self.select_header(0,row)
            else:
                pos=self.hit(e)
                if pos:
                    a,b,d,f=self.bounds()
                    if not (a<=pos[0]<=d and b<=pos[1]<=f): self.select(*pos)
            x,y=e.x_root,e.y_root
        else: x,y=self.canvas.winfo_rootx()+self.GUTTER,self.canvas.winfo_rooty()+self.H
        self.canvas.focus_set()
        menu=tk.Menu(self,tearoff=False)
        if header is not None:
            labels=('Insert rows above','Insert rows below','Delete rows') if header==0 else ('Insert columns left','Insert columns right','Delete columns')
            menu.add_command(label=labels[0],command=lambda:self.structure(header))
            menu.add_command(label=labels[1],command=lambda:self.structure(header,after=True))
            menu.add_command(label=labels[2],command=lambda:self.structure(header,delete=True))
        else:
            for label,command,shortcut in [('Cut',self.cut,'Ctrl+X'),('Copy',self.copy,'Ctrl+C'),('Paste',self.paste,'Ctrl+V')]:
                menu.add_command(label=label,command=command,accelerator=shortcut)
        try: menu.tk_popup(x,y)
        finally: menu.grab_release()
        return 'break'

    def select_header(self,axis,index,extend=False,preserve=True):
        a,b,d,f=self.bounds()
        preserve=preserve and self._header_axis in (None,axis)
        if axis==0:
            start,end=(min(self.anchor[0],index),max(self.anchor[0],index)) if extend else ((a,d) if preserve and a<=index<=d else (index,index))
            self.select(start,0); self.select(end,max(25,self.sheet.extent()[1]-1),True)
        else:
            start,end=(min(self.anchor[1],index),max(self.anchor[1],index)) if extend else ((b,f) if preserve and b<=index<=f else (index,index))
            self.select(0,start); self.select(max(199,self.sheet.extent()[0]-1),end,True)
        self._header_axis=axis

    def checkpoint(self):
        self.undo_stack.append(json.dumps(self.sheet.dump()))
        self.undo_stack = self.undo_stack[-100:]
        self.redo_stack.clear()

    def refresh_title(self):
        self.title(('• ' if self.dirty else '')+(self.path or 'Untitled')+' — Quick-Sheet')

    def changed(self):
        self.dirty=True
        self.refresh_title()
        self.draw()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(json.dumps(self.sheet.dump()))
            self.sheet = Sheet.from_data(json.loads(self.undo_stack.pop()))
            self.table_var.set(self.sheet.table)
            self.apply_fonts()
            self.update_format_controls()
            self.changed()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(json.dumps(self.sheet.dump()))
            self.sheet = Sheet.from_data(json.loads(self.redo_stack.pop()))
            self.table_var.set(self.sheet.table)
            self.apply_fonts()
            self.update_format_controls()
            self.changed()

    def bounds(self):
        r,c = self.active
        a,b = self.anchor
        return min(r,a), min(c,b), max(r,a), max(c,b)

    def rows(self):
        count = max(200, self.sheet.extent()[0]+50, self.active[0]+30)
        result = []
        for r in range(1 if self.sheet.table else 0, count):
            if all(self.sheet.display(r,int(c)) == v for c,v in self.sheet.filters.items()): result.append(r)
        return ([0] if self.sheet.table else []) + result[self.top:]

    def column_width(self,c):
        return max(35,int(self.sheet.col_widths.get(str(c),self.W)))

    def row_height(self,r):
        return max(20,int(self.sheet.row_heights.get(str(r),self.H)))

    def cell_rect(self,r,c):
        x=self.GUTTER+sum(self.column_width(j) for j in range(self.left,c))
        y=self.H+sum(self.row_height(j) for j in self.visible_rows[:self.visible_rows.index(r)])
        return x,y,self.column_width(c),self.row_height(r)

    def column_at(self,x):
        edge=self.GUTTER
        for c in range(self.left,self.left+1000):
            edge+=self.column_width(c)
            if x<edge: return c
        return self.left

    def draw(self):
        if not hasattr(self,'canvas'): return
        cv=self.canvas; cv.delete('all')
        width,height=cv.winfo_width(),cv.winfo_height()
        self.visible_rows=[]
        y=self.H
        for r in self.rows():
            if y>=height and self.visible_rows: break
            self.visible_rows.append(r); y+=self.row_height(r)
        r1,c1,r2,c2=self.bounds()
        fonts={}
        x=self.GUTTER; c=self.left
        while x<max(width,self.GUTTER+1):
            w=self.column_width(c)
            cv.create_rectangle(x,0,x+w,self.H,fill=self.HEADER_BG,outline='#ccd5df')
            cv.create_text(x+8,self.H/2,text=address(0,c)[:-1],anchor='w',font=self.menu_font)
            y=self.H
            for r in self.visible_rows:
                h=self.row_height(r)
                st=self.sheet.styles.get(address(r,c),{})
                selected=r1<=r<=r2 and c1<=c<=c2
                frozen=self.sheet.table and r==0
                bg='#deebff' if selected else st.get('background','#eef3f8' if frozen else 'white')
                cv.create_rectangle(x,y,x+w,y+h,fill=bg,outline='#e1e6ec')
                key=(bool(st.get('bold')),bool(st.get('italic')))
                if key not in fonts:
                    fonts[key]=font.Font(family=self.sheet.cell_font,size=self.sheet.cell_size,
                                         weight='bold' if key[0] else 'normal',slant='italic' if key[1] else 'roman')
                text=self.sheet.display(r,c)
                if frozen: text=text or address(0,c)[:-1]
                available=w-14-(self.DROPDOWN_WIDTH if frozen else 0)
                while fonts[key].measure(text)>available and len(text)>1: text=text[:-2]+'…'
                alignment=st.get('alignment','left')
                tx,anchor={'left':(x+7,'w'),'center':(x+available/2+7,'center'),'right':(x+available+7,'e')}.get(alignment,(x+7,'w'))
                cv.create_text(tx,y+h/2,text=text,anchor=anchor,font=fonts[key],fill=st.get('foreground','#192c3b'))
                if frozen:
                    ax=x+w-self.DROPDOWN_WIDTH/2; ay=y+h/2
                    cv.create_line(x+w-self.DROPDOWN_WIDTH,y+5,x+w-self.DROPDOWN_WIDTH,y+h-5,fill='#ccd5df')
                    cv.create_polygon(ax-4,ay-2,ax+4,ay-2,ax,ay+3,fill='#192c3b',tags=('header_dropdown',f'dropdown_{c}'))
                if (r,c)==self.active: cv.create_rectangle(x+1,y+1,x+w-1,y+h-1,outline='#2563eb',width=2)
                y+=h
            x+=w; c+=1
        self.render_fonts=fonts
        cv.create_rectangle(0,0,self.GUTTER,self.H,fill=self.HEADER_BG,outline='#ccd5df')
        y=self.H
        for r in self.visible_rows:
            h=self.row_height(r)
            cv.create_rectangle(0,y,self.GUTTER,y+h,fill=self.HEADER_BG,outline='#ccd5df')
            cv.create_text(self.GUTTER-8,y+h/2,text=str(r+1),anchor='e',font=self.menu_font)
            y+=h
        nums=[]
        if (r2-r1+1)*(c2-c1+1)<=100000:
            for r in range(r1,r2+1):
                for col in range(c1,c2+1):
                    try:
                        val=self.sheet.value(r,col)
                        if isinstance(val,(int,float)): nums.append(val)
                    except Exception: pass
        self.status.config(text=f'{address(r1,c1)}:{address(r2,c2)}    |    Numbers: {len(nums)}    Sum: {sum(nums):g}    |    Enter to edit · Ctrl+D fill down · Ctrl+R fill right')
        count=max(200,self.sheet.extent()[0]+50)
        self.vscroll.set(self.top/count,min(1,(self.top+len(self.visible_rows))/count))
        self.hscroll.set(self.left/100,min(1,c/100))

    def select(self,r,c,extend=False):
        if self._decimal_dirty: self.format_decimals()
        self._header_axis=None
        self.active=(max(0,r),max(0,c))
        if not extend: self.anchor=self.active
        self.cell_label.config(text=address(*self.active))
        self.formula.delete(0,'end')
        self.formula.insert(0,self.sheet.raw(*self.active))
        self.update_format_controls()
        self.draw()

    def update_format_controls(self):
        style=self.sheet.style(*self.active)
        self.fmt.set(style.get('format','General'))
        self._updating_decimals=True
        try: self.dec.set(style.get('decimals',0))
        finally: self._updating_decimals=False
        self._decimal_dirty=False

    def row_at(self,y):
        edge=self.H
        for row in self.visible_rows:
            edge+=self.row_height(row)
            if self.H<=y<edge: return row
        return None

    def resize_handle(self,e):
        if e.y<self.H and e.x>=self.GUTTER:
            edge=self.GUTTER
            for col in range(self.left,self.left+1000):
                edge+=self.column_width(col)
                if abs(e.x-edge)<=4: return 1,col
                if edge>e.x+4: break
        elif e.x<self.GUTTER and e.y>=self.H:
            edge=self.H
            for row in self.visible_rows:
                edge+=self.row_height(row)
                if abs(e.y-edge)<=4: return 0,row
                if edge>e.y+4: break
        return None

    def resize_cursor(self,e):
        handle=self.resize_handle(e)
        self.canvas.configure(cursor=('sb_h_double_arrow' if handle[0]==1 else 'sb_v_double_arrow') if handle else '')

    def finish_resize(self,e=None):
        if self.resize_state is None: return
        axis,index,start,original,before,dirty,initial_sheet=self.resize_state
        dimensions=self.sheet.col_widths if axis==1 else self.sheet.row_heights
        if dimensions==before:
            self.dirty=dirty; self.refresh_title()
        else:
            self.undo_stack.append(initial_sheet)
            self.undo_stack=self.undo_stack[-100:]
            self.redo_stack.clear()
        self.resize_state=None
        self.canvas.configure(cursor='')
        return 'break'

    def hit(self,e):
        if e.x<self.GUTTER or e.y<self.H: return None
        y=self.H
        for r in self.visible_rows:
            y+=self.row_height(r)
            if e.y<y: return r,self.column_at(e.x)
        return None

    def over_dropdown(self,pos,e):
        x,y,w,h=self.cell_rect(*pos)
        return e.x>=x+w-self.DROPDOWN_WIDTH

    def click(self,e):
        self.finish_edit()
        self.canvas.focus_set()
        handle=self.resize_handle(e)
        if handle:
            axis,index=handle
            original=self.column_width(index) if axis==1 else self.row_height(index)
            before=(self.sheet.col_widths if axis==1 else self.sheet.row_heights).copy()
            self.resize_state=(axis,index,e.x if axis==1 else e.y,original,before,self.dirty,json.dumps(self.sheet.dump()))
            return 'break'
        if e.y < self.H and e.x >= self.GUTTER:
            col = self.column_at(e.x)
            self.select_header(1,col,extend=bool(e.state&1),preserve=False)
            return
        if e.x<self.GUTTER and e.y>=self.H:
            row=self.row_at(e.y)
            if row is not None:
                self.select_header(0,row,extend=bool(e.state&1),preserve=False)
            return
        pos=self.hit(e)
        if pos:
            self.select(*pos,extend=bool(e.state&1))
            if self.sheet.table and pos[0]==0 and self.over_dropdown(pos,e):
                self.filter_menu(pos[1],e)

    def drag(self,e):
        if self.resize_state is not None:
            axis,index,start,original,before,dirty,initial_sheet=self.resize_state
            size=max(35 if axis==1 else 20,min(1000 if axis==1 else 500,original+(e.x if axis==1 else e.y)-start))
            dimensions=self.sheet.col_widths if axis==1 else self.sheet.row_heights
            if size==original:
                dimensions.clear(); dimensions.update(before)
            else: dimensions[str(index)]=size
            self.changed()
            return 'break'
        if self._header_axis==0 and e.x<self.GUTTER:
            row=self.row_at(e.y)
            if row is not None: self.select_header(0,row,extend=True)
            return
        if self._header_axis==1 and e.y<self.H:
            self.select_header(1,self.column_at(e.x),extend=True)
            return
        pos=self.hit(e)
        if pos: self.select(*pos,extend=True)

    def double_click(self,e):
        pos=self.hit(e)
        if pos and self.sheet.table and pos[0]==0 and self.over_dropdown(pos,e):
            self.click(e)
        else:
            self.edit()

    def key(self,e):
        if e.state&4: return
        r,c=self.active
        if e.keysym in ('Up','Down','Left','Right','Tab'):
            dr,dc={'Up':(-1,0),'Down':(1,0),'Left':(0,-1),'Right':(0,1),'Tab':(0,1)}[e.keysym]
            rows=self.rows()
            if dr and r in rows:
                idx=rows.index(r)+dr
                r=rows[idx] if 0<=idx<len(rows) else max(0,r+dr)
            else: r+=dr
            c=max(0,c+dc)
            if c<self.left: self.left=c
            while c>self.left and sum(self.column_width(j) for j in range(self.left,c+1))>self.canvas.winfo_width()-self.GUTTER: self.left+=1
            if r not in self.visible_rows: self.top=max(0,self.top+dr)
            self.select(r,c, bool(e.state&1))
            return 'break'
        if e.keysym in ('Delete','BackSpace'):
            self.checkpoint()
            a,b,d,f=self.bounds()
            for row in range(a,d+1):
                for col in range(b,f+1): self.sheet.set(row,col,'')
            self.changed()
            self.select(*self.active)
        elif e.keysym in ('Return','F2'): self.edit()
        elif e.char and e.char.isprintable(): self.edit(e.char)

    def edit(self,initial=None):
        if self.editor: return
        r,c=self.active
        if r not in self.visible_rows: return
        x,y,w,h=self.cell_rect(r,c)
        self.editor=ttk.Entry(self.canvas,font=self.cell_font)
        self.editor.place(x=x+1,y=y+1,width=w-2,height=h-2)
        self.editor.insert(0,self.sheet.raw(r,c) if initial is None else initial)
        if initial is None: self.editor.select_range(0,'end')
        self.editor.focus_set()
        self.editor.bind('<Return>',lambda e:self.finish_edit(move=True))
        self.editor.bind('<KP_Enter>', lambda e: self.finish_edit(move=True))
        self.editor.bind('<Escape>',lambda e:self.finish_edit(cancel=True))
        self.editor.bind('<Tab>',lambda e:self.finish_edit(move=True,horizontal=True))
        self.editor.bind('<FocusOut>',lambda e:self.finish_edit())

    def finish_edit(self,move=False,cancel=False,horizontal=False):
        if not self.editor: return
        entry=self.editor
        value=entry.get()
        self.editor=None
        entry.destroy()
        if not cancel and value!=self.sheet.raw(*self.active):
            self.checkpoint()
            self.sheet.set(*self.active,value)
            self.changed()
        r,c=self.active
        self.select(r+(move and not horizontal),c+(move and horizontal))
        if move or cancel: self.canvas.focus_set()
        return 'break'

    def formula_commit(self,e=None):
        self.checkpoint()
        self.sheet.set(*self.active,self.formula.get())
        self.changed()
        self.canvas.focus_set()

    def scroll_y(self,kind,value,unit=None):
        self.finish_edit()
        count=max(200,self.sheet.extent()[0]+50)
        self.top=max(0,min(count-1,int(float(value)*count) if kind=='moveto' else self.top+int(value)*(15 if unit=='pages' else 3)))
        self.draw()

    def scroll_x(self,kind,value,unit=None):
        self.finish_edit()
        self.left=max(0,min(99,int(float(value)*100) if kind=='moveto' else self.left+int(value)))
        self.draw()

    def format_cells(self):
        self.finish_edit()
        if self._decimal_dirty: self.format_decimals()
        self.checkpoint()
        a,b,d,f=self.bounds()
        for r in range(a,d+1):
            for c in range(b,f+1): self.sheet.styles.setdefault(address(r,c),{}).update(format=self.fmt.get())
        self.changed()

    def schedule_decimals(self,*args):
        if self._updating_decimals: return
        self._decimal_dirty=True
        if self._decimal_after is not None: self.after_cancel(self._decimal_after)
        self._decimal_after=self.after(300,self.format_decimals)

    def format_decimals(self,event=None):
        if self._decimal_after is not None:
            self.after_cancel(self._decimal_after); self._decimal_after=None
        if not self._decimal_dirty: return
        # Clear the flag before finishing an editor, which may update selection.
        self._decimal_dirty=False
        self.finish_edit()
        try: decimals=int(self.dec.get())
        except (ValueError,tk.TclError): return
        if not 0<=decimals<=10: return
        a,b,d,f=self.bounds()
        cols=range(b,f+1)
        if all(self.sheet.column_decimals.get(str(c))==decimals for c in cols): return
        self.checkpoint()
        for c in cols: self.sheet.column_decimals[str(c)]=decimals
        self.changed()
        return 'break' if event and event.type==tk.EventType.KeyPress else None

    def insert_function(self,name):
        self.finish_edit()
        name=name.upper()
        if name=='AUTOSUM': return self.activate_autosum()
        if name in ('SUM','AVERAGE','MIN','MAX','COUNT','COUNTA'):
            row,col=self.active
            boundary=1 if self.sheet.table else 0
            end=row-1
            start=end
            while start>=boundary and self.sheet.raw(start,col)!='': start-=1
            start+=1
            if end<boundary or start>end:
                self.status.config(text=f'No contiguous cells above {address(row,col)} to use for {name}.')
                return False
            value=f'={name}({address(start,col)}:{address(end,col)})'
            self.formula.delete(0,'end'); self.formula.insert(0,value)
            self.formula_commit()
            return True
        self.formula.delete(0,'end')
        self.formula.insert(0,f'={name}()')
        self.formula.icursor(len(name)+2)
        self.formula.focus_set()
        return True

    def activate_autosum(self):
        if self._decimal_dirty: self.format_decimals()
        self.finish_edit()
        self.checkpoint()
        row=self.sheet.start_autosum()
        style=self.sheet.styles.get(address(row,1),{})
        if style.get('format') in ('Text','Date','Date/time'): style['format']='General'
        self.sheet.filters.clear()
        self.top=self.left=0
        self.select(row,0)
        self.changed()
        self.canvas.focus_set()
        return True

    def formula_context_menu(self,event):
        self.formula.focus_set()
        menu=tk.Menu(self,tearoff=False)
        for label,action in [('Cut','<<Cut>>'),('Copy','<<Copy>>'),('Paste','<<Paste>>')]:
            menu.add_command(label=label,command=lambda a=action:self.formula.event_generate(a))
        menu.add_command(label='Enter',command=self.formula_commit)
        x=getattr(event,'x_root',self.formula.winfo_rootx()+10)
        y=getattr(event,'y_root',self.formula.winfo_rooty()+10)
        try: menu.tk_popup(x,y)
        finally: menu.grab_release()
        return 'break'

    def clear_sheet(self):
        if self._decimal_dirty: self.format_decimals()
        self.finish_edit()
        self.checkpoint()
        self.sheet=Sheet()
        self.top=self.left=0
        self.table_var.set(False)
        self.apply_fonts()
        self.select(0,0)
        self.changed()

    def apply_style(self, **changes):
        self.finish_edit(); self.checkpoint()
        a,b,d,f=self.bounds()
        for r in range(a,d+1):
            for c in range(b,f+1): self.sheet.styles.setdefault(address(r,c),{}).update(changes)
        self.changed()

    def style_dialog(self):
        self.finish_edit()
        st=self.sheet.styles.get(address(*self.active),{})
        win=self.dialogs.window('Cell style')
        bold=tk.BooleanVar(value=st.get('bold',False)); italic=tk.BooleanVar(value=st.get('italic',False))
        ttk.Checkbutton(win,text='Bold',variable=bold).grid(row=0,column=0,padx=12,pady=10)
        ttk.Checkbutton(win,text='Italic',variable=italic).grid(row=0,column=1,padx=12)
        align=ttk.Combobox(win,values=['left','center','right'],state='readonly',width=10)
        align.set(st.get('alignment','left')); align.grid(row=1,column=0,padx=12,pady=10)
        colors={k:st.get(k,v) for k,v in [('foreground','#192c3b'),('background','#ffffff')]}
        def choose(k):
            picked=self.dialogs.askcolor(colors[k])[1]
            if picked: colors[k]=picked
        ttk.Button(win,text='Text color…',command=lambda:choose('foreground')).grid(row=2,column=0,padx=12,pady=10)
        ttk.Button(win,text='Fill color…',command=lambda:choose('background')).grid(row=2,column=1,padx=12,pady=10)
        def apply():
            self.apply_style(bold=bold.get(),italic=italic.get(),alignment=align.get(),**colors); win.destroy()
        ttk.Button(win,text='Apply',command=apply).grid(row=3,column=1,padx=12,pady=10)

    def size_dialog(self):
        self.finish_edit()
        if hasattr(self,'size_window') and self.size_window.winfo_exists():
            self.size_window.lift(); return self.size_window
        self.size_window=SizeDialog(self)
        return self.size_window

    def sum_below(self):
        self.finish_edit()
        a,b,d,f=self.bounds()
        if any(self.sheet.raw(d+1,c) for c in range(b,f+1)):
            self.dialogs.showinfo('Sum','The row below your selection contains data. Choose a range with an empty row below it.')
            return
        self.checkpoint()
        for c in range(b,f+1): self.sheet.set(d+1,c,f'=SUM({address(a,c)}:{address(d,c)})')
        self.changed()
        self.select(d+1,b)

    def table_toggle(self):
        self.finish_edit()
        self.checkpoint()
        self.sheet.table=self.table_var.get()
        self.sheet.filters.clear()
        self.top=0
        self.changed()

    def clear_filters(self):
        if not self.sheet.filters: return
        self.checkpoint()
        self.sheet.filters.clear()
        self.top=0
        self.changed()

    def filter_menu(self,col,e):
        menu=tk.Menu(self,tearoff=False)
        menu.add_command(label='Sort A–Z',command=lambda:self.sort_column(col))
        menu.add_command(label='Sort Z–A',command=lambda:self.sort_column(col,True))
        menu.add_command(label='Sort numbers ascending',command=lambda:self.sort_column(col,numeric=True))
        menu.add_command(label='Sort numbers descending',command=lambda:self.sort_column(col,True,True))
        menu.add_separator()
        def choose(value):
            self.finish_edit()
            self.checkpoint()
            if value is None: self.sheet.filters.pop(str(col),None)
            else: self.sheet.filters[str(col)]=value
            self.top=0
            self.changed()
        menu.add_command(label='All values',command=lambda:choose(None))
        values=sorted({self.sheet.display(r,col) for r in range(1,self.sheet.extent()[0])})
        for value in values:
            menu.add_command(label=value or '(blank)',command=lambda v=value:choose(v))
        try: menu.tk_popup(e.x_root,e.y_root)
        finally: menu.grab_release()

    def sort_column(self,col,descending=False,numeric=False):
        self.finish_edit()
        self.checkpoint()
        self.sheet.sort_rows(col,descending,numeric)
        self.top=0
        self.changed()
        self.select(0,col)

    def copy(self,e=None):
        self.finish_edit()
        a,b,d,f=self.bounds()
        out=io.StringIO()
        writer=csv.writer(out,delimiter='\t',lineterminator='\n')
        values=[[self.sheet.raw(r,c) for c in range(b,f+1)] for r in range(a,d+1)]
        styles=[[self.sheet.styles.get(address(r,c),{}).copy() for c in range(b,f+1)] for r in range(a,d+1)]
        writer.writerows(values)
        self.clipboard_clear()
        self.clipboard_append(out.getvalue())
        self.internal_clipboard=(out.getvalue(),values,styles,(a,b),False)
        return 'break'

    def cut(self,e=None):
        self.copy()
        self.internal_clipboard=(*self.internal_clipboard[:4],True)
        self.checkpoint()
        a,b,d,f=self.bounds()
        for r in range(a,d+1):
            for c in range(b,f+1):
                self.sheet.set(r,c,'')
                self.sheet.styles.pop(address(r,c),None)
        self.changed()
        self.select(*self.active,extend=True)
        return 'break'

    def paste(self,e=None):
        self.finish_edit()
        try: text=self.clipboard_get()
        except tk.TclError: return 'break'
        values=list(csv.reader(io.StringIO(text,newline=''),delimiter='\t'))
        if not values: return 'break'
        styles=None
        source=None
        cut=False
        if self.internal_clipboard and self.internal_clipboard[0]==text:
            _,values,styles,source,cut=self.internal_clipboard
        self.checkpoint()
        r,c,end_r,end_c=self.bounds()
        height,width=len(values),max(len(row) for row in values)
        if width==0: return 'break'
        selected_h,selected_w=end_r-r+1,end_c-c+1
        out_h,out_w=height,width
        if selected_h%height==0 and selected_w%width==0:
            out_h,out_w=selected_h,selected_w
        for i in range(out_h):
            row=values[i%height]
            for j in range(out_w):
                value=row[j%width] if j%width<len(row) else ''
                if source is not None and not cut:
                    value=translate(value,r+i-source[0]-i%height,c+j-source[1]-j%width)
                self.sheet.set(r+i,c+j,value)
                if styles is not None:
                    key=address(r+i,c+j)
                    self.sheet.styles.pop(key,None)
                    if styles[i%height][j%width]: self.sheet.styles[key]=styles[i%height][j%width].copy()
        self.changed()
        self.select(r,c)
        self.select(r+out_h-1,c+out_w-1,extend=True)
        return 'break'

    def fill(self, right=False):
        self.finish_edit()
        a,b,d,f=self.bounds()
        if (right and b==f) or (not right and a==d): return 'break'
        self.checkpoint()
        for r in range(a,d+1):
            for c in range(b,f+1):
                sr,sc=(r,b) if right else (a,c)
                if (r,c)==(sr,sc): continue
                self.sheet.set(r,c,translate(self.sheet.raw(sr,sc),r-sr,c-sc))
                style=self.sheet.styles.get(address(sr,sc),{}).copy()
                self.sheet.styles.pop(address(r,c),None)
                if style: self.sheet.styles[address(r,c)]=style
        self.changed()
        return 'break'

    def structure(self, axis, delete=False, after=False):
        self.finish_edit()
        a,b,d,f=self.bounds()
        index,count=(a,d-a+1) if axis==0 else (b,f-b+1)
        if after and not delete: index+=count
        self.checkpoint()
        self.sheet.structural_edit(axis,index,count,delete)
        self.changed()
        self.select(a,b)

    def apply_fonts(self):
        self.menu_font=font.Font(family=self.sheet.ui_font,size=self.sheet.ui_size,weight='normal',slant='roman')
        for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont',
                     'TkCaptionFont','TkSmallCaptionFont','TkIconFont','TkTooltipFont'):
            if name in font.names(self):
                font.nametofont(name,root=self).configure(family=self.sheet.ui_font,
                    size=self.sheet.ui_size,weight='normal',slant='roman')
        self.cell_font=font.Font(family=self.sheet.cell_font,size=self.sheet.cell_size)
        self.H=max(28,self.cell_font.metrics('linespace')+10)
        ttk.Style(self).configure('.',font=self.menu_font)
        self.option_add('*Menu.font',self.menu_font)
        if hasattr(self,'menubar'):
            def style_menu(menu):
                menu.configure(font=self.menu_font)
                for child in menu.winfo_children():
                    if isinstance(child,tk.Menu): style_menu(child)
            style_menu(self.menubar)
        self.draw()

    def search_dialog(self,replace=False):
        self.finish_edit()
        if hasattr(self,'search_window') and self.search_window.winfo_exists(): self.search_window.destroy()
        win=self.search_window=self.dialogs.window('Find and Replace' if replace else 'Find')
        query=tk.StringVar(value=self.search_text)
        replacement=tk.StringVar()
        ttk.Label(win,text='Find').grid(row=0,column=0,padx=10,pady=10)
        entry=ttk.Entry(win,textvariable=query,width=32)
        entry.grid(row=0,column=1,padx=10,pady=10)
        note=ttk.Label(win,text='Searches cell contents and formulas, ignoring case.')
        note.grid(row=3,column=0,columnspan=3,padx=10,pady=10)
        def find():
            self.search_text=query.get()
            if not self.find_next(): note.config(text='No matching cells.' if query.get() else 'Enter text to find.')
            else: note.config(text='Found '+address(*self.active))
        ttk.Button(win,text='Find next',command=find).grid(row=0,column=2,padx=10)
        if replace:
            ttk.Label(win,text='Replace with').grid(row=1,column=0,padx=10,pady=10)
            ttk.Entry(win,textvariable=replacement,width=32).grid(row=1,column=1,padx=10)
            def replace_one():
                self.search_text=query.get()
                if not query.get(): return
                if query.get().casefold() not in self.sheet.raw(*self.active).casefold():
                    find()
                    return
                count=self.replace_matches(query.get(),replacement.get(),False)
                note.config(text=f'Replaced {count} cell. Use Find next to continue.')
            def replace_all():
                self.search_text=query.get()
                count=self.replace_matches(query.get(),replacement.get(),True)
                note.config(text=f'Replaced text in {count} cells.')
            ttk.Button(win,text='Replace',command=replace_one).grid(row=1,column=2,padx=10)
            ttk.Button(win,text='Replace all',command=replace_all).grid(row=2,column=2,padx=10,pady=10)
        entry.bind('<Return>',lambda e:find())
        win.bind('<Escape>',lambda e:win.destroy())
        entry.focus_set()
        entry.select_range(0,'end')

    def find_next(self):
        self.finish_edit()
        if not self.search_text: return False
        matches=sorted(coordinates(key) for key,value in self.sheet.cells.items() if self.search_text.casefold() in value.casefold())
        if not matches: return False
        pos=next((point for point in matches if point>self.active),matches[0])
        self.sheet.filters.clear()
        self.top=max(0,pos[0]-(1 if self.sheet.table else 0))
        self.left=pos[1]
        self.select(*pos)
        return True

    def replace_matches(self,query,replacement,all_cells=False):
        self.finish_edit()
        if not query: return 0
        pattern=re.compile(re.escape(query),re.IGNORECASE)
        keys=list(self.sheet.cells) if all_cells else [address(*self.active)]
        changes={key:pattern.sub(lambda m:replacement,self.sheet.cells.get(key,''))
                 for key in keys if pattern.search(self.sheet.cells.get(key,''))}
        if changes:
            self.checkpoint()
            for key,value in changes.items(): self.sheet.set(*coordinates(key),value)
            self.changed()
            self.select(*self.active,extend=True)
        return len(changes)

    def persist_session(self):
        self.update_idletasks()
        state={'sheet':self.sheet.dump(),'path':self.path,'dirty':self.dirty,
               'active':self.active,'anchor':self.anchor,'top':self.top,'left':self.left,
               'geometry':self.geometry(),'maximized':self.state()=='zoomed',
               'undo':self.undo_stack,'redo':self.redo_stack,'search':self.search_text,'recent':self.recent_files}
        self.state_path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.state_path.with_suffix('.tmp')
        temp.write_text(json.dumps(state),encoding='utf-8')
        temp.replace(self.state_path)

    def restore_session(self):
        if not self.state_path.exists(): return
        try:
            state=json.loads(self.state_path.read_text(encoding='utf-8'))
            sheet=Sheet.from_data(state['sheet'])
            self.load(sheet,state.get('path'))
            self.dirty=bool(state.get('dirty'))
            self.top=max(0,int(state.get('top',0)))
            self.left=max(0,int(state.get('left',0)))
            self.select(*state.get('active',[0,0]))
            self.anchor=tuple(state.get('anchor',self.active))
            self.undo_stack=state.get('undo',[])[-100:]
            self.redo_stack=state.get('redo',[])[-100:]
            self.search_text=state.get('search','')
            self.recent_files=state.get('recent',[])[:10]
            self.update_recent_menu()
            self._restored_geometry=state.get('geometry')
            self._restored_maximized=bool(state.get('maximized'))
            if self._restored_geometry: self.geometry(self._restored_geometry)
            if state.get('maximized'):
                try: self.state('zoomed')
                except tk.TclError: self.attributes('-zoomed',True)
            self.title(('• ' if self.dirty else '')+(self.path or 'Untitled')+' — Quick-Sheet')
            self.draw()
        except Exception as error:
            self.after_idle(lambda text=str(error):self.dialogs.showerror('Could not restore previous session',text))

    def fonts(self):
        self.finish_edit()
        win=self.dialogs.window('Fonts')
        families=sorted(font.families())
        variables=[]
        controls=[]
        for i,(label,family,size) in enumerate([('Menus',self.sheet.ui_font,self.sheet.ui_size),('Cells',self.sheet.cell_font,self.sheet.cell_size)]):
            caption=ttk.Label(win,text=label)
            caption.grid(row=i,column=0,padx=12,pady=12)
            name=tk.StringVar(value=family)
            num=tk.IntVar(value=size)
            dropdown=ttk.Combobox(win,textvariable=name,values=families)
            dropdown.grid(row=i,column=1,padx=5)
            size_control=ttk.Spinbox(win,from_=8,to=36,textvariable=num,width=4)
            size_control.grid(row=i,column=2,padx=12)
            controls.append((caption,dropdown,size_control))
            variables.append((name,num))
        def apply():
            try: sizes=[max(8,min(36,v[1].get())) for v in variables]
            except (ValueError,tk.TclError): return
            self.checkpoint()
            self.sheet.ui_font,self.sheet.cell_font=[v[0].get() for v in variables]
            self.sheet.ui_size,self.sheet.cell_size=sizes
            self.apply_fonts()
            self.update_format_controls()
            self.changed()
            win.destroy()
        apply_button=ttk.Button(win,text='Apply',command=apply)
        apply_button.grid(row=2,column=2,padx=12,pady=12)
        win.update_idletasks()
        original_size=(win.winfo_reqwidth(),win.winfo_reqheight())
        for caption,dropdown,size_control in controls:
            caption.grid_configure(padx=4)
            dropdown.configure(width=int(dropdown.cget('width'))+8)
            dropdown.grid_configure(padx=3)
            size_control.grid_configure(padx=6)
        apply_button.grid_configure(column=0,columnspan=3,sticky='e')
        win.preferred_size=original_size
        win.show()

    def may_discard(self):
        self.finish_edit()
        if not self.dirty: return True
        answer=self.dialogs.askyesnocancel('Unsaved sheet','Save your changes first?')
        return False if answer is None else self.save() if answer else True

    def new(self):
        if self.may_discard(): self.load(Sheet(),None)

    def load(self,sheet,path):
        self.sheet,self.path,self.dirty=sheet,path,False
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.top=self.left=0
        self.table_var.set(sheet.table)
        self.apply_fonts()
        self.select(0,0)
        self.title((path or 'Untitled')+' — Quick-Sheet')

    def update_recent_menu(self):
        self.recent_menu.delete(0,'end')
        for path in self.recent_files:
            self.recent_menu.add_command(label=path,command=lambda p=path:self.open_path(p))
        if not self.recent_files: self.recent_menu.add_command(label='No recent files',state='disabled')

    def remember_file(self,path):
        path=str(Path(path).resolve())
        self.recent_files=[path]+[p for p in self.recent_files if p!=path][:9]
        self.update_recent_menu()

    def open(self):
        path=self.dialogs.askopenfilename(filetypes=[('Sheets','*.mini *.csv *.tsv *.xlsx'),('All files','*.*')])
        if path: self.open_path(path)

    def open_path(self,path):
        if not self.may_discard(): return
        try:
            sheet=read_sheet(path)
            native=Path(path).suffix.lower()=='.mini'
            self.load(sheet,str(path) if native else None)
            if not native: self.changed()
            self.remember_file(path)
            if Path(path).suffix.lower()=='.xlsx':
                self.dialogs.showinfo('Excel import','Imported the active worksheet. Quick-Sheet preserves supported cell data and styles. Save as a new file; other sheets, charts, and unsupported Excel features are not imported.')
        except Exception as error: self.dialogs.showerror('Could not open sheet',str(error))

    def import_csv(self):
        self.import_delimited('.csv')

    def import_delimited(self,ext):
        path=self.dialogs.askopenfilename(filetypes=[(ext[1:].upper(),'*'+ext),('All files','*.*')])
        if path: self.open_path(path)

    def save(self,save_as=False):
        self.finish_edit()
        path=self.path if not save_as else None
        if not path:
            path=self.dialogs.asksaveasfilename(defaultextension='.mini',filetypes=[('Quick-Sheet','*.mini'),('Excel','*.xlsx'),('CSV (values only)','*.csv'),('TSV (values only)','*.tsv')])
        if not path: return False
        ext=Path(path).suffix.lower()
        if ext in ('.csv','.tsv') and (self.sheet.styles or self.sheet.column_decimals or any(v.startswith('=') for v in self.sheet.cells.values())):
            if not self.dialogs.askyesno('Values only','CSV/TSV saves displayed values only. Formulas and formatting will not be retained in this file. Continue?'): return False
        try:
            write_sheet(self.sheet,path)
            self.path,self.dirty=str(path),False
            self.remember_file(path)
            self.title(str(path)+' — Quick-Sheet')
            return True
        except Exception as error:
            self.dialogs.showerror('Could not save sheet',str(error)); return False

    def export(self):
        self.finish_edit()
        path=self.dialogs.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV (values only)','*.csv')])
        if path:
            try:
                with open(path,'w',encoding='utf-8-sig',newline='') as stream: stream.write(self.sheet.csv_text())
            except Exception as error: self.dialogs.showerror('Could not export CSV',str(error))

    def close(self):
        if self.focus_get()==self.formula: self.formula_commit()
        self.finish_edit()
        try: self.persist_session()
        except Exception as error:
            self.dialogs.showerror('Could not remember session',f'Your window will stay open so your work is retained.\n\n{error}')
            return
        self.destroy()


if __name__=='__main__':
    App().mainloop()

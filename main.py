"""Quick-Sheet — launch with python main.py."""
import csv
import json
import io
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
from sheet import Sheet, address, coordinates
import re


class App(tk.Tk):
    W, H, GUTTER = 125, 28, 52
    HEADER_BG = '#dce4ed'
    DROPDOWN_WIDTH = 24

    def __init__(self, state_path=None):
        super().__init__(className='QuickSheet')
        icon_path=Path(__file__).resolve().parent/'assets'/'Quick-Sheet.png'
        if icon_path.exists():
            self.app_icon=tk.PhotoImage(file=str(icon_path))
            self.iconphoto(True,self.app_icon)
        self.geometry('1100x720')
        self.minsize(650, 400)
        self.sheet = Sheet()
        self.path = None
        self.dirty = False
        self.active = (0, 0)
        self.anchor = (0, 0)
        self.top = self.left = 0
        self.editor = None
        self.undo_stack = []
        self.redo_stack = []
        self.state_path = Path(state_path) if state_path else Path(__file__).resolve().parent / '.mini-session.json'
        self.internal_clipboard = None
        self.search_text = ''
        self.table_var = tk.BooleanVar()
        formatting = ttk.Frame(self, padding=(10, 2, 10, 8))
        formatting.pack(fill='x')
        ttk.Label(formatting, text='Cell format').pack(side='left')
        self.fmt = ttk.Combobox(formatting, values=['General', 'Text', 'Decimal', 'Currency'], state='readonly', width=12)
        self.fmt.set('General')
        self.fmt.pack(side='left', padx=6)
        self.fmt.bind('<<ComboboxSelected>>', lambda e: self.format_cells())
        ttk.Label(formatting, text='Decimals').pack(side='left')
        self.dec = tk.IntVar(value=2)
        ttk.Spinbox(formatting, from_=0, to=10, textvariable=self.dec, width=3, command=self.format_cells).pack(side='left', padx=6)
        ttk.Button(formatting, text='Σ Sum below selection', command=self.sum_below).pack(side='left', padx=10)
        ttk.Button(formatting, text='Clear filters', command=self.clear_filters).pack(side='right')
        formula = ttk.Frame(self, padding=(10, 0, 10, 8))
        formula.pack(fill='x')
        self.cell_label = ttk.Label(formula, width=8)
        self.cell_label.pack(side='left')
        self.formula = ttk.Entry(formula)
        self.formula.pack(side='left', fill='x', expand=True)
        self.formula.bind('<Return>', self.formula_commit)
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
        self.restore_session()

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
                      ('Paste', lambda: self.clipboard_action('paste'), 'Ctrl+V')]),
            ('Search', [('Find…', self.search_dialog, 'Ctrl+F'), ('Find next', self.find_next, 'F3'),
                        ('Find and Replace…', lambda: self.search_dialog(True), 'Ctrl+H')]),
            ('Data', [('Import CSV…', self.import_csv, ''), ('Export CSV…', self.export, ''), None,
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
        if getattr(e, 'num', None) == 3:
            pos = self.hit(e)
            if pos:
                a,b,d,f = self.bounds()
                if not (a <= pos[0] <= d and b <= pos[1] <= f): self.select(*pos)
            x,y = e.x_root,e.y_root
        else:
            x,y = self.canvas.winfo_rootx()+self.GUTTER, self.canvas.winfo_rooty()+self.H
        self.canvas.focus_set()
        menu = tk.Menu(self, tearoff=False)
        for label, command, shortcut in [('Cut',self.cut,'Ctrl+X'), ('Copy',self.copy,'Ctrl+C'), ('Paste',self.paste,'Ctrl+V')]:
            menu.add_command(label=label, command=command, accelerator=shortcut)
        try: menu.tk_popup(x,y)
        finally: menu.grab_release()
        return 'break'

    def checkpoint(self):
        self.undo_stack.append(json.dumps(self.sheet.dump()))
        self.undo_stack = self.undo_stack[-100:]
        self.redo_stack.clear()

    def changed(self):
        self.dirty = True
        self.title(('• ' if self.dirty else '') + (self.path or 'Untitled') + ' — Quick-Sheet')
        self.draw()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(json.dumps(self.sheet.dump()))
            self.sheet = Sheet.from_data(json.loads(self.undo_stack.pop()))
            self.table_var.set(self.sheet.table)
            self.apply_fonts()
            self.changed()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(json.dumps(self.sheet.dump()))
            self.sheet = Sheet.from_data(json.loads(self.redo_stack.pop()))
            self.table_var.set(self.sheet.table)
            self.apply_fonts()
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

    def draw(self):
        if not hasattr(self, 'canvas'): return
        cv = self.canvas
        cv.delete('all')
        width, height = cv.winfo_width(), cv.winfo_height()
        self.visible_rows = self.rows()[:max(1,height//self.H)]
        r1,c1,r2,c2 = self.bounds()
        for j in range(max(1,(width-self.GUTTER)//self.W+1)):
            c = self.left+j
            x = self.GUTTER+j*self.W
            cv.create_rectangle(x,0,x+self.W,self.H,fill=self.HEADER_BG,outline='#ccd5df')
            cv.create_text(x+8,self.H/2,text=address(0,c)[:-1],anchor='w',font=self.menu_font)
            for i,r in enumerate(self.visible_rows):
                y = (i+1)*self.H
                selected = r1<=r<=r2 and c1<=c<=c2
                fill = '#deebff' if selected else ('#eef3f8' if self.sheet.table and r==0 else 'white')
                cv.create_rectangle(x,y,x+self.W,y+self.H,fill=fill,outline='#e1e6ec')
                text = self.sheet.display(r,c)
                frozen_header = self.sheet.table and r==0
                if frozen_header: text = text or address(0,c)[:-1]
                # Clip text per cell so long values cannot cover neighbors.
                text_width = self.W-14-(self.DROPDOWN_WIDTH if frozen_header else 0)
                while self.cell_font.measure(text)>text_width and len(text)>1: text=text[:-2]+'…'
                cv.create_text(x+7,y+self.H/2,text=text,anchor='w',font=self.cell_font,fill='#192c3b')
                if frozen_header:
                    arrow_x=x+self.W-self.DROPDOWN_WIDTH/2
                    arrow_y=y+self.H/2
                    cv.create_line(x+self.W-self.DROPDOWN_WIDTH,y+5,
                                   x+self.W-self.DROPDOWN_WIDTH,y+self.H-5,fill='#ccd5df')
                    cv.create_polygon(arrow_x-4,arrow_y-2,arrow_x+4,arrow_y-2,
                                      arrow_x,arrow_y+3,fill='#192c3b',
                                      tags=('header_dropdown',f'dropdown_{c}'))
                if (r,c)==self.active:
                    cv.create_rectangle(x+1,y+1,x+self.W-1,y+self.H-1,outline='#2563eb',width=2)
        cv.create_rectangle(0,0,self.GUTTER,self.H,fill=self.HEADER_BG,outline='#ccd5df')
        for i,r in enumerate(self.visible_rows):
            y=(i+1)*self.H
            cv.create_rectangle(0,y,self.GUTTER,y+self.H,fill=self.HEADER_BG,outline='#ccd5df')
            cv.create_text(self.GUTTER-8,y+self.H/2,text=str(r+1),anchor='e',font=self.menu_font)
        nums=[]
        if (r2-r1+1)*(c2-c1+1)<=100000:
            for r in range(r1,r2+1):
                for c in range(c1,c2+1):
                    try:
                        val=self.sheet.value(r,c)
                        if isinstance(val,(int,float)): nums.append(val)
                    except Exception: pass
        self.status.config(text=f'{address(r1,c1)}:{address(r2,c2)}    |    Numbers: {len(nums)}    Sum: {sum(nums):g}    |    Enter to edit · Shift + arrows to select · Ctrl+C / Ctrl+V')
        self.vscroll.set(self.top/max(200,self.sheet.extent()[0]+50), min(1,(self.top+len(self.visible_rows))/max(200,self.sheet.extent()[0]+50)))
        self.hscroll.set(self.left/100, min(1,(self.left+max(1,width//self.W))/100))

    def select(self,r,c,extend=False):
        self.active=(max(0,r),max(0,c))
        if not extend: self.anchor=self.active
        self.cell_label.config(text=address(*self.active))
        self.formula.delete(0,'end')
        self.formula.insert(0,self.sheet.raw(*self.active))
        self.fmt.set(self.sheet.styles.get(address(*self.active),{}).get('format','General'))
        self.draw()

    def hit(self,e):
        i=e.y//self.H-1
        if i<0 or i>=len(self.visible_rows) or e.x<self.GUTTER: return None
        return self.visible_rows[i], self.left+(e.x-self.GUTTER)//self.W

    def click(self,e):
        self.finish_edit()
        self.canvas.focus_set()
        if e.y < self.H and e.x >= self.GUTTER:
            col = self.left + (e.x-self.GUTTER)//self.W
            self.select(0,col)
            self.select(max(199,self.sheet.extent()[0]-1),col,extend=True)
            return
        pos=self.hit(e)
        if pos:
            self.select(*pos,extend=bool(e.state&1))
            if self.sheet.table and pos[0]==0 and (e.x-self.GUTTER)%self.W>=self.W-self.DROPDOWN_WIDTH:
                self.filter_menu(pos[1],e)

    def drag(self,e):
        pos=self.hit(e)
        if pos: self.select(*pos,extend=True)

    def double_click(self,e):
        pos=self.hit(e)
        if pos and self.sheet.table and pos[0]==0 and (e.x-self.GUTTER)%self.W>=self.W-self.DROPDOWN_WIDTH:
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
            if c>=self.left+max(1,(self.canvas.winfo_width()-self.GUTTER)//self.W): self.left+=1
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
        x=self.GUTTER+(c-self.left)*self.W
        y=(self.visible_rows.index(r)+1)*self.H
        self.editor=ttk.Entry(self.canvas,font=self.cell_font)
        self.editor.place(x=x+1,y=y+1,width=self.W-2,height=self.H-2)
        self.editor.insert(0,self.sheet.raw(r,c) if initial is None else initial)
        if initial is None: self.editor.select_range(0,'end')
        self.editor.focus_set()
        self.editor.bind('<Return>',lambda e:self.finish_edit(move=True))
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
        try: decimals=max(0,min(10,int(self.dec.get())))
        except (ValueError,tk.TclError): return
        self.checkpoint()
        a,b,d,f=self.bounds()
        for r in range(a,d+1):
            for c in range(b,f+1): self.sheet.styles[address(r,c)]={'format':self.fmt.get(),'decimals':decimals}
        self.changed()

    def sum_below(self):
        self.finish_edit()
        a,b,d,f=self.bounds()
        if any(self.sheet.raw(d+1,c) for c in range(b,f+1)):
            messagebox.showinfo('Sum','The row below your selection contains data. Choose a range with an empty row below it.')
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
        self.sheet.filters.clear()
        self.top=0
        self.draw()

    def filter_menu(self,col,e):
        menu=tk.Menu(self,tearoff=False)
        menu.add_command(label='Sort A–Z',command=lambda:self.sort_column(col))
        menu.add_command(label='Sort Z–A',command=lambda:self.sort_column(col,True))
        menu.add_command(label='Sort numbers ascending',command=lambda:self.sort_column(col,numeric=True))
        menu.add_command(label='Sort numbers descending',command=lambda:self.sort_column(col,True,True))
        menu.add_separator()
        def choose(value):
            if value is None: self.sheet.filters.pop(str(col),None)
            else: self.sheet.filters[str(col)]=value
            self.top=0
            self.draw()
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
        self.internal_clipboard=(out.getvalue(),values,styles)
        return 'break'

    def cut(self,e=None):
        self.copy()
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
        if self.internal_clipboard and self.internal_clipboard[0]==text:
            _,values,styles=self.internal_clipboard
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
                self.sheet.set(r+i,c+j,row[j%width] if j%width<len(row) else '')
                if styles is not None:
                    key=address(r+i,c+j)
                    self.sheet.styles.pop(key,None)
                    if styles[i%height][j%width]: self.sheet.styles[key]=styles[i%height][j%width].copy()
        self.changed()
        self.select(r,c)
        self.select(r+out_h-1,c+out_w-1,extend=True)
        return 'break'

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
        win=self.search_window=tk.Toplevel(self)
        win.title('Find and Replace' if replace else 'Find')
        win.transient(self)
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
               'undo':self.undo_stack,'redo':self.redo_stack,'search':self.search_text}
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
            if state.get('geometry'): self.geometry(state['geometry'])
            if state.get('maximized'):
                try: self.state('zoomed')
                except tk.TclError: self.attributes('-zoomed',True)
            self.title(('• ' if self.dirty else '')+(self.path or 'Untitled')+' — Quick-Sheet')
            self.draw()
        except Exception as error:
            self.after_idle(lambda text=str(error):messagebox.showerror('Could not restore previous session',text))

    def fonts(self):
        self.finish_edit()
        win=tk.Toplevel(self)
        win.withdraw()
        win.title('Fonts')
        win.transient(self)
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
        self.update_idletasks()
        width,height=original_size
        x=self.winfo_rootx()+(self.winfo_width()-width)//2
        y=self.winfo_rooty()+(self.winfo_height()-height)//2
        win.geometry(f'{width}x{height}+{x}+{y}')
        win.deiconify()

    def may_discard(self):
        self.finish_edit()
        if not self.dirty: return True
        answer=messagebox.askyesnocancel('Unsaved sheet','Save your changes first?')
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

    def open(self):
        if not self.may_discard(): return
        path=filedialog.askopenfilename(filetypes=[('Sheets and CSV','*.mini *.csv'),('All files','*.*')])
        if not path: return
        try:
            with open(path,encoding='utf-8-sig',newline='') as stream:
                if path.lower().endswith('.csv'):
                    sheet=Sheet()
                    for r,row in enumerate(csv.reader(stream)):
                        for c,value in enumerate(row): sheet.set(r,c,value)
                    path=None
                else: sheet=Sheet.from_data(json.load(stream))
            self.load(sheet,path)
        except Exception as error: messagebox.showerror('Could not open sheet',str(error))

    def import_csv(self):
        if not self.may_discard(): return
        path=filedialog.askopenfilename(filetypes=[('CSV','*.csv'),('All files','*.*')])
        if not path: return
        try:
            sheet=Sheet()
            with open(path,encoding='utf-8-sig',newline='') as stream:
                for r,row in enumerate(csv.reader(stream,delimiter=',')):
                    for c,value in enumerate(row): sheet.set(r,c,value)
            self.load(sheet,None)
            self.changed()
        except Exception as error: messagebox.showerror('Could not import CSV',str(error))

    def save(self,save_as=False):
        self.finish_edit()
        path=self.path if not save_as else None
        if not path: path=filedialog.asksaveasfilename(defaultextension='.mini',filetypes=[('Quick-Sheet','*.mini')])
        if not path: return False
        try:
            from pathlib import Path
            target=Path(path)
            temp=target.with_suffix(target.suffix+'.tmp')
            temp.write_text(json.dumps(self.sheet.dump(),indent=2),encoding='utf-8')
            temp.replace(target)
            self.path,self.dirty=path,False
            self.title(path+' — Quick-Sheet')
            return True
        except Exception as error:
            messagebox.showerror('Could not save sheet',str(error))
            return False

    def export(self):
        self.finish_edit()
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV (values only)','*.csv')])
        if path:
            try:
                with open(path,'w',encoding='utf-8-sig',newline='') as stream: stream.write(self.sheet.csv_text())
            except Exception as error: messagebox.showerror('Could not export CSV',str(error))

    def close(self):
        if self.focus_get()==self.formula: self.formula_commit()
        self.finish_edit()
        try: self.persist_session()
        except Exception as error:
            messagebox.showerror('Could not remember session',f'Your window will stay open so your work is retained.\n\n{error}')
            return
        self.destroy()


if __name__=='__main__':
    App().mainloop()

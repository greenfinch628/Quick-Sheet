"""Small, scrollable context menus contained in the main Tk window."""
import tkinter as tk
from tkinter import ttk


class ContextMenu(tk.Frame):
    """Keep focus on the owner so clipboard commands retain entry selections."""

    def __init__(self, app):
        super().__init__(app, borderwidth=1, relief='solid', background='white')
        self.entries = []
        self.rows = []
        self.active = None
        self.viewport = tk.Canvas(self, background='white', highlightthickness=0)
        self.viewport.pack(side='left', fill='both', expand=True)
        self.scrollbar = ttk.Scrollbar(self, command=self.viewport.yview)
        self.viewport.configure(yscrollcommand=self.scrollbar.set)
        self.items = tk.Frame(self.viewport, background='white')
        self.window = self.viewport.create_window(0, 0, window=self.items, anchor='nw')
        self._bind_wheel(self.viewport)
        self._bind_wheel(self.items)

    def _bind_wheel(self, widget):
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            widget.bind(sequence, self._wheel)

    def _wheel(self, event):
        if event.num in (4, 5):
            amount = -1 if event.num == 4 else 1
        else:
            amount = -int(event.delta / 120)
        self.viewport.yview_scroll(amount, 'units')
        return 'break'

    def add_command(self, label, command, accelerator=''):
        index = len(self.entries)
        row = tk.Frame(self.items, background='white')
        row.pack(fill='x')
        title = tk.Label(row, text=label, anchor='w', background='white', foreground='#192c3b',
                         font=self.master.menu_font, padx=10, pady=5)
        title.pack(side='left', fill='x', expand=True)
        shortcut = tk.Label(row, text=accelerator, anchor='e', background='white', foreground='#526575',
                            font=self.master.menu_font, padx=10, pady=5)
        shortcut.pack(side='right')
        for widget in (row, title, shortcut):
            # Motion avoids changing keyboard selection when scrolling under a stationary pointer.
            widget.bind('<Motion>', lambda e, i=index: self.highlight(i))
            widget.bind('<ButtonRelease-1>', lambda e, i=index: self.invoke(i))
            self._bind_wheel(widget)
        self.entries.append((label, command))
        self.rows.append(row)

    def add_separator(self):
        row = ttk.Separator(self.items)
        row.pack(fill='x', pady=3)
        self.entries.append(('', None))
        self.rows.append(row)

    def entrycget(self, index, option):
        if option != 'label':
            raise ValueError(option)
        return self.entries[index][0]

    def highlight(self, index):
        if self.active == index:
            return
        for i in (self.active, index):
            if i is not None and self.entries[i][1] is not None:
                row = self.rows[i]
                color = '#dce4ed' if i == index else 'white'
                row.configure(background=color)
                for label in row.winfo_children():
                    label.configure(background=color)
        self.active = index

    def handle_key(self, event):
        if not self.winfo_ismapped():
            return
        if event.keysym in ('Escape', 'Tab'):
            self.hide()
            return 'break' if event.keysym == 'Escape' else None
        if event.keysym in ('Up', 'Down', 'Home', 'End'):
            choices = [i for i, (_, command) in enumerate(self.entries) if command is not None]
            if choices:
                if event.keysym in ('Home', 'End'):
                    index = choices[0 if event.keysym == 'Home' else -1]
                elif self.active not in choices:
                    index = choices[0 if event.keysym == 'Down' else -1]
                else:
                    index = choices[(choices.index(self.active) + (1 if event.keysym == 'Down' else -1)) % len(choices)]
                self.highlight(index)
                row = self.rows[index]
                top, bottom = self.viewport.yview()
                total = self.items.winfo_reqheight()
                if row.winfo_y() < top * total:
                    self.viewport.yview_moveto(row.winfo_y() / total)
                elif row.winfo_y() + row.winfo_height() > bottom * total:
                    self.viewport.yview_moveto((row.winfo_y() + row.winfo_height() - self.viewport.winfo_height()) / total)
            return 'break'
        if event.keysym in ('Return', 'KP_Enter', 'space'):
            if self.active is not None:
                self.invoke(self.active)
            return 'break'
        self.hide()

    def invoke(self, index):
        command = self.entries[index][1]
        self.hide()
        if command is not None:
            command()

    def show(self, x, y):
        self.update_idletasks()
        available_width = max(1, self.master.winfo_width() - 2)
        height = min(self.items.winfo_reqheight(), max(1, self.master.winfo_height() - 20))
        scroll_width = 0
        if self.items.winfo_reqheight() > height:
            self.scrollbar.pack(side='right', fill='y')
            scroll_width = self.scrollbar.winfo_reqwidth()
        width = min(self.items.winfo_reqwidth(), max(1, available_width - scroll_width))
        self.viewport.configure(width=width, height=height,
                                scrollregion=(0, 0, width, self.items.winfo_reqheight()))
        self.viewport.itemconfigure(self.window, width=width)
        self.update_idletasks()
        x = max(0, min(x - self.master.winfo_rootx(), self.master.winfo_width() - self.winfo_reqwidth()))
        y = max(0, min(y - self.master.winfo_rooty(), self.master.winfo_height() - self.winfo_reqheight()))
        self.place(x=x, y=y)
        self.lift()

    def hide(self):
        self.place_forget()

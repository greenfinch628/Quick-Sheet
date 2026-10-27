"""Selection-border moves, with previews and bounded edge scrolling."""
import json
from sheet import address


class SelectionDrag:
    MARGIN = 24

    def __init__(self, app):
        self.app = app
        self.state = None
        self.timer = None

    def border_hit(self, event):
        a = self.app
        if event.x < a.GUTTER or event.y < a.H:
            return False
        return any('selection_border' in a.canvas.gettags(item) for item in
                   a.canvas.find_overlapping(event.x-4, event.y-4, event.x+4, event.y+4))

    def press(self, event):
        if event.state & 1 or not self.border_hit(event):
            return False
        a = self.app
        origin = a.hit(event)
        if origin is None:
            return False
        self.state = dict(source=a.bounds(), axis=a._header_axis, origin=origin,
                          press=(event.x, event.y), pointer=(event.x, event.y),
                          target=None, moving=False)
        a.canvas.configure(cursor='fleur')
        return True

    def motion(self, event):
        if self.state is None:
            return False
        s = self.state
        s['pointer'] = event.x, event.y
        if not s['moving']:
            x, y = s['press']
            if max(abs(event.x-x), abs(event.y-y)) < 5:
                return True
            s['moving'] = True
        self.update_target()
        self.app.draw()
        if self.timer is None:
            self.timer = self.app.after(120, self.scroll)
        return True

    def update_target(self):
        a, s = self.app, self.state
        x, y = s['pointer']
        # The last visible cell remains the target while scrolling near an edge.
        x = max(a.GUTTER+1, min(x, a.canvas.winfo_width()-2))
        y = max(a.H+1, min(y, a.canvas.winfo_height()-2))
        row = a.row_at(y)
        if row is None:
            row = a.visible_rows[-1] if a.visible_rows else None
        if row is None:
            s['target'] = None
            return
        col = a.column_at(x)
        if s['axis'] == 0:
            _, top, _, height = a.cell_rect(row, col)
            s['target'] = row + (y >= top+height/2)
        elif s['axis'] == 1:
            left, _, width, _ = a.cell_rect(row, col)
            s['target'] = col + (x >= left+width/2)
        else:
            first_row, first_col, _, _ = s['source']
            origin_row, origin_col = s['origin']
            s['target'] = (max(0, row-origin_row+first_row),
                           max(0, col-origin_col+first_col))

    def scroll(self):
        self.timer = None
        if self.state is None or not self.state['moving']:
            return
        a, s = self.app, self.state
        x, y = s['pointer']
        dx = (1 if x > a.canvas.winfo_width()-self.MARGIN else
              -1 if x < a.GUTTER+self.MARGIN else 0)
        dy = (1 if y > a.canvas.winfo_height()-self.MARGIN else
              -1 if y < a.H+self.MARGIN else 0)
        if s['axis'] == 0: dx = 0
        if s['axis'] == 1: dy = 0
        if dy: a.scroll_y('scroll', dy, 'units')
        if dx: a.scroll_x('scroll', dx, 'units')
        if dx or dy:
            self.update_target()
            a.draw()
        self.timer = a.after(120, self.scroll)

    def cancel(self, event=None):
        if self.timer is not None:
            self.app.after_cancel(self.timer)
            self.timer = None
        had_state = self.state is not None
        self.state = None
        self.app.canvas.configure(cursor='')
        self.app.canvas.delete('move_preview')
        if had_state:
            self.app.draw()
        return 'break'

    def release(self, event):
        if self.state is None:
            return False
        a, s = self.app, self.state
        if s['moving']:
            s['pointer'] = event.x, event.y
            self.update_target()
        self.cancel()
        if not s['moving'] or s['target'] is None:
            return True
        if not (0 <= event.x < a.canvas.winfo_width() and 0 <= event.y < a.canvas.winfo_height()):
            return True
        if s['axis'] is None and (event.x < a.GUTTER or event.y < a.H):
            return True
        first_row, first_col, last_row, last_col = s['source']
        axis, target = s['axis'], s['target']
        if axis is None:
            if target == (first_row, first_col):
                return True
            if a.sheet.block_move_conflicts(s['source'], target):
                if not a.dialogs.askyesno('Move cells',
                        'The destination contains data or formatting. Replace it with the selected cells?'):
                    return True
        else:
            start, end = (first_row, last_row) if axis == 0 else (first_col, last_col)
            if start <= target <= end+1:
                return True
        before = json.dumps(a.sheet.dump())
        if axis is None:
            if not a.sheet.move_block(s['source'], target):
                return True
            row, col = target
            a.select(row, col)
            a.select(row+last_row-first_row, col+last_col-first_col, True)
        else:
            destination = a.sheet.move_axis(axis, start, end-start+1, target)
            a.select_header(axis, destination, preserve=False)
            if end > start:
                a.select_header(axis, destination+end-start, extend=True, preserve=False)
        a.undo_stack.append(before)
        a.undo_stack = a.undo_stack[-100:]
        a.redo_stack.clear()
        a.changed()
        return True

    def column_edge(self, col):
        a = self.app
        if col >= a.left:
            return a.GUTTER+sum(a.column_width(c) for c in range(a.left, col))
        return a.GUTTER-sum(a.column_width(c) for c in range(col, a.left))

    def outline(self, bounds, tag, color, dash=None):
        a = self.app
        first_row, first_col, last_row, last_col = bounds
        rows = [r for r in a.visible_rows if first_row <= r <= last_row]
        if not rows:
            return
        width, height = a.canvas.winfo_width(), a.canvas.winfo_height()
        x1, x2 = self.column_edge(first_col), self.column_edge(last_col+1)
        if x2 < a.GUTTER or x1 >= width:
            return
        y1 = a.cell_rect(rows[0], a.left)[1]
        _, bottom, _, row_height = a.cell_rect(rows[-1], a.left)
        y2 = min(height-1, bottom+row_height)
        left, right = max(a.GUTTER+1, x1+1), min(width-1, x2-1)
        options = dict(fill=color, width=2, tags=tag)
        if dash: options['dash'] = dash
        if first_row in rows:
            a.canvas.create_line(left, y1+1, right, y1+1, **options)
        if last_row in rows and bottom+row_height < height:
            a.canvas.create_line(left, y2-1, right, y2-1, **options)
        if x1 >= a.GUTTER:
            a.canvas.create_line(left, y1+1, left, y2-1, **options)
        if x2 <= width:
            a.canvas.create_line(right, y1+1, right, y2-1, **options)

    def draw(self):
        a = self.app
        self.outline(a.bounds(), 'selection_border', '#2563eb')
        s = self.state
        if s is None or not s['moving'] or s['target'] is None:
            return
        first_row, first_col, last_row, last_col = s['source']
        target = s['target']
        if s['axis'] is None:
            row, col = target
            end_row, end_col = row+last_row-first_row, col+last_col-first_col
            self.outline((row, col, end_row, end_col), 'move_preview', '#15803d', (5, 3))
            label = f'Move to {address(row,col)}:{address(end_row,end_col)}'
        elif s['axis'] == 0:
            if target in a.visible_rows:
                y = a.cell_rect(target, a.left)[1]
            elif a.visible_rows and target == a.visible_rows[-1]+1:
                _, top, _, height = a.cell_rect(a.visible_rows[-1], a.left)
                y = top+height
            else:
                y = a.H
            y = max(a.H+1, min(y, a.canvas.winfo_height()-2))
            a.canvas.create_line(a.GUTTER, y, a.canvas.winfo_width(), y,
                                 fill='#15803d', width=3, tags='move_preview')
            label = f'Insert selected rows before row {target+1}'
        else:
            x = max(a.GUTTER+1, min(self.column_edge(target), a.canvas.winfo_width()-2))
            a.canvas.create_line(x, a.H, x, a.canvas.winfo_height(),
                                 fill='#15803d', width=3, tags='move_preview')
            label = f'Insert selected columns before {address(0,target)[:-1]}'
        a.status.configure(text=label+' · Release to move · Escape to cancel')

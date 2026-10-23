"""Small, dependency-free spreadsheet data model."""
import csv
import io
import re


def address(row, col):
    name = ''
    col += 1
    while col:
        col, rem = divmod(col - 1, 26)
        name = chr(65 + rem) + name
    return f'{name}{row + 1}'


def coordinates(ref):
    match = re.fullmatch(r'([A-Z]+)([1-9][0-9]*)', ref.upper())
    if not match:
        raise ValueError('Invalid cell reference')
    col = 0
    for letter in match[1]:
        col = col * 26 + ord(letter) - 64
    return int(match[2]) - 1, col - 1


class Sheet:
    def __init__(self):
        self.cells = {}
        self.styles = {}
        self.table = False
        self.filters = {}
        self.row_heights = {}
        self.col_widths = {}
        self.column_decimals = {}
        self.ui_font = 'CaskaydiaCove NFM'
        self.ui_size = 10
        self.cell_font = 'Arial'
        self.cell_size = 11

    def raw(self, row, col):
        return self.cells.get(address(row, col), '')

    def set(self, row, col, value):
        key = address(row, col)
        if str(value):
            self.cells[key] = str(value)
        else:
            self.cells.pop(key, None)
        if col==0:
            self.refresh_autosums(changed_row=row)
        elif col==1 and row in (0,1) and self.autosum_bounds(row,col) is not None:
            self.refresh_autosums()

    def autosum_bounds(self,row,col):
        """Only B1/A1 or B2/A2 are valid anchors for the custom total."""
        if col!=1 or row not in (0,1): return None
        match=re.fullmatch(r'=\s*AUTOSUM\(\s*(?:A([12])\s*:\s*A([1-9][0-9]*))?\s*\)',self.raw(row,col),re.IGNORECASE)
        if not match: return None
        start=int(match[1])-1 if match[1] else row
        end=int(match[2])-1 if match[2] else start
        if start!=row or end<start: return None
        return start,end

    def refresh_autosums(self,changed_row=None):
        """Extend on entry; rescan sparse column A only when a tail is removed."""
        last=None
        for row in (0,1):
            bounds=self.autosum_bounds(row,1)
            if bounds is None: continue
            start,end=bounds
            if changed_row is not None and changed_row<start: continue
            if changed_row is not None and self.raw(changed_row,0)!='':
                end=max(end,changed_row)
            elif changed_row is None or changed_row>=end:
                if last is None:
                    last=max((int(key[1:])-1 for key,value in self.cells.items()
                              if value!='' and re.fullmatch(r'A[1-9][0-9]*',key)),default=-1)
                end=max(start,last)
            self.cells[address(row,1)]=f'=AUTOSUM(A{start+1}:A{end+1})'

    def start_autosum(self):
        row=1 if self.table else 0
        other=1-row
        if self.autosum_bounds(other,1) is not None: self.cells.pop(address(other,1),None)
        self.set(row,1,f'=AUTOSUM(A{row+1}:A{row+1})')
        return row

    def value(self, row, col, seen=None):
        key = address(row, col)
        seen = set() if seen is None else set(seen)
        if key in seen:
            raise ValueError('Circular reference')
        seen.add(key)
        raw = self.raw(row, col)
        if self.styles.get(key,{}).get('format') in ('Date','Date/time') and not raw.startswith('='):
            from datetime import datetime
            try: return (datetime.fromisoformat(raw)-datetime(1899,12,30)).total_seconds()/86400
            except ValueError: pass
        if self.styles.get(key, {}).get('format') == 'Text':
            return raw
        if not raw.startswith('='):
            try:
                return float(raw.replace(',', '')) if raw else ''
            except ValueError:
                return raw
        if re.search(r'\bAUTOSUM\s*\(',raw,re.IGNORECASE) and self.autosum_bounds(row,col) is None:
            raise ValueError('AUTOSUM is only available in B1 using A1 or B2 using A2')
        from formulas import evaluate
        return evaluate(raw, lambda r,c: self.value(r,c,seen))

    def structural_edit(self, axis, index, count=1, delete=False):
        """Move sparse cells and update references, including absolute references."""
        from formulas import map_refs
        if axis not in (0,1) or index<0 or count<1: raise ValueError('Invalid insertion')
        def shift(point):
            result=list(point)
            v=result[axis]
            if delete and index<=v<index+count: return None
            if v>=index: result[axis] += -count if delete else count
            return result
        def ref_move(ref):
            point=shift(coordinates(ref.replace('$','')))
            if point is None: return '#REF!'
            letters,digits=re.fullmatch(r'([A-Z]+)([0-9]+)',address(*point)).groups()
            col,row=re.fullmatch(r'([$]?[A-Za-z]+)([$]?[0-9]+)',ref).groups()
            return ('$' if col.startswith('$') else '')+letters+('$' if row.startswith('$') else '')+digits
        def range_move(first,last):
            if not delete: return ref_move(first)+':'+ref_move(last)
            points=[list(coordinates(ref.replace('$',''))) for ref in (first,last)]
            low,high=sorted(point[axis] for point in points)
            end=index+count
            low_new=low if low<index else low-count if low>=end else index
            high_new=high-count if high>=end else high if high<index else index-1
            if low_new>high_new: return '#REF!'
            refs=[]
            for ref,point in zip((first,last),points):
                point[axis]=low_new if point[axis]==low else high_new
                letters,digits=re.fullmatch(r'([A-Z]+)([0-9]+)',address(*point)).groups()
                col,row=re.fullmatch(r'([$]?[A-Za-z]+)([$]?[0-9]+)',ref).groups()
                refs.append(('$' if col.startswith('$') else '')+letters+('$' if row.startswith('$') else '')+digits)
            return ':'.join(refs)
        for attr in ('cells','styles'):
            result={}
            for key,value in getattr(self,attr).items():
                point=shift(coordinates(key))
                if point is not None:
                    result[address(*point)] = map_refs(value,ref_move,range_move) if attr=='cells' else value.copy()
            setattr(self,attr,result)
        dimensions=self.row_heights if axis==0 else self.col_widths
        updated={}
        for key,value in dimensions.items():
            point=[0,0]; point[axis]=int(key)
            moved=shift(point)
            if moved is not None: updated[str(moved[axis])]=value
        dimensions.clear(); dimensions.update(updated)
        if axis==1:
            filters={}
            for key,value in self.filters.items():
                point=shift((0,int(key)))
                if point is not None: filters[str(point[1])]=value
            self.filters=filters
            precision={}
            for key,value in self.column_decimals.items():
                point=shift((0,int(key)))
                if point is not None: precision[str(point[1])]=value
            self.column_decimals=precision

    def style(self,row,col):
        style=self.styles.get(address(row,col),{}).copy()
        if str(col) in self.column_decimals: style['decimals']=self.column_decimals[str(col)]
        return style

    def display(self, row, col):
        try:
            value = self.value(row, col)
            if isinstance(value,bool): return 'TRUE' if value else 'FALSE'
            if isinstance(value, (int, float)):
                style = self.style(row,col)
                fmt = style.get('format', 'General')
                decimals = style.get('decimals', 0)
                if fmt == 'Percentage': return f'{value*100:.{decimals}f}%'
                if fmt in ('Date','Date/time'):
                    from datetime import datetime, timedelta
                    stamp=datetime(1899,12,30)+timedelta(days=value)
                    return stamp.strftime('%Y-%m-%d %H:%M:%S' if fmt=='Date/time' else '%Y-%m-%d')
                if fmt == 'Currency': return f'${value:,.{decimals}f}'
                if fmt == 'Decimal': return f'{value:,.{decimals}f}'
                return f'{value:.{decimals}f}'
            if isinstance(value,bool): return 'TRUE' if value else 'FALSE'
            return str(value)
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError, TypeError, ArithmeticError):
            return '#ERROR'

    def extent(self):
        points = [coordinates(key) for key in self.cells]
        return (max((r for r,c in points), default=0)+1,
                max((c for r,c in points), default=0)+1)

    def dump(self):
        return {key: getattr(self, key) for key in ('cells', 'styles', 'table', 'filters', 'ui_font', 'ui_size', 'cell_font', 'cell_size', 'row_heights', 'col_widths', 'column_decimals')}

    def sort_rows(self, col, descending=False, numeric=False):
        """Sort whole data rows, preserving the header and cell formatting.

        Numeric sorting falls back to text for the entire column when any
        nonblank value is text. Blank keys stay at the bottom in either direction.
        Formula references remain literal, as with clipboard operations.
        """
        rows, cols = self.extent()
        values = {}
        for r in range(1, rows):
            try: values[r] = self.value(r, col)
            except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError, TypeError, ArithmeticError):
                values[r] = self.display(r, col)
        filled = [r for r in values if values[r] != '']
        blanks = [r for r in values if values[r] == '']
        numbers = numeric and all(isinstance(values[r], (int, float)) for r in filled)
        order = sorted(filled, key=lambda r: values[r] if numbers else self.display(r,col).casefold(), reverse=descending) + blanks
        old_cells, old_styles = self.cells.copy(), self.styles.copy()
        for dest, source in enumerate(order, 1):
            for c in range(cols):
                target, origin = address(dest,c), address(source,c)
                self.cells.pop(target, None)
                self.styles.pop(target, None)
                if origin in old_cells: self.cells[target] = old_cells[origin]
                if origin in old_styles: self.styles[target] = old_styles[origin].copy()

    @classmethod
    def from_data(cls, data):
        sheet = cls()
        for key in sheet.dump():
            if key in data: setattr(sheet, key, data[key])
        for key in sheet.cells: coordinates(key)
        sheet.refresh_autosums()
        return sheet

    def csv_text(self):
        out = io.StringIO(newline='')
        writer = csv.writer(out)
        rows, cols = self.extent()
        for r in range(rows): writer.writerow([self.display(r,c) for c in range(cols)])
        return out.getvalue()

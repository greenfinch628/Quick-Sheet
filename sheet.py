"""Small, dependency-free spreadsheet data model."""
import ast
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

    def value(self, row, col, seen=None):
        key = address(row, col)
        seen = set() if seen is None else set(seen)
        if key in seen:
            raise ValueError('Circular reference')
        seen.add(key)
        raw = self.raw(row, col)
        if self.styles.get(key, {}).get('format') == 'Text':
            return raw
        if not raw.startswith('='):
            try:
                return float(raw.replace(',', '')) if raw else ''
            except ValueError:
                return raw
        expr = raw[1:].upper()

        def number(ref):
            value = self.value(*coordinates(ref), seen)
            return value if isinstance(value, (int, float)) else 0

        def total(match):
            r1, c1 = coordinates(match[1])
            r2, c2 = coordinates(match[2])
            if (abs(r2-r1)+1)*(abs(c2-c1)+1) > 100000:
                raise ValueError('Range too large')
            return str(sum(number(address(r, c)) for r in range(min(r1,r2), max(r1,r2)+1)
                           for c in range(min(c1,c2), max(c1,c2)+1)))

        expr = re.sub(r'SUM\(\s*([A-Z]+[1-9][0-9]*)\s*:\s*([A-Z]+[1-9][0-9]*)\s*\)', total, expr)
        expr = re.sub(r'\b[A-Z]+[1-9][0-9]*\b', lambda m: str(number(m[0])), expr)
        tree = ast.parse(expr, mode='eval')

        def evaluate(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return node.value
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                return evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
            if isinstance(node, ast.BinOp):
                a, b = evaluate(node.left), evaluate(node.right)
                if isinstance(node.op, ast.Add): return a + b
                if isinstance(node.op, ast.Sub): return a - b
                if isinstance(node.op, ast.Mult): return a * b
                if isinstance(node.op, ast.Div): return a / b
            raise ValueError('Unsupported formula')
        return evaluate(tree.body)

    def display(self, row, col):
        try:
            value = self.value(row, col)
            if isinstance(value, (int, float)):
                style = self.styles.get(address(row, col), {})
                fmt = style.get('format', 'General')
                decimals = style.get('decimals', 2)
                if fmt == 'Currency': return f'${value:,.{decimals}f}'
                if fmt == 'Decimal': return f'{value:,.{decimals}f}'
                return f'{value:g}'
            return str(value)
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError):
            return '#ERROR'

    def extent(self):
        points = [coordinates(key) for key in self.cells]
        return (max((r for r,c in points), default=0)+1,
                max((c for r,c in points), default=0)+1)

    def dump(self):
        return {key: getattr(self, key) for key in ('cells', 'styles', 'table', 'filters', 'ui_font', 'ui_size', 'cell_font', 'cell_size')}

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
            except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError):
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
        return sheet

    def csv_text(self):
        out = io.StringIO(newline='')
        writer = csv.writer(out)
        rows, cols = self.extent()
        for r in range(rows): writer.writerow([self.display(r,c) for c in range(cols)])
        return out.getvalue()

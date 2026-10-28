"""Keep formula references attached to their source cells during drag moves."""
import re
from formulas import map_refs


def intersection(first, second):
    a,b,d,f=first
    r,c,y,x=second
    result=max(a,r),max(b,c),min(d,y),min(f,x)
    return result if result[0]<=result[2] and result[1]<=result[3] else None


def subtract(rectangle, cut):
    overlap=intersection(rectangle,cut)
    if overlap is None: return [rectangle]
    a,b,d,f=rectangle
    r,c,y,x=overlap
    parts=[]
    if a<r: parts.append((a,b,r-1,f))
    if y<d: parts.append((y+1,b,d,f))
    if b<c: parts.append((r,b,y,c-1))
    if x<f: parts.append((r,x+1,y,f))
    return parts


def union_rectangles(rectangles):
    """Remove overlap and join adjacent rectangles without including new cells."""
    result=[]
    for rectangle in sorted(rectangles):
        parts=[rectangle]
        for existing in result:
            parts=[piece for part in parts for piece in subtract(part,existing)]
        result.extend(parts)
    while True:
        for i,first in enumerate(result):
            for j in range(i+1,len(result)):
                second=result[j]
                same_rows=first[0]==second[0] and first[2]==second[2]
                same_cols=first[1]==second[1] and first[3]==second[3]
                adjacent_cols=first[3]+1==second[1] or second[3]+1==first[1]
                adjacent_rows=first[2]+1==second[0] or second[2]+1==first[0]
                if (same_rows and adjacent_cols) or (same_cols and adjacent_rows):
                    result[i]=(min(first[0],second[0]),min(first[1],second[1]),
                               max(first[2],second[2]),max(first[3],second[3]))
                    result.pop(j)
                    break
            else: continue
            break
        else: return sorted(result)


def rewrite_for_move(formula, regions):
    """Apply disjoint source rectangles and their (row, column) displacements.

    Ranges split into reference unions when their original members no longer
    occupy a rectangle. Absolute markers lock copying, but still follow moves.
    """
    if not formula.startswith('=') or not regions: return formula
    from sheet import address, coordinates

    def format_ref(original, point):
        letters,digits=re.fullmatch(r'([A-Z]+)([0-9]+)',address(*point)).groups()
        col_fixed,row_fixed=re.fullmatch(r'(\$?)[A-Za-z]+(\$?)[0-9]+',original).groups()
        return col_fixed+letters+row_fixed+digits

    def ref_move(ref):
        row,col=coordinates(ref.replace('$',''))
        for (a,b,d,f),(dr,dc) in regions:
            if a<=row<=d and b<=col<=f:
                return format_ref(ref,(row+dr,col+dc))
        return ref

    def range_move(first,last):
        row,col=coordinates(first.replace('$',''))
        end_row,end_col=coordinates(last.replace('$',''))
        original=(min(row,end_row),min(col,end_col),max(row,end_row),max(col,end_col))
        pending=[original]
        moved=[]
        for source,(dr,dc) in regions:
            remaining=[]
            for rectangle in pending:
                overlap=intersection(rectangle,source)
                if overlap is not None:
                    a,b,d,f=overlap
                    moved.append((a+dr,b+dc,d+dr,f+dc))
                remaining.extend(subtract(rectangle,source))
            pending=remaining
        rectangles=union_rectangles(pending+moved)
        if rectangles==[original]: return first+':'+last
        pieces=[]
        for a,b,d,f in rectangles:
            start=(d if row>end_row else a, f if col>end_col else b)
            end=(a if row>end_row else d, b if col>end_col else f)
            pieces.append(format_ref(first,start)+':'+format_ref(last,end))
        return pieces[0] if len(pieces)==1 else '('+','.join(pieces)+')'

    return map_refs(formula,ref_move,range_move)

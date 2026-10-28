"""Restricted spreadsheet expressions and reference translation."""
import ast
import re
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

REF = re.compile(r'(?<![A-Za-z0-9_])([$]?[A-Za-z]+[$]?[1-9][0-9]*)(?![A-Za-z0-9_])')
STRING = re.compile(r'("(?:[^"]|"")*")')

def map_refs(formula, transform, range_transform=None):
    if not formula.startswith('='): return formula
    parts = STRING.split(formula)
    for i in range(0, len(parts), 2):
        chunk=parts[i]
        ranges=[]
        if range_transform:
            def capture(m):
                ranges.append(range_transform(m[1],m[2]))
                return f'__RANGE_{len(ranges)-1}__'
            chunk=re.sub(r'([$]?[A-Za-z]+[$]?[1-9][0-9]*)\s*:\s*([$]?[A-Za-z]+[$]?[1-9][0-9]*)',capture,chunk)
        chunk=REF.sub(lambda m: transform(m[0]),chunk)
        for j,value in enumerate(ranges): chunk=chunk.replace(f'__RANGE_{j}__',value)
        parts[i]=chunk
    return ''.join(parts)

def translate(formula, dr, dc):
    from sheet import address, coordinates
    def move(ref):
        col, row = re.fullmatch(r'([$]?[A-Za-z]+)([$]?[0-9]+)', ref).groups()
        r,c = coordinates(ref.replace('$',''))
        r += 0 if row.startswith('$') else dr
        c += 0 if col.startswith('$') else dc
        if min(r,c)<0: return '#REF!'
        name = address(r,c)
        letters, digits = re.fullmatch(r'([A-Z]+)([0-9]+)',name).groups()
        return ('$' if col.startswith('$') else '')+letters+('$' if row.startswith('$') else '')+digits
    return map_refs(formula, move)

def evaluate(formula, lookup):
    from sheet import coordinates
    parts = STRING.split(formula[1:])
    import json
    for i in range(1,len(parts),2): parts[i]=json.dumps(parts[i][1:-1].replace('""','"'))
    for i in range(0,len(parts),2):
        part=parts[i]
        part=re.sub(r'([$]?[A-Za-z]+[$]?[1-9][0-9]*)\s*:\s*([$]?[A-Za-z]+[$]?[1-9][0-9]*)',r'RANGE("\1","\2")',part)
        # Protect the generated range arguments while replacing cell references.
        chunks=STRING.split(part)
        for j in range(0,len(chunks),2):
            chunks[j]=REF.sub(lambda m:'CELL("'+m[0]+'")',chunks[j])
        part=''.join(chunks).replace('^','**').replace('<>','!=')
        part=re.sub(r'(?<![<>=!])=(?!=)','==',part)
        parts[i]=part
    expr=''.join(parts)
    tree=ast.parse(expr,mode='eval')
    if sum(1 for _ in ast.walk(tree))>2000: raise ValueError('Formula too complex')
    def cell(ref): return lookup(*coordinates(ref.replace('$','')))
    def num(v):
        if v=='': return 0
        if isinstance(v,(int,float)): return v
        raise ValueError('Expected number')
    def flatten(values):
        for v in values:
            if isinstance(v,list): yield from flatten(v)
            else: yield v
    def run(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float,str,bool): return n.value
        if isinstance(n,ast.Tuple): return [run(item) for item in n.elts]
        if isinstance(n,ast.Name) and n.id.upper() in ('TRUE','FALSE'): return n.id.upper()=='TRUE'
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
            return num(run(n.operand))*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp):
            a,b=num(run(n.left)),num(run(n.right))
            if isinstance(n.op,ast.Add): return a+b
            if isinstance(n.op,ast.Sub): return a-b
            if isinstance(n.op,ast.Mult): return a*b
            if isinstance(n.op,ast.Div): return a/b
            if isinstance(n.op,ast.Pow):
                if abs(b)>1000 or abs(a)>1e100: raise ValueError('Power too large')
                return a**b
        if isinstance(n,ast.Compare):
            a=run(n.left)
            for op,right in zip(n.ops,n.comparators):
                b=run(right)
                if isinstance(op,ast.Eq): ok=a==b
                elif isinstance(op,ast.NotEq): ok=a!=b
                elif isinstance(op,ast.Lt): ok=a<b
                elif isinstance(op,ast.LtE): ok=a<=b
                elif isinstance(op,ast.Gt): ok=a>b
                elif isinstance(op,ast.GtE): ok=a>=b
                else: raise ValueError('Unsupported comparison')
                if not ok: return False
                a=b
            return True
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and not n.keywords:
            name=n.func.id.upper()
            args=n.args
            if name=='IF' and len(args)==3: return run(args[1] if run(args[0]) else args[2])
            vals=[run(a) for a in args]
            if name=='CELL' and len(vals)==1: return cell(vals[0])
            if name=='RANGE' and len(vals)==2:
                r,c=coordinates(vals[0].replace('$','')); rr,cc=coordinates(vals[1].replace('$',''))
                if (abs(rr-r)+1)*(abs(cc-c)+1)>100000: raise ValueError('Range too large')
                return [lookup(i,j) for i in range(min(r,rr),max(r,rr)+1) for j in range(min(c,cc),max(c,cc)+1)]
            flat=list(flatten(vals))
            numbers=[v for v in flat if type(v) in (int,float)]
            if name in ('SUM','AUTOSUM'): return sum(numbers)
            if name=='AVERAGE': return sum(numbers)/len(numbers)
            if name=='MIN': return min(numbers,default=0)
            if name=='MAX': return max(numbers,default=0)
            if name=='COUNT': return len(numbers)
            if name=='COUNTA': return sum(v!='' for v in flat)
            if name=='ABS' and len(vals)==1: return abs(num(vals[0]))
            if name=='ROUND' and 1<=len(vals)<=2:
                places=int(num(vals[1])) if len(vals)==2 else 0
                if abs(places)>100: raise ValueError('Precision too large')
                return float(Decimal(str(num(vals[0]))).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP))
            if name=='TODAY' and not vals: return (date.today()-date(1899,12,30)).days
            if name=='NOW' and not vals: return (datetime.now()-datetime(1899,12,30)).total_seconds()/86400
        raise ValueError('Unsupported formula')
    result=run(tree.body)
    if isinstance(result,complex): raise ValueError('Complex result')
    return result

import unittest
from datetime import date
from formulas import translate
from sheet import Sheet

class FormulaTests(unittest.TestCase):
    def test_functions_and_lazy_if(self):
        s=Sheet()
        for r,v in enumerate(['2','4','text','']): s.set(r,0,v)
        cases={'SUM(A1:A4,3)':9,'AVERAGE(A1:A4)':3,'MIN(A1:A4)':2,'MAX(A1:A4)':4,'COUNT(A1:A4)':2,'COUNTA(A1:A4)':3,'IF(A1=2,"Mixed Case",1/0)':'Mixed Case','ROUND(-2.5,0)':-3,'ABS(-7)':7,'2^3':8,'$A$1+A$2+$A1':8}
        for expr,expected in cases.items():
            with self.subTest(expr=expr):
                s.set(0,1,'='+expr)
                self.assertEqual(s.value(0,1),expected)
        s.set(0,1,'=TODAY()')
        self.assertEqual(s.value(0,1),(date.today()-date(1899,12,30)).days)
        s.set(0,1,'=NOW()')
        self.assertGreaterEqual(s.value(0,1),(date.today()-date(1899,12,30)).days)
    def test_translation_preserves_literals_and_absolute_axes(self):
        self.assertEqual(translate('=A1+$B$2+C$3+$D4+IF(A1=1,"A1",0)',2,3),'=D3+$B$2+F$3+$D6+IF(D3=1,"A1",0)')
        self.assertEqual(translate('=A1',-1,0),'=#REF!')
    def test_security_and_errors(self):
        s=Sheet()
        for expr in ['=__import__("os")','=A1','=AVERAGE(C1:C2)','=2^1000000','=SUM.__class__']:
            s.set(0,0,expr)
            self.assertEqual(s.display(0,0),'#ERROR')

import json
import unittest
from sheet import Sheet, address, coordinates


class SheetTests(unittest.TestCase):
    def test_addresses(self):
        for r,c in [(0,0),(99,25),(199,26),(4,702)]:
            self.assertEqual(coordinates(address(r,c)),(r,c))

    def test_formulas_and_recalculation(self):
        s=Sheet()
        s.set(0,0,'12.5')
        s.set(1,0,'7.5')
        s.set(2,0,'=SUM(A1:A2)')
        s.set(0,1,'=A3 * 2 + 1')
        self.assertEqual(s.value(0,1),41)
        s.set(1,0,'10')
        self.assertEqual(s.value(0,1),46)

    def test_errors_and_safe_evaluation(self):
        s=Sheet()
        for formula in ['=A1','=1/0','=__import__("os")','=SUM(A1:A2)']:
            s.set(0,0,formula)
            self.assertEqual(s.display(0,0),'#ERROR')

    def test_formats_and_roundtrip(self):
        s=Sheet()
        s.set(0,0,'1234.5')
        s.styles['A1']={'format':'Currency','decimals':2}
        s.set(0,1,'00123')
        s.styles['B1']={'format':'Text'}
        restored=Sheet.from_data(json.loads(json.dumps(s.dump())))
        self.assertEqual(restored.display(0,0),'$1,234.50')
        self.assertEqual(restored.display(0,1),'00123')
        self.assertIn('"$1,234.50"',restored.csv_text())

    def test_sort_numeric_and_whole_rows(self):
        s=Sheet()
        for r,row in enumerate([['Price','Item'],['10','ten'],['2','two'],['','blank'],['30','thirty']]):
            for c,v in enumerate(row): s.set(r,c,v)
        s.styles['A2']={'format':'Currency','decimals':2}
        s.sort_rows(0,numeric=True)
        self.assertEqual([s.raw(r,0) for r in range(5)],['Price','2','10','30',''])
        self.assertEqual(s.raw(2,1),'ten')
        self.assertEqual(s.styles['A3']['format'],'Currency')
        s.sort_rows(0,descending=True,numeric=True)
        self.assertEqual([s.raw(r,0) for r in range(5)],['Price','30','10','2',''])

    def test_mixed_column_uses_text_order(self):
        s=Sheet()
        for r,v in enumerate(['Header','2','10','3 apples','Apple','apple']): s.set(r,0,v)
        s.sort_rows(0,numeric=True)
        self.assertEqual([s.raw(r,0) for r in range(6)],['Header','10','2','3 apples','Apple','apple'])
        s.sort_rows(0,descending=True)
        self.assertEqual(s.raw(1,0),'Apple')


if __name__=='__main__': unittest.main()

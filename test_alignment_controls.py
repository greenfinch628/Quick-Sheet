import unittest
from tkinter import ttk, font
from unittest.mock import patch
import test_app

class FormattingControlsTests(unittest.TestCase):
    setUp=test_app.AppTests.setUp
    tearDown=test_app.AppTests.tearDown

    def test_alignment_applies_to_single_cell_blocks_rows_and_columns(self):
        a=self.app
        for selection in ('single','block','row','column'):
            for alignment in ('left','center','right'):
                with self.subTest(selection=selection,alignment=alignment):
                    a.select(2,2)
                    if selection=='block': a.select(4,5,extend=True)
                    elif selection=='row': a.select_header(0,2,preserve=False)
                    elif selection=='column': a.select_header(1,2,preserve=False)
                    before=a.sheet.dump()['styles'].copy()
                    r1,c1,r2,c2=a.bounds()
                    a.alignment_buttons[alignment].invoke()
                    for r in range(r1,r2+1):
                        for c in range(c1,c2+1):
                            self.assertEqual(a.sheet.style(r,c)['alignment'],alignment)
                    self.assertNotIn('alignment',a.sheet.style(r2+1,c2+1))
                    a.undo()
                    self.assertEqual(a.sheet.styles,before)

    def test_font_dropdowns_fit_longest_name(self):
        a=self.app
        families=list(font.families())+['An unusually long font family name for dropdown sizing']
        with patch('main.font.families',return_value=families): a.fonts()
        a.update()
        windows=[w for w in a.winfo_children() if w.winfo_class()=='Toplevel']
        win=windows[-1]
        dropdowns=[w for w in win.winfo_children() if isinstance(w,ttk.Combobox)]
        self.assertEqual(len(dropdowns),2)
        needed=max(font.nametofont('TkTextFont',root=a).measure(name) for name in families)
        for dropdown in dropdowns:
            self.assertGreater(dropdown.winfo_width()-25,needed)
        self.assertGreaterEqual(win.winfo_width(),win.winfo_reqwidth()-30)

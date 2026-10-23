# Quick-Sheet

A lightweight, single-sheet Python/Tk spreadsheet for Windows and Fedora. The core uses the standard library; XLSX import/export uses optional openpyxl.

## Run and install Excel support

Python 3.10+ with Tk is required. The launchers prefer a local `.venv` when present and otherwise use the system Python. Windows: double-click `Launch.vbs` or the existing shortcut. Fedora: run `sh launch.sh` or use the application menu.

Windows PowerShell, from the application directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Fedora (install `python3-tkinter` if missing):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
sh launch.sh
```

`tools/install_linux.sh` preserves the menu and icon installation convention for `~/Applications/Quick-Sheet`. Windows retains its VBS launcher, shortcut, and ICO files; Fedora retains its shell launcher, desktop entry, and PNG/SVG icons. Pillow is needed only to rebuild icons with `tools/build_icons.py`.

## Editing and formulas

- Type to replace a cell; double-click, Enter, or F2 to edit. The formula bar shows the original content.
- Arrows/Tab move; dragging or Shift+arrows selects a rectangle. Clicking a column heading selects its working rows. Delete clears contents. Ctrl+Z/Ctrl+Y undo/redo.
- Ctrl+C/X/V copy/cut/paste ranges with cell formats. External clipboard data uses tabs. A single copied cell can fill a selection. Copied formulas adjust relative references; `$A$1`, `A$1`, and `$A1` lock the indicated axes. Cut/paste keeps the formula text.
- Ctrl+D fills down from the selection's first row. Ctrl+R fills right from its first column. Both copy formats and translate references.
- Edit contains insert/delete rows and columns. Operations affect the selected number of rows/columns, move data and styles, and update formula references, including absolute references. Deleted referenced cells produce `#ERROR`.
- Formulas support arithmetic `+ - * / ^`, parentheses, comparisons `= <> < <= > >=`, strings, TRUE/FALSE, SUM, AVERAGE, MIN, MAX, COUNT, COUNTA, IF, ROUND, ABS, TODAY, and NOW. Aggregates accept ranges and multiple arguments: `=SUM(A1:B10,5)`. IF evaluates only its chosen branch. ROUND uses half-away-from-zero rounding.
- Example: `=IF(A1>0,ROUND(A1*$B$1,2),0)`. Numeric aggregates ignore text and blanks. COUNTA counts nonempty values. Errors/cycles display `#ERROR`.
- Values recalculate when displayed after edits. TODAY/NOW use local machine time and refresh the view every 30 seconds. Date functions return spreadsheet serial values; apply Date or Date/time formatting.
- The sum button inserts a SUM formula below each selected column if the destination is empty.

## Formatting and grid

The compact toolbar offers General, Text, Decimal, Currency (dollars), Percentage, Date, Date/time, and decimal precision. Text preserves leading zeros. ISO date input such as `2026-10-23` works with Date formatting.

Style opens bold/italic, left/center/right alignment, and text/fill colors for the selection. Size sets selected column widths and row heights in pixels. Both are undoable and saved in native files. Edit > Settings > Fonts sets sheet-wide menu/cell fonts.

Tools > Freeze First Row keeps row 1 visible. Its dropdowns offer text/numeric sorting and exact displayed-value filtering. Sorting moves whole rows and formats, preserves row 1, keeps blanks last, and includes hidden rows. Mixed numeric/text columns use text ordering. Existing sort behavior keeps formula reference text literal. Clear filters shows all rows.

Ctrl+F opens Find, F3 finds next, and Ctrl+H opens Replace. Search is case-insensitive, wraps through raw contents/formulas, and clears filters to reveal matches. Replacement can be undone.

## Files and recovery

Ctrl+O opens `.mini`, CSV, TSV, or XLSX. Ctrl+S saves; Ctrl+Shift+S opens Save As with all four formats. File > Recent files retains up to ten paths in the local session.

- `.mini` is the full-fidelity Quick-Sheet format, including styles, dimensions, fonts, and filters.
- CSV/TSV import handles quoted fields and UTF-8 BOMs. Export writes displayed values, including filtered rows. Saving with formulas/styles asks before using a values-only format.
- XLSX imports the active worksheet, formulas, supported formats/styles, sizes, and a frozen first row. It opens as an unsaved import so the original workbook is protected. Save As creates a single-sheet workbook. Other tabs, charts, macros, merges, and unsupported Excel features are not retained. Excel may recalculate formulas when opening a saved workbook. Import is limited to one million cells.
- New/Open/Import ask before discarding unsaved work. Named saves use a temporary file and replacement so failed writes retain the original.
- Closing preserves unsaved work, styles, selection, filters, view, fonts, recent paths, and undo history in `.mini-session.json`. A snapshot failure leaves the window open. Recovery is on normal close, not after a crash.

## Shared code and updates

The same Git repository serves nauvoo (Windows) and scopuli (Fedora): https://github.com/greenfinch628/Quick-Sheet. Keep `.mini-session.json` and `.venv` machine-local; they are ignored by Git. Back up existing local changes before updating.

```sh
git status --short
git pull --ff-only origin master
```

If dependencies changed, rerun the environment's `python -m pip install -r requirements.txt`. Close Quick-Sheet before updates, then relaunch using the platform launcher. The application uses sparse storage and draws the visible grid; very large workbooks and Excel's complete formula language are outside its scope.

## Tests

Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Fedora:

```sh
xvfb-run -a .venv/bin/python -m unittest -v
```

Tests cover formulas, reference translation, editing, formatting, dimensions, sorting/filter UI, clipboard, search, native/CSV/TSV/XLSX files, failed writes, and session recovery. macOS is untested.

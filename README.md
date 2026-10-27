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

Context menus for cells, row/column headings, the formula bar, and filters are drawn inside the main window. Escape dismisses them; clicking another cell dismisses the menu and selects the cell in one click. Shift+F10 opens a context menu from the grid or formula bar. Use Up/Down, Home/End, and Enter to choose commands; long filter lists also support the mouse wheel and scrollbar. Menus hide when the main window loses focus, unmaps, or changes geometry, and when the sheet scrolls. Focus-loss dismissal also handles GNOME minimizing an XWayland window without sending Tk an unmap event.

The system-Python branch of `launch.sh` retains its `WAYLAND_DISPLAY` workaround. Custom context menus no longer create separate popup windows, but the main menubar and Functions dropdown still use native Tk menus. Removing the launcher workaround requires a GNOME desktop check of those menus; the automated Xvfb tests do not establish whether it is still needed.

## Editing and formulas

- Type to replace a cell; double-click, Enter, or F2 to edit. The formula bar shows the original content.
- Arrows/Tab move; dragging or Shift+arrows selects a rectangle. Clicking a column heading selects its working rows. Delete clears contents. Ctrl+Z/Ctrl+Y undo/redo.
- Select a block, row, or column, then drag its blue border in the grid to move it. Dragging inside cells still changes the selection. A green outline previews a block destination; a green insertion line previews row/column placement. Release to move, or press Escape to cancel. Hold near a grid edge to scroll; releasing outside the grid cancels the move. Blocks replace destination cells after confirmation if data or formatting would be overwritten. Overlapping moves are supported. Whole rows/columns are inserted at the marked position, shifting the intervening rows/columns, and carry their heights/widths, styles, column precision, and column filters. Moves include hidden cells and keep formula reference text unchanged, matching cut/paste. Ctrl+Z/Ctrl+Y undo/redo each move.
- Ctrl+C/X/V copy/cut/paste ranges with cell formats. External clipboard data uses tabs. A single copied cell can fill a selection. Copied formulas adjust relative references; `$A$1`, `A$1`, and `$A1` lock the indicated axes. Cut/paste keeps the formula text.
- Ctrl+D fills down from the selection's first row. Ctrl+R fills right from its first column. Both copy formats and translate references.
- Edit contains insert/delete rows and columns. Operations affect the selected number of rows/columns, move data and styles, and update formula references, including absolute references. Deleted referenced cells produce `#ERROR`.
- Formulas support arithmetic `+ - * / ^`, parentheses, comparisons `= <> < <= > >=`, strings, TRUE/FALSE, SUM, AVERAGE, MIN, MAX, COUNT, COUNTA, IF, ROUND, ABS, TODAY, and NOW. Aggregates accept ranges and multiple arguments: `=SUM(A1:B10,5)`. IF evaluates only its chosen branch. ROUND uses half-away-from-zero rounding.
- Example: `=IF(A1>0,ROUND(A1*$B$1,2),0)`. Numeric aggregates ignore text and blanks. COUNTA counts nonempty values. Errors/cycles display `#ERROR`.
- Values recalculate when displayed after edits. TODAY/NOW use local machine time and refresh the view every 30 seconds. Date functions return spreadsheet serial values; apply Date or Date/time formatting.
- The Functions dropdown next to the formula bar lists Auto Sum, Sum, Average, Min, Max, Count, CountA, ABS, Today, and Now, in that order. Sum through CountA immediately place their formula in the active cell, automatically using consecutive nonempty cells above it in the same column. The range stops at the first blank, or at row 2 when the first row is frozen (otherwise row 1). With no cells above to use, the destination stays unchanged. ABS, Today, and Now insert an editable template; Enter applies it. IF and ROUND remain available by typing formulas. Right-click the formula bar for Cut, Copy, Paste, and Enter.
- Auto Sum is a custom running-total mode for columns A and B. Choose it to place `=AUTOSUM(A1:A1)` in B1 and select A1, or `=AUTOSUM(A2:A2)` in B2 and select A2 when row 1 is frozen. Type each number and press Enter to continue down column A; the formula's endpoint and total update with every committed entry. Existing column A entries are included immediately. Blanks and text do not add to the total, and entries after gaps still count. Edits, pasted ranges, cuts, and deletion of trailing entries also update the total. Other columns do not extend the range. Overwriting the total stops its automatic tracking; Clear Sheet removes it. Activation and entries support undo/redo. Native `.mini` files and session recovery retain live Auto Sum; XLSX exports use a standard SUM over the current range, and CSV/TSV export the current total.
- Right-click a cell and choose Sum to total every cell above it in the same column, including cells above gaps. Empty cells contribute zero; text is ignored. The formula starts at row 2 when the first row is frozen, otherwise row 1, and ends immediately above the destination. It includes hidden rows and updates when source cells change. With no data rows above the destination, Sum inserts zero. Toggling Freeze First Row affects newly created sums; existing formula ranges remain unchanged and can be edited in the formula bar or replaced by choosing Sum again. The toolbar Sum button applies the same operation to the active cell.

## Formatting and grid

The compact toolbar offers Cell Format (General, Text, Decimal, Currency in dollars, Percentage, Date, and Date/time) and decimal precision. Precision defaults to 0, displaying integers with no decimal point. Changing Decimals applies to every numeric cell in the selected column(s), including future entries and calculated values, without changing the underlying numbers. Type a precision or use the spinner; General format honors precision too. Text and dates retain their own presentation. Text preserves leading zeros. ISO date input such as `2026-10-23` works with Date formatting.

Format > Style opens bold/italic, left/center/right alignment, and text/fill colors for the selection. Format > Size opens a single dialog for column width and row height in pixels: Apply previews both sizes, Undo steps through size changes made since opening, Ok applies and closes, and Cancel (or closing the dialog) restores the starting dimensions. The up/down arrows at the far right move to the preceding/next row in the same column and show its cell address, contents, width, and height. Pending size edits are applied before moving; Undo traverses changes across visited rows, and Cancel restores both the original sizes and selection. Accepted size changes can also be undone with Ctrl+Z. Drag the right edge of a column letter or the bottom edge of a row number to resize it; each drag is one undo step. Right-click row numbers for Insert above/below or Delete, and column letters for Insert left/right or Delete. Shift-click headers to select multiple rows or columns. Styles and sizes are saved in native files. Edit > Settings > Fonts sets sheet-wide menu/cell fonts.

Clear Sheet removes all contents, cell formatting, column precision, sizes, filters, and sheet font overrides. It keeps the document filename and can be undone. Clear filters remains available in the Data menu.

All dialogs use a shared service that centers them on the application window, including style, size, font, search, file, color, and message dialogs. New dialogs should use `self.dialogs.window(...)` or the common-dialog methods on `self.dialogs`, rather than constructing unowned windows. On Windows the application sets a Quick-Sheet app identity and uses `assets/Quick-Sheet.ico` for the taskbar/window icons; the launcher shortcut uses the same ICO.

Select row 1 by clicking its row number, then right-click and choose Freeze First Row, or use Tools > Freeze First Row. This keeps row 1 visible. The context command becomes Unfreeze First Row while frozen; both it and the Tools command toggle the setting. Its dropdowns offer text/numeric sorting and exact displayed-value filtering. Sorting moves whole rows and formats, preserves row 1, keeps blanks last, and includes hidden rows. Mixed numeric/text columns use text ordering. Existing sort behavior keeps formula reference text literal. Clear filters shows all rows.

Ctrl+F opens Find, F3 finds next, and Ctrl+H opens Replace. Search is case-insensitive, wraps through raw contents/formulas, and clears filters to reveal matches. Replacement can be undone.

## Files and recovery

Ctrl+O opens `.mini`, CSV, TSV, or XLSX. Ctrl+S saves; Ctrl+Shift+S opens Save As with all four formats. File > Recent files retains up to ten paths in the local session.

- `.mini` is the full-fidelity Quick-Sheet format, including styles, dimensions, fonts, and filters.
- CSV/TSV import handles quoted fields and UTF-8 BOMs. Export writes displayed values, including filtered rows. Saving with formulas/styles asks before using a values-only format.
- XLSX imports the active worksheet, formulas, supported formats/styles, sizes, and a frozen first row. It opens as an unsaved import so the original workbook is protected. Save As creates a single-sheet workbook. Other tabs, charts, macros, merges, and unsupported Excel features are not retained. Excel may recalculate formulas when opening a saved workbook. Import is limited to one million cells.
- New/Open/Import ask before discarding unsaved work. Named saves use a temporary file and replacement so failed writes retain the original.
- Closing preserves unsaved work, styles, selection, filters, view, fonts, recent paths, and undo history in `.mini-session.json`. A snapshot failure leaves the window open. Recovery is on normal close, not after a crash.

## Shared code and updates

The same Git repository serves nauvoo (Windows) and scopuli (Fedora). Both installations have two remotes:

- `origin`: https://github.com/greenfinch628/Quick-Sheet.git
- `gitea`: ssh://git@scopuli:2224/scopuli/Quick-Sheet.git

Git commits are shared between both hosts. Push each remote explicitly; a normal `git push` updates only the upstream (`origin`). Direct Gitea access requires that machine's SSH public key to be registered in Gitea.

```sh
git push origin master
git push gitea master
```

 Keep `.mini-session.json` and `.venv` machine-local; they are ignored by Git. Back up existing local changes before updating.

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

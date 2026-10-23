# Quick-Sheet

A small, single-sheet desktop spreadsheet built with Python and Tk. No third-party runtime dependencies, server, account, or browser required.

## Run

Install Python 3.10 or newer, then run `python main.py` (on some Linux systems, `python3 main.py`). Windows Python installations normally include Tk. On Fedora, install `python3-tkinter`; on Ubuntu/Debian, install `python3-tk` if needed. Tk is also available on macOS, but this version has not been tested there.

For Windows, double-click `Launch.vbs` to start without a console window, or use the command above for diagnostics. Linux users can run `sh launch.sh`.

### Installed on scopuli

The Linux copy is installed at `/home/rczys/Applications/Quick-Sheet`. Open **Quick-Sheet** from the application menu, or run `/home/rczys/Applications/Quick-Sheet/launch.sh`. The launcher uses Fedora's `/usr/bin/python3`, with `python3-tkinter` installed. It runs directly from source, so there is no compilation step.

The desktop entry is `~/.local/share/applications/Quick-Sheet.desktop`. Linux icons are `~/Pictures/icons/Quick-Sheet.png` and `Quick-Sheet.svg`. The Windows icon is `C:\Users\rczys\OneDrive\Pictures\My Icons\Quick-Sheet.ico`; the existing workspace shortcut uses it. The application window also uses the shared PNG icon.

To update scopuli, copy `main.py`, `sheet.py`, `launch.sh`, the desktop entry, and `assets/` into that installation folder while the app is closed. Do not copy `.mini-session.json`: each machine retains its own session. The supplied `tools/install_linux.sh` installs icons and the application-menu entry after the files are copied. Rebuild the icon assets with `python tools/build_icons.py` using Pillow (build-time dependency only).

## Use

- Type to replace a cell; double-click, Enter, or F2 to edit it. The formula bar shows the original contents.
- Move with arrows or Tab. Drag or Shift + arrows to select a range. The bottom bar shows its numeric count and sum.
- Cut, copy, and paste individual cells or rectangular selections with Ctrl+X / Ctrl+C / Ctrl+V, the Edit menu, or the right-click menu. Internal clipboard operations preserve number formats; external text pastes as tab-separated data. A single copied cell fills a selected range. Click a column letter to select its current working rows (at least 200). Delete clears the selected cells. Ctrl+Z / Ctrl+Y undo and redo edits.
- Choose General, Text, Decimal, or Currency formatting for the selection. Currency uses dollars. Use Text to preserve leading zeros. **Edit → Settings → Fonts…** lets you set separate menu and cell font families and sizes across the sheet.
- Select numbers and click **Σ Sum below selection** to place a SUM formula in the empty row below each selected column.
- Formulas support cell references, arithmetic (`+ - * /`), parentheses, and rectangular ranges such as `=SUM(A1:B10)`. Errors and circular references show `#ERROR`.
- Enable **Tools → Freeze First Row** to keep row 1 visible while scrolling. Its dropdowns offer A–Z, Z–A, ascending numbers, descending numbers, and value filters. Sorting moves entire data rows with their formats, always keeping row 1 fixed. Numeric sort uses text order for the whole column if any nonblank value contains text. Text order ignores case; blank keys stay last. Sorting applies to all data rows, including filtered-out rows. Formula references remain literal when cells are sorted or copied.
- The menu bar includes **File**, **Edit**, **Search**, and **Data**. Ctrl+F opens Find, F3 finds the next match, and Ctrl+H opens Find and Replace. Search ignores case, wraps through the whole sheet, and searches original contents (including formulas). Finding a match clears filters so the match is visible. Replace supports the current cell or all matching cells and can be undone.
- Close the app without a save prompt. The next launch restores your sheet, unsaved edits, formats, fonts, filters, selection, scroll position, window size, and undo history. This session snapshot is written to `.mini-session.json` beside the app on a normal close. A write failure leaves the window open and reports the error. New/Open/Import still ask before discarding unsaved work in the current sheet.
- Save `.mini` files to preserve formulas, formats, fonts, and filters as named documents. **File → Open** accepts sheets and CSV. **Data → Import CSV** assumes comma delimiters, supports quoted fields, and opens the data in a new sheet without a delimiter question. **Data → Export CSV** saves the whole sheet's displayed values, including filtered-out rows; it does not preserve formulas or styles. Ctrl+S saves; Ctrl+Shift+S opens Save as.

## Scope

This is an initial desktop prototype. It does not read or write Excel `.xlsx` workbooks, offer multiple tabs, resize columns, or implement Excel's full formula language. Fonts are sheet-wide, with number formatting per cell. The viewport draws only visible cells; data is stored sparsely. It starts with 200 navigable rows and expands with pasted data and keyboard entry. Very large files are outside its intended use. Session recovery happens on normal close, not after a crash; the app folder must be writable.

## Checks

Run `python -m unittest -v` for model and desktop integration checks (requires a graphical desktop). They cover formulas, formatting, sorting, clipboard ranges, search/replace, CSV parsing, menus, and closing/reopening unsaved sessions. All 15 tests pass on Windows and Fedora Linux (scopuli, using `xvfb-run -a /usr/bin/python3 -m unittest -v`). macOS remains untested.

For standalone app distribution, a future release can package this with PyInstaller separately on each operating system.

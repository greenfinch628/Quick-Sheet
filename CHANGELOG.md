# Release history

## 1.1.1 — 2026-11-20

- Add `setup_windows.ps1` to create or reuse the local Python environment, verify Python 3.10+ and Tkinter, and install the application requirements.
- Generate current-user desktop and Start menu shortcuts using the installation folder and Quick-Sheet icon, with reuse of existing shortcut aliases and protection for unrelated shortcuts.
- Document installation on another Windows computer and optional interpreter and shortcut choices.
- Make the Linux session migration test independent of the host platform so it also runs on Windows.
- Verify fresh and repeated setup in a temporary path containing spaces, dependency installation, shortcut properties, alias reuse, and unrelated shortcut protection.

## 1.1.0 — 2026-11-20

- Add bottom worksheet tabs with creation, selection, renaming, duplication, deletion, and drag-and-drop reordering.
- Add a Worksheets menu for sheet actions and access to every worksheet.
- Preserve each worksheet's selection, scroll position, formatting, filters, and undo/redo history.
- Add the versioned `.qsheet` workbook format to retain all worksheets, names, order, and the active worksheet without additional dependencies.
- Restore complete workbooks and worksheet histories on normal session recovery; continue opening legacy single-sheet sessions and `.mini` files.
- Retain CSV/TSV and Excel active-worksheet import/export; warn before exporting a multi-worksheet workbook to a single-sheet format and retain the workbook's unsaved state.
- Update documentation, desktop description, and workbook regression coverage.
- Publish Fedora 44 RPM and Ubuntu 26.04 DEB packages at package revision 1; retain prior releases.
- Validate the full suite: 120 tests, with two Windows-only checks skipped. Verify package metadata/digests and confirm both package source payloads match the release sources.

## 1.0.0, package revision 2 — 2026-11-08

- Move whole-row selections with Up and Down and whole-column selections with Left and Right.
- Move left with Shift+Tab and commit an edit and move up with Shift+Enter.
- Extend selections to column A, column Z, row 1, or the last working row with Ctrl+Shift+Arrow. Keep the active cell fixed while adjusting the selection.
- Publish Fedora 44 RPM and Ubuntu 26.04 DEB packages with the application version held at 1.0.0.
- Verify both package payloads and run focused Tk navigation checks against the installed Fedora RPM.

## 1.0.0 — 2026-11-06

- Use a consistent desktop identity and existing application icons for GNOME.
- Add Help → About Quick-Sheet, reading the shared VERSION file.
- Include alignment toolbar buttons, Σ, Cell Style/Cell Size menu labels, and font selector sizing improvements.
- Add Fedora 44 RPM and Ubuntu 26.04 DEB builds with validated reuse and retained releases.
- Add a standalone Fedora RPM installer/updater, preserving manual sessions and source files and backing up obsolete launcher references.
- Store Linux sessions and settings in the user data directory rather than the installed application directory.

### Release validation

- Fedora 44: RPM installed successfully; source files match the installed payload; package verification and desktop-entry validation pass.
- Fedora 44 and Ubuntu 26.04: all 115 tests pass (two Windows-only checks skipped on each). Ubuntu tests ran against the installed DEB in a disposable container.
- Installed desktop launch, custom window icon, matching startup window class, and Help → About verified. GNOME denies direct dock introspection in this environment; a full visual dock check remains manual.
- Manual session/settings copied without changing the original; launcher backup and GNOME favorite migration verified. Updater and build reruns avoid reinstalling/rebuilding current releases.
- Cross-machine SSH retrieval requires working SSH authentication to Scopuli. The local loopback SSH authentication test was denied, so live remote retrieval could not be verified here.

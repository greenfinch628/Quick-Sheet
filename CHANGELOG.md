# Release history

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

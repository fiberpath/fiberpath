# TODO

- [ ] Add reprapdiscount smart graphics display to our machine and then document the process of connecting it to Marlin. More importantly, create documentation (need to think thru the best format for this) for the Marlin configuration itself for the machine as well as the physical wiring of everything.

- [ ] Review logic of how the various patterns are constructing and give tool tips or tables or aids or something or other to help users understand what the patterns are doing and how to use them effectively. The only relevant one right now is helical where it often gives circuit mismatch errors but its unclear where the raised number values come from / derive from their inputs in the properties panel.

- [ ] Add more detailed documentation for the various winding patterns and their parameters, including visual aids to help users understand concepts like wind angle, pattern number, skip index, and lock degrees.

- [ ] Research and develop new relevant wind patterns that could be useful for users, such as geodesic patterns or variable angle profiles.

- [ ] Figure out if it's possible and feasible to recognize `.wind` files on various systems to open fiberpath by default

- [ ] Implement machine connection info panel in the GUI, connect to Marlin to get example of the connection message upon connection, parse it (already have code that does this in the python lib) and display it in a side pane next to the log output in the stream tab. Consider how to handle refreshing the info, locking during jobs, and initial state before connection.

- [ ] Design a logo and replace the placeholder icon with an actual logo

- [ ] Fix zooming behavior in the plot viewer so it expands the entire image not within the image bounds since this becomes an issue for larger (exceeds bounds) or smaller (impossible to look at properly) images

- [ ] Track Dependabot moderate alert #3 (GHSA-wrw7-89jp-8q8g / glib). Current Tauri GTK stack pins `glib` 0.18.x (`^0.18` via `gtk`), so patched `glib` 0.20.0 cannot be adopted yet. Do not block a release solely for this; re-check after upstream Tauri/GTK dependency line moves to non-vulnerable glib.

- [ ] Track Dependabot low alert (GHSA-cq8v-f236-94qc / `rand`). The `rand 0.8.x` instance was patched to 0.8.6; a residual `rand 0.7.3` remains, pinned via `phf_generator 0.8.0` (`^0.7`) in Tauri's `tauri-build` → `kuchikiki` → `selectors`/`cssparser` chain. It is a **build-time-only** dependency (CSS-parser codegen), not in the shipped runtime, and the advisory (runtime `rand::rng()` soundness) does not apply to it — effectively zero risk. No 0.7.x fix exists; re-check after the Tauri `tauri-utils`/`kuchikiki` dependency line moves off `phf 0.8`. Do not block a release for this.

- [ ] Manual cross-platform validation (waived for v0.6.0, required before v1.0 or first public release): Linux `.deb`/`.AppImage` (Ubuntu 22.04, Debian 12, Fedora 39) and macOS `.dmg` (Intel + Apple Silicon) install, bundled CLI discovery, full workflow (validate → plan → simulate → visualize), serial port, file ops, upgrade, and uninstall. See `planning/roadmap-v6.md` Phases 1 & 2 for the full checklist.

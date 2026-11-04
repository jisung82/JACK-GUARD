# Changelog

## 0.2.1 — CMD-style color command, local release candidate

- Add `color`, `color /?`, one/two hexadecimal digits and all 16 classic console colors.
- Apply session colors to existing terminal content, controls and Swarm replay; restore the
  original app theme with bare `color`. No settings persistence or system shell invocation.
- Reject equal foreground/background and invalid values without changing colors; report ERRORLEVEL 1.
- Validate actual widget palettes, theme reset and replay backgrounds with regression tests.

## 0.2.0 — Terminal Edition, local release candidate

- Replace the dashboard with a monochrome terminal interface, native window frame,
  1100×700 default and 850×550 minimum size, monospace fonts and Korean fallback.
- Add the exact built-in command allowlist, Tab completion, in-memory command history,
  asynchronous current-user process queries and shared GUI/controller actions.
- Add an original QPainter Swarm reconstruction engine with synchronized real widget reveals,
  3/5/8 virtual cursors, speed controls, skip, replay and emergency workstation lock access.
- Honor Windows reduced motion; stop the animation timer on exit and reduce slow frames.
- Preserve P0 privacy/process/password/startup/log behavior and migrate existing settings.
- Include actual screenshots, intro GIF, Qt scale checks and measured performance.
- Public source license and GitHub publication remain pending owner approval.

## 0.1.0 — local release candidate, not yet published

- Initial Windows privacy companion implementation.
- Safe default monitoring, path exceptions and fail-closed process authorization.
- Korean dark UI, tray, shortcuts, multi-screen overlays and local settings/logs.
- Windows CI, reproducible dependency list, portable/single-file packaging and checksums.
- Prevent incompatible ICU/API-set DLL collection from external development tools.
- Distinguish shortcut collisions from desktop access denial; isolate automated test shortcuts.
- Public release and project license pending explicit owner approval.

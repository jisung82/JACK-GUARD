# Security and privacy boundaries

JACK GUARD assists the current interactive Windows user. Only LockWorkStation requests
an OS lock; Windows handles unlocking. Overlays do not prevent access to the desktop.
No input hooks, input blocking, privilege escalation, policy bypass, network transfer,
remote control, service, driver, self-protection or forced reboot is implemented.

Settings passwords use independent 32-byte salts and PBKDF2-HMAC-SHA256 (600,000 rounds),
constant-time digest comparison and increasing retry delays. Passwords protect this UI,
not files against the same account or administrators. Exit and local reset remain available.
Exports omit password records. Imports preserve the current password and disable actions.
Corrupt configuration fails closed, requiring explicit reset; it never silently drops a password.

Monitoring compares canonical executable paths, with an exception list taking priority.
Termination defaults off, requires explicit dialog consent, and refuses the app, its ancestors,
PID <=4, known essential executable names and paths under the Windows directory.
Immediately before termination a single Windows handle is opened with query/terminate rights.
The image path, current account SID, session ID and IsProcessCritical are checked on that handle.
Any failed check denies termination. This avoids killing a reused PID through a second lookup.
Users must only register their own games. Automatic termination may lose unsaved progress.
Not all protected applications can be inspected; access denial is expected and logged.

Configuration/logs are local and user-scoped. Folder ACL removes inherited grants and adds
the current user and SYSTEM. Administrators can take ownership. Deliberately shared preexisting
folders/custom parent ACLs are outside the default storage threat model.
Daily log files are capped near 2 MB and pruned on events/startup; no screen/input capture.
Qt native hotkey registration observes only selected shortcut activation, not arbitrary keys.

No signing certificate is included. SmartScreen reputation is not established.
Windows 10/11 x64 compatibility still needs the manual matrix in docs/TEST_RESULTS.md.

For security defects, report privately to the repository owner's security advisory channel
once the repository exists. Never include settings files, passwords or personal logs publicly.

# Authorized real-device test plan

These tests are **not executed** and require separate hardware/production approval.
Use an isolated printer and safely rated loads; identify the physical device first.
Record all software versions, active mode, channel, requested state, observed state,
readback result and evidence without credentials.

| ID | Authorized procedure and required observation |
| --- | --- |
| H01 | Compare original startup/default writes with and without companion; no extra companion write |
| H02 | Open companion settings, compare VID/PID/channel/active mode with the original, choose Light and enable only the intended lamp channel |
| H03 | Verify the instance device and Light in HA, with actual initial state, no manual YAML and no unsolicited write |
| H04 | Use HA ON/OFF sequentially; compare the physical lamp, HA and both OctoPrint displays; stop on any mismatch |
| H05 | Use the visible original ON/OFF buttons; compare the physical lamp and immediate companion/HA updates |
| H06 | Interrupt MQTT safely; original local control still works, HA follows LWT, reconnect rereads current state without replaying old commands |
| H07 | Restart OctoPrint; only documented original defaults may write, companion only reads/publishes |
| H08 | Restart HA; discovery, availability and current state return, retained command replay remains inert |
| H09 | Disable, uninstall, restart and authorized update/rollback; original plugin remains usable and no foreign topic deleted |

A pass in synthetic software tests is not a hardware pass. Human code review,
real screenshots and explicit release approval remain separate gates.

After the basic sequence, separately authorize multi-channel Active High/Low checks,
controlled USB removal, real original configuration reconstruction, type/prefix/name
changes and update/rollback. Never disconnect a load or change active mode without a
safe electrical plan. Restore the documented starting configuration, remove synthetic
retained commands and record teardown. Original default writes must be understood before
every restart; stop immediately on any unplanned output.

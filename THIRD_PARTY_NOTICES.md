# Third-party boundaries and license recommendation

The product does not bundle upstream implementation code. Explicit test preparation
downloads checksum-pinned upstream sources into ignored local artifacts. Installed
upstream plugins remain separate distributions with their own notices and licenses.

| Reference | Upstream license observed in the pinned source | Use |
| --- | --- | --- |
| USB Relay Control 1.0.0 | AGPL version 3; no additional later-version grant inferred | Existing objects and narrow runtime method adapter; test source fixtures |
| OctoPrint-MQTT 0.8.19 / 0.8.20 | AGPL version 3 or later according to upstream declaration | Existing public MQTT helpers; test source fixtures |
| OctoPrint | AGPL version 3 or later according to upstream declaration | Plugin API and runtime |
| MQTT exposure for PSU Control 1.3.0 | AGPL version 3 or later according to upstream package metadata | Architecture reference only; no implementation copied |
| Home Assistant | Apache License 2.0 according to upstream distribution | External discovery consumer; optional isolated schema validation |

Sources: [USB Relay Control](https://github.com/abudden/OctoPrint-USBRelayControl),
[OctoPrint-MQTT](https://github.com/OctoPrint/OctoPrint-MQTT),
[OctoPrint](https://github.com/OctoPrint/OctoPrint),
[Home Assistant](https://github.com/home-assistant/core),
[PSU companion reference](https://github.com/oerkel47/OctoPrint-MQTT-for-PSUcontrol/tree/ff7c4efc386617ef517213d7fc63716ac415951c).

AGPL-3.0-or-later is the proposed license for this companion, subject to the owner's
explicit final approval and review of combined-work obligations. Interaction through
helpers or instance wrappers is not presented as a blanket exemption from upstream
license obligations. Copied upstream source is not included in product files or public
release archives. If future changes copy or distribute such code, preserve notices
and reassess compatibility and corresponding-source obligations first.

**No project license has been granted by this document.** The final LICENSE file,
SPDX expression, public copyright attribution and release metadata remain approval
gates. Do not publish or redistribute this development build as an approved release.
The [GNU AGPL text](https://www.gnu.org/licenses/agpl-3.0.html) is the reference for the
recommendation; this engineering note is not a legal determination.

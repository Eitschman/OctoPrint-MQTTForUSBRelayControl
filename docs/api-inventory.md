# Integration API inventory

The initial contract targets OctoPrint 2.0.1, USB Relay Control 1.0.0 and
OctoPrint-MQTT 0.8.19/0.8.20. Python 3.9 is the minimum product interpreter.
The source revisions and SHA-256 checksums live in
`tests/fixtures/upstream-manifest.json`. Preparation downloads them explicitly;
normal unit tests never download code or connect to hardware.

| Boundary | Contract | Failure behavior |
| --- | --- | --- |
| Original plugin | `get_plugin_info("usbrelaycontrol").implementation` | Refuse unknown versions, signatures or wrappers |
| Original settings | `usbrelay_configurations`; vendor, product, relaynumber, active_mode, name | Validate identifiers and reject duplicate normalized channels |
| Existing relay | `state(relay, on=None)`; bool reads, None writes | Always read after a write; distinguish exceptions and mismatches |
| Original lifecycle | instance `on_after_startup`, `on_settings_save` | Observe actual calls; never invoke them for synchronization |
| MQTT helpers | `get_helpers("mqtt", ...)` | No client construction, no offline queue, no claimed delivery ACK |
| MQTT subscribe | `(topic, callback, args=None, kwargs=None)` | Effective QoS 0; retain metadata required |
| MQTT unsubscribe | `(callback, topic=None)` | One exact topic per invocation |
| Connection events | `register_message_receiver(callback)`; callback accepts permissions | Boolean mqtt connected messages; retained LWT only bootstraps unknown status |
| Own settings API | SimpleApiPlugin, `is_api_adminonly`, protected API | Use OctoPrint authentication, permissions and CSRF protection |
| Teardown | `on_shutdown`, `on_plugin_disabled`, pending-uninstall, Plugin Manager events | Invalidate queued work before removing instance wrappers |
| Original browser model | optional `uSBRelayControlViewModel`, `usbrelayButtons`, `usbrelayConfigurations` | Validate Knockout observables and current channel mapping |

OctoPrint's examined LifecycleManager does not attach its event wrappers in its
constructor. It is not the sole dependency lifecycle mechanism. Browser assets
make restart requirements apply even when internal disabling takes effect immediately.

The oldest supported OctoPrint version must be established by installation and
lifecycle tests; source API similarity alone is insufficient. Hardware behavior
remains unverified until separately authorized real-device tests.

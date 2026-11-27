/* Event-driven companion view model. Original view model methods stay intact. */
(function (root) {
  "use strict";
  function normalizeId(value) {
    if (typeof value !== "string" || !/^(0x)?[0-9a-f]+$/i.test(value))
      return null;
    var number = parseInt(value, 16);
    return number <= 65535 ? number.toString(16).padStart(4, "0") : null;
  }
  function matches(row, configuration) {
    return (
      configuration &&
      normalizeId(configuration.vendor) === row.vendor &&
      normalizeId(configuration.product) === row.product &&
      String(configuration.relaynumber) === String(row.channel) &&
      configuration.active_mode === row.active_mode
    );
  }
  function createBridge(original, knockout) {
    var active = false;
    var latest = [];
    var compatible = Boolean(
      original &&
      knockout.isObservable(original.usbrelayButtons) &&
      typeof original.usbrelayButtons.replace === "function" &&
      knockout.isObservable(original.usbrelayConfigurations),
    );
    function apply() {
      if (!compatible || active) return;
      active = true;
      try {
        var configurations = knockout.toJS(original.usbrelayConfigurations);
        latest.forEach(function (row) {
          if (!matches(row, configurations[row.index])) return;
          var item = original.usbrelayButtons()[row.index];
          if (!item) return;
          var actual = row.snapshot && row.snapshot.actual;
          var state =
            typeof actual === "boolean" ? (actual ? "on" : "off") : "unknown";
          if (item.current_state !== state) {
            original.usbrelayButtons.replace(
              item,
              Object.assign({}, item, { current_state: state }),
            );
          }
        });
      } finally {
        active = false;
      }
    }
    var subscription = compatible
      ? original.usbrelayButtons.subscribe(apply)
      : null;
    return {
      compatible: compatible,
      update: function (rows) {
        latest = rows;
        apply();
      },
      dispose: function () {
        if (subscription) subscription.dispose();
      },
    };
  }
  root.MQTTUSBRelayUI = {
    normalizeId: normalizeId,
    matches: matches,
    createBridge: createBridge,
  };
  if (!root.OCTOPRINT_VIEWMODELS) return;
  root.$(function () {
    function MQTTForUSBRelayControlViewModel(parameters) {
      var self = this;
      var identifier = "mqttforusbrelaycontrol";
      self.settingsViewModel = parameters[0];
      self.loginState = parameters[1];
      var original = parameters[2];
      var bridge = createBridge(original, root.ko);
      var epoch = -1,
        revision = -1;
      var connectionGeneration = 0;
      self.configuration = root.ko.observable();
      self.status = root.ko.observable({
        connected: null,
        ready: false,
        relays: [],
        versions: {},
      });
      self.rows = root.ko.observableArray([]);
      self.busy = root.ko.observable(false);
      self.actionError = root.ko.observable("");
      self.frontendCompatible = bridge.compatible;
      self.isAdmin = root.ko.pureComputed(function () {
        return self.loginState.isAdmin();
      });
      self.connectionText = root.ko.pureComputed(function () {
        var connected = self.status().connected;
        return connected === true
          ? root.gettext("Connected")
          : connected === false
            ? root.gettext("Disconnected")
            : root.gettext("Unknown");
      });
      self.readyText = root.ko.pureComputed(function () {
        return self.status().ready
          ? root.gettext("Ready")
          : root.gettext("Inactive");
      });
      self.deviceSourceText = root.ko.pureComputed(function () {
        var source = self.status().device_source;
        return source === "octoprint"
          ? root.gettext("HomeAssistant Discovery")
          : source === "custom"
            ? root.gettext("Custom identifier")
            : root.gettext("Separate companion device");
      });
      self.deviceWarningText = root.ko.pureComputed(function () {
        var reason = self.status().device_warning;
        if (reason === "cached")
          return root.gettext(
            "Device identity could not be read. Keeping the last confirmed assignment.",
          );
        if (reason === "unavailable")
          return root.gettext(
            "Device identity could not be read and no saved assignment is available. Using a separate device.",
          );
        if (reason === "cache_write_failed")
          return root.gettext(
            "Device assignment is active but could not be saved for recovery after restart.",
          );
        return "";
      });
      self.durationText = function (seconds) {
        return typeof seconds === "number" && Number.isFinite(seconds)
          ? seconds.toFixed(2) + " s"
          : "—";
      };
      self.operationText = function (kind) {
        var labels = {
          read: root.gettext("Reading"),
          write: root.gettext("Writing"),
          configuration: root.gettext("Configuring"),
          reconcile: root.gettext("Synchronizing"),
          command: root.gettext("Command"),
          publish: root.gettext("Publishing"),
        };
        return labels[kind] || root.gettext("Idle");
      };
      function ownSettings() {
        return self.settingsViewModel.settings.plugins[identifier];
      }
      function rebuildRows() {
        var options = root.ko.toJS(ownSettings().relays) || {};
        self.rows(
          self.status().relays.map(function (entry) {
            var settings = options[entry.id] || {};
            return Object.assign({}, entry, {
              snapshot: root.ko.observable(entry.snapshot),
              enabled: root.ko.observable(settings.enabled === true),
              entity_type: root.ko.observable(settings.entity_type || "switch"),
              display_name: root.ko.observable(settings.display_name || ""),
            });
          }),
        );
      }
      function receive(data) {
        if (
          !data ||
          data.schema !== 1 ||
          !Array.isArray(data.relays) ||
          !Number.isSafeInteger(data.epoch) ||
          data.epoch < 0 ||
          !Number.isSafeInteger(data.revision) ||
          data.revision < 0 ||
          data.epoch < epoch ||
          (data.epoch === epoch && data.revision < revision)
        )
          return;
        epoch = data.epoch;
        revision = data.revision;
        self.status(data);
        bridge.update(data.relays);
        // Preserve unsaved field edits while updating live state and new configuration rows.
        var previous = {};
        self.rows().forEach(function (row) {
          previous[row.id] = row;
        });
        self.rows(
          data.relays.map(function (entry) {
            var row = previous[entry.id];
            if (row) {
              row.snapshot(entry.snapshot);
              var metadataChanged = [
                "index",
                "original_name",
                "vendor",
                "product",
                "channel",
                "active_mode",
              ].some(function (key) {
                return row[key] !== entry[key];
              });
              if (!metadataChanged) return row;
              return Object.assign({}, row, entry, {
                snapshot: row.snapshot,
                enabled: row.enabled,
                entity_type: row.entity_type,
                display_name: row.display_name,
              });
            }
            var options = root.ko.toJS(ownSettings().relays) || {};
            var settings = options[entry.id] || {};
            return Object.assign({}, entry, {
              snapshot: root.ko.observable(entry.snapshot),
              enabled: root.ko.observable(settings.enabled === true),
              entity_type: root.ko.observable(settings.entity_type || "switch"),
              display_name: root.ko.observable(settings.display_name || ""),
            });
          }),
        );
      }
      self.refresh = function () {
        var generation = connectionGeneration;
        if (self.isAdmin())
          root.OctoPrint.simpleApiGet(identifier).done(function (data) {
            if (generation === connectionGeneration) receive(data);
          });
      };
      self.onServerReconnect = function () {
        connectionGeneration += 1;
        epoch = -1;
        revision = -1;
        self.refresh();
      };
      self.onBeforeBinding = function () {
        self.configuration(ownSettings());
        self.refresh();
      };
      self.onUserLoggedIn = self.refresh;
      self.onSettingsShown = function () {
        rebuildRows();
        self.refresh();
      };
      self.onSettingsHidden = rebuildRows;
      self.onSettingsBeforeSave = function () {
        ["command_max_age", "command_min_interval"].forEach(function (key) {
          var setting = ownSettings()[key];
          if (root.ko.isObservable(setting)) setting(Number(setting()));
        });
        var options = root.ko.toJS(ownSettings().relays) || {};
        self.rows().forEach(function (row) {
          options[row.id] = {
            enabled: row.enabled(),
            entity_type: row.entity_type(),
            display_name: row.display_name(),
          };
        });
        if (root.ko.isObservable(ownSettings().relays))
          ownSettings().relays(options);
        else ownSettings().relays = options;
      };
      self.onAllBound = function () {
        if (self.isAdmin())
          root.OctoPrint.simpleApiCommand(identifier, "frontend", {
            compatible: bridge.compatible,
          });
      };
      self.onDataUpdaterPluginMessage = function (plugin, data) {
        if (plugin === identifier) receive(data);
      };
      self.stateText = function (row) {
        var snapshot = root.ko.unwrap(row.snapshot);
        var actual = snapshot && snapshot.actual;
        return typeof actual === "boolean"
          ? actual
            ? root.gettext("On")
            : root.gettext("Off")
          : root.gettext("Unknown");
      };
      self.stateKind = function (row) {
        var snapshot = root.ko.unwrap(row.snapshot);
        return snapshot && typeof snapshot.actual === "boolean"
          ? snapshot.actual
            ? "on"
            : "off"
          : "unknown";
      };
      self.availabilityText = function (row) {
        var status = self.status();
        var saved = status.relays.find(function (entry) {
          return entry.id === row.id;
        });
        var snapshot = root.ko.unwrap(row.snapshot);
        return saved &&
          saved.enabled &&
          status.ready &&
          status.connected === true &&
          snapshot &&
          typeof snapshot.actual === "boolean" &&
          snapshot.outcome === "confirmed"
          ? root.gettext("Available for MQTT")
          : root.gettext("Unavailable for MQTT");
      };
      self.relayName = function (row) {
        return row.original_name || root.gettext("Relay") + " " + row.channel;
      };
      self.targetText = function (row) {
        var snapshot = root.ko.unwrap(row.snapshot);
        if (!snapshot || typeof snapshot.target !== "boolean") return "";
        return (
          root.gettext("Requested:") +
          " " +
          (snapshot.target ? root.gettext("On") : root.gettext("Off"))
        );
      };
      self.errorText = function (row) {
        var snapshot = root.ko.unwrap(row.snapshot);
        if (!snapshot) return "";
        var messages = [];
        if (snapshot.write_error)
          messages.push(
            root.gettext("Write failed:") + " " + snapshot.write_error,
          );
        if (snapshot.read_error)
          messages.push(
            root.gettext("Read failed:") + " " + snapshot.read_error,
          );
        if (snapshot.outcome === "mismatch")
          messages.push(
            root.gettext("Actual state differs from requested state"),
          );
        return messages.join("; ");
      };
      self.action = function (command) {
        var confirmed = true;
        if (command === "cleanup")
          confirmed = root.confirm(
            root.gettext("Submit pending discovery deletions? Count:") +
              " " +
              self.status().pending_deletions,
          );
        if (command === "clone")
          confirmed = root.confirm(
            root.gettext(
              "Create a new identity for this offline clone? Old topics will remain untouched.",
            ),
          );
        if (!confirmed || self.busy() || !self.isAdmin()) return;
        self.busy(true);
        self.actionError("");
        root.OctoPrint.simpleApiCommand(identifier, command, {
          confirmed: confirmed,
        })
          .fail(function () {
            self.actionError(
              root.gettext(
                "The action failed. Check the current prerequisites.",
              ),
            );
          })
          .always(function () {
            self.busy(false);
            self.refresh();
          });
      };
    }
    root.OCTOPRINT_VIEWMODELS.push({
      construct: MQTTForUSBRelayControlViewModel,
      name: "mqttForUSBRelayControlViewModel",
      dependencies: [
        "settingsViewModel",
        "loginStateViewModel",
        "uSBRelayControlViewModel",
      ],
      optional: ["uSBRelayControlViewModel"],
      elements: ["#settings_plugin_mqttforusbrelaycontrol"],
    });
  });
})(typeof window !== "undefined" ? window : globalThis);

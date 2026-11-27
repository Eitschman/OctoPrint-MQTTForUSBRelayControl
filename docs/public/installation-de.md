# Installation und Konfiguration

Die stabile Version ist [0.1.0](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/releases/tag/0.1.0).
Der Projektinhaber bestätigt menschliche Prüfung, erfolgreichen Betrieb auf echter
Hardware und die erfolgreiche Installation aus der öffentlichen Beta-URL.
Lizenz: AGPL-3.0-or-later. Maintainer: Eitschman. Automatische Tests verwenden
isolierte synthetische Hardware und dürfen niemals auf eine produktive Instanz zeigen.

Voraussetzungen: Python 3.11+, eine unterstützte OctoPrint-Installation, USB Relay
Control 1.0.0 und OctoPrint-MQTT 0.8.19 oder 0.8.20. Zuerst Kanäle im Originalplugin
konfigurieren und dessen normale Bedienung prüfen. Der Companion verwendet dieselben
Relaisobjekte und die vorhandene MQTT-Verbindung; er installiert keinen USB-Treiber.

Im vorhandenen MQTT-Plugin das Last Will selbst aktivieren und die Verbindung prüfen.
Ohne Last Will bleiben MQTT-Schaltbefehle und neue Discovery gesperrt. Retained Last
Will erlaubt die Initialisierung nach einer bereits erfolgten Verbindung. Das Plugin
verändert keine fremden Einstellungen. Broker-ACLs und Verschlüsselung entsprechend
der bestehenden Installation konfigurieren: Frische berechtigte Befehle können reale
Hardware schalten.

In OctoPrint **Einstellungen → Plugin Manager → Mehr … → … von URL** öffnen.
Diese genaue Archivadresse einfügen, installieren und OctoPrint neu starten:

```text
https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/archive/refs/tags/0.1.0.zip
```

Danach muss der Plugin Manager die Version **0.1.0** anzeigen. Vorhandene Companion-Einstellungen bleiben
bei einem Update erhalten. Danach die installierte Version im Plugin Manager prüfen.
Vor Updates die OctoPrint-Sicherung verwenden und die zugehörigen Release Notes lesen.
Stabile Versionen erst installieren, wenn sie auf der
[Release-Seite](https://github.com/Eitschman/OctoPrint-MQTTForUSBRelayControl/releases) stehen.
Lokal geprüfte Wheels mit dem Python der OctoPrint-Umgebung installieren und ebenfalls
neu starten. Keine ZIP-Datei des privaten gesamten Arbeitsverzeichnisses installieren oder verteilen.

Unter Einstellungen → MQTT for USB Relay Control die Integration aktivieren und jeden
gewünschten Kanal separat freigeben. Switch, Light und Fan bieten ausschließlich
binäres Ein/Aus. Optional einen Home-Assistant-Namen setzen. Mit OctoPrint Speichern
übernehmen oder mit Schließen verwerfen. Aktionen verwenden die gespeicherten Einstellungen.
Hardwarewerte bleiben im Originalplugin. Active Low invertiert den physischen Bitwert;
logisches Ein bedeutet stets den konfigurierten aktiven Zustand. Kanäle 1–8 sind
unabhängig nutzbar; Kanal 0 wird keine eigene Entität. Doppelte normalisierte Kanäle
werden gesperrt. Mehrere physische Platinen mit identischer VID/PID sind durch das
Original nicht getrennt auswählbar.

Discovery ist standardmäßig aktiviert. MQTT-Präfix leer lassen, um das Basispräfix
des vorhandenen MQTT-Plugins zu verwenden. Discovery-Präfix `homeassistant`, Birth-Topic
`homeassistant/status` und Payload `online` sind die Vorgaben. Unter den erweiterten
Einstellungen können Präfixe, Gerätename, Birth und Debug-Logging angepasst werden.
Standardmäßig werden Relais dem vorhandenen Gerät des aktiven Plugins **HomeAssistant
Discovery** über dessen exakte `node_id` zugeordnet. Ein leerer Gerätename übernimmt
dessen Namen. Unser Plugin liest nur `node_id` und `node_name`; es verändert das
andere Plugin nicht und benötigt keinen direkten Home-Assistant-Zugriff.

Fehlt das Plugin oder ist es deaktiviert, bleibt es bei unserem separaten Gerät.
Bei einem vorübergehenden Lookup-/Lesefehler oder einer ungültigen Quellkennung
bleibt die zuletzt gültige Zuordnung erhalten, auch nach einem Neustart. Nur diese
Kennung und ihr Name werden in `device-identity.json` im eigenen Plugin-Datenordner
gespeichert; fremde Einstellungen werden nicht geschrieben. Die Diagnose zeigt die
Verwendung des Zwischenspeichers beziehungsweise die fehlende Quelle an. Ohne
vorherige Zuordnung wird ein separates Gerät verwendet. Eine neue gültige Kennung
ersetzt die alte Zuordnung.
Für ein ausdrücklich separates Gerät **Vorhandenes OctoPrint-Gerät verwenden, wenn
verfügbar** deaktivieren und **Gerätekennung überschreiben** leer lassen. Sein leerer
Gerätename folgt dem MQTT-Basistopic ohne abschließende Schrägstriche (`octoPrint/`
wird `octoPrint`), unabhängig vom eigenen MQTT-Präfix.

Eine eigene **Gerätekennung** hat Vorrang vor Automatik und Checkbox. Die exakte
MQTT-Gerätekennung einschließlich Groß-/Kleinschreibung eingeben, nicht den Anzeigenamen.
Ohne eigenen Namen bleibt der Name dieses Zielgeräts erhalten. Ein eigener Name
benennt auch ein gemeinsames Gerät um; spätere Discovery-Nachrichten des anderen
Plugins können ihn erneut ändern. Hersteller-/Modellangaben werden nicht übernommen.

Nach einem Update von dev2 Einstellungen speichern oder **Discovery übergeben**
verwenden. Relais-IDs und Discovery-/Command-/State-Topics bleiben unverändert.
Gerätebasierte Automationen mit dem bisherigen separaten Gerät bei einer Umordnung
prüfen. Das vorhandene OctoPrint-Gerät und seine anderen Entitäten nicht löschen.
Ältere Home-Assistant-Versionen können ein leeres bisheriges Gerät zurücklassen.
Bei Offline-Klonen muss außerdem die kopierte Kennung des anderen Discovery-Plugins
beziehungsweise eine manuelle Gerätekennung separat angepasst werden; unsere
Klonaktion ändert diese fremden Kennungen nicht.
Nur konkrete Topics ohne Wildcards, NUL oder leere Segmente verwenden; Command, State,
Availability, Discovery, Birth und Last Will dürfen nicht kollidieren.

Unter **Befehlsschutz** gelten standardmäßig **5 Sekunden maximales Befehlsalter**
(einstellbar von 1 bis 60) und **0,25 Sekunden Mindestabstand pro Kanal** (0,1 bis
10). Der Abstand beginnt nach Abschluss eines Befehls. MQTT-Befehle warten auf ihren
Kanal und verfallen vor der Ausführung, wenn sie zu alt sind. Andere Kanäle und
Zustandsmeldungen können währenddessen weiterlaufen. Mit Speichern übernehmen.
Laufende Hardwareaufrufe lassen sich dadurch nicht abbrechen; die ursprünglichen
Relaisschaltflächen behalten ihr Verhalten. Die Diagnose zeigt Warteschlange,
verfallene Befehle, Überläufe und die zuletzt erfassten Laufzeiten. Ein Hardwareaufruf
über 2 Sekunden löst eine Warnung aus; es gibt keine zyklische Hardwareabfrage.
Das Lesen des Controllers bestätigt nur dessen gemeldete Bits, keine Spannung am
angeschlossenen Verbraucher. Bei blockierter Hardware zuerst die Ursache prüfen.
Eine fehlgeschlagene Wiederherstellung der Anbindung erfordert einen OctoPrint-Neustart,
bevor unser Plugin die Hardware erneut anbinden kann.

Nach dem Speichern entdeckt Home Assistant freigegebene Entitäten. Verfügbarkeit
setzt sowohl das vorhandene MQTT-Last-Will als auch erfolgreiche Zustandsermittlung
des Kanals voraus. Jeder MQTT-Schaltversuch wird nachgelesen. Sollzustand ist kein
Istnachweis; unbekannt bedeutet nicht Aus. Eine erfolgreiche Helper-Rückgabe ist keine
Zustellbestätigung. Retained Replay wird vor Hardwareaktionen verworfen; Publisher
müssen retain=false verwenden. Bei MQTT-Ausfällen werden keine Befehle oder historischen
Zustände gepuffert. Reconnect und Birth lesen den aktuellen Zustand erneut.

„Aktuelle Zustände lesen“ führt ausschließlich Reads aus. „Discovery übergeben“
sendet aktuelle Konfigurationen. „Ausstehende Löschungen übergeben“ verlangt eine
Bestätigung mit Anzahl und betrifft nur eigene obsolete Discovery-Topics. Keine
Aktion ruft den Settings-Save des Originals zum Zustandsabgleich auf.

Eine geklonte OctoPrint-Instanz kopiert die UUID. Den Klon deshalb vor MQTT-Verbindung
offline halten, einen bestätigten Offline-Verbindungszustand herstellen und „Neue
Identität für Offline-Klon“ bestätigen. Die neue UUID wird dauerhaft gespeichert;
alte Identität und Eigentumsdaten werden nur lokal abgetrennt. Es erfolgen keinerlei
Publikationen oder Löschungen auf der kopierten alten Identität. Kanal-Freigaben der
alten Identität werden nicht automatisch übernommen; neue Kanäle ausdrücklich prüfen
und freigeben. Klone werden nicht
automatisch erkannt. Erst anschließend gewünschtes Broker-/Präfixziel konfigurieren
und verbinden.

Zur Deinstallation bei erreichbarem Broker die Integration deaktivieren, eigene
ausstehende Discovery-Löschungen übergeben und Entfernung bei Broker und Home Assistant
prüfen. Companion deinstallieren und OctoPrint neu starten. Offline-Deinstallation
kann retained Einträge hinterlassen; später ausschließlich die dokumentierten eigenen
Topics entfernen. Kein automatisches Ausschalten der Hardware. Originalkonfiguration
bleibt beim Originalplugin.

Ohne Polling werden ausschließlich beobachtete Softwarepfade und definierte
Abgleichereignisse erfasst. Beliebige Hardwareausfälle oder externe Änderungen sind
nicht universell erkennbar. Bei Lesefehlern Originalbedienung prüfen und gezielt neu
lesen; inkompatible Versionen und fehlende Abhängigkeiten sperren den Companion.
Siehe englische [Fehlerhilfe](troubleshooting.md), [Datenschutz](privacy.md),
[Kompatibilität](compatibility.md) und [MQTT-Vertrag](mqtt-topics.md). Lizenzfreigabe und
öffentliche Supportkontakte stehen noch aus; keine Zugangsdaten in öffentliche Meldungen.

"""Opt-in fake HID for isolated OctoPrint subprocesses only."""

import os

if os.environ.get("MQTT_RELAY_ISOLATED_TEST") != "1":
    raise RuntimeError("The test HID module requires an explicitly isolated test process")


class device:
    def __init__(self):
        self.bits = 0
        self.closed = False

    def open(self, vendor, product):
        if os.environ.get("MQTT_RELAY_TEST_NO_DEVICE") == "1":
            raise OSError("The synthetic test device is absent")
        if (vendor, product) != (0x16C0, 0x05DF):
            raise OSError("Only the synthetic test device is available")

    def set_nonblocking(self, value):
        pass

    def close(self):
        self.closed = True

    def send_feature_report(self, message):
        if self.closed:
            raise OSError("Synthetic device is closed")
        operation = message[0]
        if operation in (0xFE, 0xFC):
            self.bits = 255 if operation == 0xFE else 0
        elif operation == 0xFF:
            self.bits |= 1 << (message[1] - 1)
        else:
            self.bits &= ~(1 << (message[1] - 1))
        return len(message)

    def get_feature_report(self, feature, length):
        if os.environ.get("MQTT_RELAY_TEST_READ_FAILURE") == "1":
            raise OSError("Synthetic state read failure")
        if self.closed:
            raise OSError("Synthetic device is closed")
        return [0] * 7 + [self.bits]

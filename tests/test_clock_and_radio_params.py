"""Audit R5 (clock sanity) and R6 (radio parameter validation).

Source anchors plus small Python mirrors of the MMBasic helpers. Firmware
limits were read from MeshCore main 81dbae5 (examples/companion_radio/
MyMesh.cpp): CMD_SET_DEVICE_TIME refuses times earlier than the radio clock;
CMD_SET_RADIO_PARAMS accepts 150000-2500000 kHz, BW 7000-500000 Hz, SF 5-12,
CR 5-8. Not PicoMite execution.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()
LORA_BW_KHZ = ["7.8", "10.4", "15.6", "20.8", "31.25", "41.7", "62.5", "125", "250", "500"]


def block(signature, end="End Sub"):
    start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index(end, start)]


def const(name):
    return int(re.search(rf"^Const {name} = (\d+)$", SOURCE, re.M).group(1))


def epoch(y, m, d):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


# Python mirrors of the MMBasic helpers.
def date_time_to_unix(date_s, time_s):
    d, mo, y = int(date_s[0:2]), int(date_s[3:5]), int(date_s[6:10])
    h, mi, se = int(time_s[0:2]), int(time_s[3:5]), int(time_s[6:8])
    return int(datetime(y, mo, d, h, mi, se, tzinfo=timezone.utc).timestamp())


def pico_clock_valid(date_s, time_s="12:00:00"):
    e = date_time_to_unix(date_s, time_s)
    return const("CLOCK_MIN_EPOCH") <= e < const("CLOCK_MAX_EPOCH")


def is_whole_number(s):
    return 1 <= len(s) <= 6 and all(c in "0123456789" for c in s)


def is_decimal_number(s):
    if not 1 <= len(s) <= 12 or any(c not in "0123456789." for c in s):
        return False
    return s.count(".") <= 1 and any(c.isdigit() for c in s)


def bw_hz(text):
    return int(float(text) * 1000 + 0.5)


class ClockTests(unittest.TestCase):
    def test_window_constants(self):
        self.assertEqual(const("CLOCK_MIN_EPOCH"), epoch(2024, 1, 1))
        self.assertEqual(const("CLOCK_MAX_EPOCH"), epoch(2100, 1, 1))

    def test_unset_pico_clock_is_invalid(self):
        self.assertFalse(pico_clock_valid("01-01-2000", "00:00:00"))
        self.assertFalse(pico_clock_valid("31-12-2023", "23:59:59"))
        self.assertTrue(pico_clock_valid("07-11-2026"))
        self.assertFalse(pico_clock_valid("01-01-2100", "00:00:00"))

    def test_helper_shape(self):
        b = block("Function PicoClockValid()", "End Function")
        self.assertIn("e = DateTimeToUnix(Date$, Time$)", b)
        self.assertIn("If e >= CLOCK_MIN_EPOCH And e < CLOCK_MAX_EPOCH Then", b)

    def test_sync_skips_before_sending_when_clock_invalid(self):
        b = block("Sub DoSyncDeviceTime")
        guard = "If PicoClockValid() = 0 Then"
        self.assertLess(b.index(guard), b.index("SendFrame payload$"))
        self.assertIn("Exit Sub", b[b.index(guard):b.index("SendFrame payload$")])
        self.assertIn("radio clock is already later than the Pico clock", b)
        self.assertNotIn('\\"', SOURCE)  # MMBasic has no backslash escapes

    def test_send_paths_warn_about_unset_clock(self):
        for sub_name in ("Sub DoSendMessage", "Sub DoSendChannelMessage"):
            b = block(sub_name)
            self.assertIn('If PicoClockValid() = 0 Then Print "Warning: Pico clock not set', b, sub_name)


class RadioParamTests(unittest.TestCase):
    def test_frequency_limits_match_firmware(self):
        self.assertEqual(const("RADIO_MIN_FREQ_MHZ") * 1000, 150000)
        self.assertEqual(const("RADIO_MAX_FREQ_MHZ") * 1000, 2500000)

    def test_bandwidth_table_matches_lora_set(self):
        b = block("Function IsLoraBandwidth(bwHz)", "End Function")
        listed = [int(x) for x in re.search(r"Case ([\d, ]+)\n", b).group(1).split(",")]
        self.assertEqual(listed, [bw_hz(k) for k in LORA_BW_KHZ])
        self.assertTrue(all(7000 <= hz <= 500000 for hz in listed))  # firmware range

    def test_number_helpers(self):
        for good in ("869.525", "915", "0.5", "62.5"):
            self.assertTrue(is_decimal_number(good), good)
        for bad in ("", "9 15", "869..5", "1e3", "-915", ".", "869.5.2", "abc"):
            self.assertFalse(is_decimal_number(bad), bad)
        for good in ("7", "12", "22"):
            self.assertTrue(is_whole_number(good), good)
        for bad in ("", "7.5", "-1", "1e1", "1234567"):
            self.assertFalse(is_whole_number(bad), bad)

    def test_helpers_match_source(self):
        whole = block("Function IsWholeNumber(s$)", "End Function")
        self.assertIn("If Len(s$) < 1 Or Len(s$) > 6 Then Exit Function", whole)
        dec = block("Function IsDecimalNumber(s$)", "End Function")
        self.assertIn("If Len(s$) < 1 Or Len(s$) > 12 Then Exit Function", dec)
        self.assertIn("If dots <= 1 And digits >= 1 Then IsDecimalNumber = 1", dec)

    def test_validation_and_confirmation_precede_send(self):
        b = block("Sub DoSetRadioParams")
        send = b.index("SendFrame payload$")
        for needle in ("IsDecimalNumber(freqStr$) = 0 Or IsDecimalNumber(bwStr$) = 0",
                       "IsWholeNumber(sfStr$) = 0 Or IsWholeNumber(crStr$) = 0",
                       "If freqMHz < RADIO_MIN_FREQ_MHZ Or freqMHz > RADIO_MAX_FREQ_MHZ Then",
                       "If IsLoraBandwidth(Int(bwKHz * 1000 + 0.5)) = 0 Then",
                       'If confirm$ <> "APPLY" Then'):
            self.assertLess(b.index(needle), send, needle)
        self.assertIn("freqEnc = Int(freqMHz * 1000 + 0.5)", b)
        self.assertIn("bwEnc   = Int(bwKHz * 1000 + 0.5)", b)

    def test_tx_power_checks_and_confirmation_precede_send(self):
        b = block("Sub DoSetTxPower")
        send = b.index("SendFrame payload$")
        for needle in ("If IsWholeNumber(pwrStr$) = 0 Then",
                       "If gMaxTxPowerVal > 0 And pwrVal > gMaxTxPowerVal Then",
                       'If confirm$ <> "APPLY" Then'):
            self.assertLess(b.index(needle), send, needle)


if __name__ == "__main__":
    unittest.main()

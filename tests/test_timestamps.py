import unittest
from datetime import datetime, timezone

from timestamps import normalize_text, utc_stamp


class TimestampTest(unittest.TestCase):
    def test_utc_stamp_is_rfc3339_with_z(self):
        self.assertEqual(utc_stamp("2026-10-21T19:54:53.751822+00:00"), "2026-10-21T19:54:53Z")
        self.assertEqual(utc_stamp("2026-10-21T14:54:53-05:00"), "2026-10-21T19:54:53Z")
        self.assertEqual(utc_stamp("2026-10-21T19:54:53Z"), "2026-10-21T19:54:53Z")
        self.assertEqual(utc_stamp(datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)), "2026-01-02T03:04:05Z")
        self.assertRegex(utc_stamp(), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_other_values_pass_through(self):
        for value in ("2026-10-21", "unknown", "2026-10-21T19:54:53", 7, 3.5):
            self.assertEqual(utc_stamp(value), value)

    def test_normalize_text(self):
        self.assertEqual(normalize_text('{"a": "2026-10-19T21:12:29.5+00:00", "b": "2026-10-19"}'),
                         '{"a": "2026-10-19T21:12:29Z", "b": "2026-10-19"}')


if __name__ == "__main__":
    unittest.main()

"""Calendar state checks without a display; GUI workflows live in test_ui.py."""

from datetime import date
import unittest
from unittest.mock import Mock

from sunrise.booking_picker import BookingPicker


class CalendarStateTests(unittest.TestCase):
    def picker(self):
        picker = BookingPicker.__new__(BookingPicker)
        picker.today = date(2030, 1, 7)
        picker.day = picker.today
        picker.month = picker.day.replace(day=1)
        picker.cache = {}
        picker.selected_time = ""
        picker.availability = Mock(return_value=["10:00", "10:30"])
        picker.changed = Mock()
        picker.draw_calendar = Mock()
        picker.draw_times = Mock()
        picker.time_buttons = {"10:00": Mock(), "10:30": Mock()}
        picker.summary = Mock()
        return picker

    def test_past_days_do_not_load_availability(self):
        picker = self.picker()
        self.assertEqual(picker.slots(date(2030, 1, 6)), [])
        picker.availability.assert_not_called()

    def test_cache_is_per_date_and_refresh_reloads(self):
        picker = self.picker()
        self.assertEqual(picker.slots(picker.day), ["10:00", "10:30"])
        picker.slots(picker.day)
        picker.availability.assert_called_once_with("2030-01-07")
        picker.selected_time = "10:00"
        picker.refresh()
        self.assertEqual(picker.cache, {})
        self.assertEqual(picker.selected_time, "")
        picker.slots(picker.day)
        self.assertEqual(picker.availability.call_count, 2)

    def test_clicking_day_clears_previous_time(self):
        picker = self.picker()
        picker.selected_time = "10:00"
        picker.choose_day(date(2030, 2, 12))
        self.assertEqual(picker.day, date(2030, 2, 12))
        self.assertEqual(picker.month, date(2030, 2, 1))
        self.assertEqual(picker.selected_time, "")
        picker.changed.assert_called_once()

    def test_only_available_times_can_be_selected(self):
        picker = self.picker()
        picker.choose_time("03:00")
        self.assertEqual(picker.selected_time, "")
        picker.changed.assert_not_called()
        picker.choose_time("10:30")
        self.assertEqual(picker.selected_time, "10:30")
        picker.time_buttons["10:30"].configure.assert_called_with(style="Selected.Time.TButton")
        picker.changed.assert_called_once()

    def test_month_navigation_crosses_year(self):
        picker = self.picker()
        picker.move_month(-1)
        self.assertEqual(picker.month, date(2029, 12, 1))
        picker.move_month(1)
        self.assertEqual(picker.month, date(2030, 1, 1))


if __name__ == "__main__":
    unittest.main()

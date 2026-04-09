from datetime import date
from unittest.mock import patch, MagicMock
from django.test import TestCase
from agents.calendar import occurrencesInWindow, _windowStart, getBirthdays, getDeathdays, getWeddings
from agents.models import Person, PersonName, RomanticRelationship


def make_starred_person(name=None, day_of_birth=None, month_of_birth=None, year_of_birth=None,
                        day_of_death=None, month_of_death=None, year_of_death=None):
    person = Person.objects.create(
        starred=True,
        day_of_birth=day_of_birth,
        month_of_birth=month_of_birth,
        year_of_birth=year_of_birth,
        day_of_death=day_of_death,
        month_of_death=month_of_death,
        year_of_death=year_of_death,
    )
    if name:
        PersonName.objects.create(agent=person, name=name)
    return person


class OccurrencesInWindowTest(TestCase):
    """Tests for occurrencesInWindow() with today mocked to 2026-04-09."""

    def setUp(self):
        # Today: 2026-04-09
        # Window start: 2026-03-09 (1 month back)
        # Window end: 2027-04-09 (1 year ahead)
        self.today = date(2026, 4, 9)
        self.patcher = patch('agents.calendar.date')
        mock_date = self.patcher.start()
        mock_date.today.return_value = self.today
        # Pass through date() constructor calls
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

    def tearDown(self):
        self.patcher.stop()

    def test_event_in_future_included(self):
        # June 15 occurs in 2026 - within window
        result = occurrencesInWindow(15, 6)
        self.assertIn(date(2026, 6, 15), result)

    def test_event_just_past_included(self):
        # March 15, 2026 is within the 1-month lookback (window starts March 9)
        result = occurrencesInWindow(15, 3)
        self.assertIn(date(2026, 3, 15), result)

    def test_event_too_far_past_excluded(self):
        # February 15, 2026 is before window start (March 9, 2026)
        result = occurrencesInWindow(15, 2)
        self.assertNotIn(date(2026, 2, 15), result)

    def test_event_at_window_start_included(self):
        # March 9, 2026 is exactly at the window start
        result = occurrencesInWindow(9, 3)
        self.assertIn(date(2026, 3, 9), result)

    def test_event_at_window_end_included(self):
        # April 9, 2027 is exactly at the window end
        result = occurrencesInWindow(9, 4)
        self.assertIn(date(2027, 4, 9), result)

    def test_event_beyond_window_end_excluded(self):
        # April 15, 2027 is past the window end (April 9, 2027)
        result = occurrencesInWindow(15, 4)
        self.assertNotIn(date(2027, 4, 15), result)

    def test_event_appearing_twice_in_window(self):
        # March 15 appears in 2026 (past) AND 2027 (future) — both in window
        result = occurrencesInWindow(15, 3)
        self.assertIn(date(2026, 3, 15), result)
        self.assertIn(date(2027, 3, 15), result)
        self.assertEqual(len(result), 2)

    def test_feb29_non_leap_year_skipped(self):
        # Feb 29 only appears in leap years; 2025 and 2026 are not leap years
        # 2028 is a leap year but outside the window
        result = occurrencesInWindow(29, 2)
        for d in result:
            self.assertEqual(d.month, 2)
            self.assertEqual(d.day, 29)


class WindowStartEdgeCaseTest(TestCase):
    """Tests _windowStart() handles month-end edge cases."""

    def _window_start_for_today(self, today):
        with patch('agents.calendar.date') as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
            return _windowStart()

    def test_march_31_gives_feb_28_or_29(self):
        result = self._window_start_for_today(date(2026, 3, 31))
        self.assertEqual(result, date(2026, 2, 28))

    def test_march_31_leap_year_gives_feb_29(self):
        result = self._window_start_for_today(date(2028, 3, 31))
        self.assertEqual(result, date(2028, 2, 29))

    def test_jan_15_gives_dec_15_previous_year(self):
        result = self._window_start_for_today(date(2026, 1, 15))
        self.assertEqual(result, date(2025, 12, 15))


class GetBirthdaysTest(TestCase):
    """Tests getBirthdays() filtering with today mocked to 2026-04-09."""

    def setUp(self):
        self.today = date(2026, 4, 9)
        self.patcher = patch('agents.calendar.date')
        mock_date = self.patcher.start()
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

    def tearDown(self):
        self.patcher.stop()

    def test_birthday_in_window_included(self):
        make_starred_person('Alice', day_of_birth=15, month_of_birth=6)
        birthdays = getBirthdays()
        self.assertEqual(len(birthdays), 1)
        self.assertIn('Alice', birthdays[0]['label'])

    def test_birthday_before_birth_year_excluded(self):
        # Person born in 2027 — their March 2026 birthday should be excluded
        # but their April 2027 one is in the window and >= birth year
        # Only occurrence in window that satisfies year_of_birth filter should appear
        make_starred_person('Future', day_of_birth=15, month_of_birth=3, year_of_birth=2027)
        birthdays = getBirthdays()
        # March 15, 2026 is in window but 2026 < 2027, so excluded
        # March 15, 2027 is in window and 2027 >= 2027, so included
        self.assertEqual(len(birthdays), 1)
        self.assertEqual(birthdays[0]['date'], date(2027, 3, 15))

    def test_birthday_both_occurrences_after_birth_year(self):
        # Born in 2020 — both 2026 and 2027 occurrences should appear
        make_starred_person('Older', day_of_birth=15, month_of_birth=3, year_of_birth=2020)
        birthdays = getBirthdays()
        dates = [b['date'] for b in birthdays]
        self.assertIn(date(2026, 3, 15), dates)
        self.assertIn(date(2027, 3, 15), dates)

    def test_no_birth_year_shows_all_occurrences_in_window(self):
        make_starred_person('NoBirthYear', day_of_birth=15, month_of_birth=3)
        birthdays = getBirthdays()
        # Both 2026 and 2027 should be included since no year restriction
        self.assertEqual(len(birthdays), 2)

    def test_unstarred_person_excluded(self):
        person = Person.objects.create(starred=False, day_of_birth=15, month_of_birth=6)
        PersonName.objects.create(agent=person, name='Unstarred')
        birthdays = getBirthdays()
        self.assertEqual(len(birthdays), 0)

    def test_ordinal_label_reflects_occurrence_year(self):
        # Born in 2000; March 15, 2026 = 26th birthday; 2027 = 27th
        make_starred_person('Ordinal', day_of_birth=15, month_of_birth=3, year_of_birth=2000)
        birthdays = getBirthdays()
        labels = {b['date']: b['label'] for b in birthdays}
        self.assertIn('26th', labels[date(2026, 3, 15)])
        self.assertIn('27th', labels[date(2027, 3, 15)])

    def test_uid_includes_year(self):
        make_starred_person('UidTest', day_of_birth=15, month_of_birth=3)
        birthdays = getBirthdays()
        uids = [b['uid'] for b in birthdays]
        self.assertTrue(any('2026' in uid for uid in uids))
        self.assertTrue(any('2027' in uid for uid in uids))


class GetDeathdaysTest(TestCase):
    """Tests getDeathdays() filtering with today mocked to 2026-04-09."""

    def setUp(self):
        self.today = date(2026, 4, 9)
        self.patcher = patch('agents.calendar.date')
        mock_date = self.patcher.start()
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

    def tearDown(self):
        self.patcher.stop()

    def test_deathday_in_window_included(self):
        make_starred_person('Bob', day_of_death=15, month_of_death=6, year_of_death=2020)
        deathdays = getDeathdays()
        self.assertEqual(len(deathdays), 1)
        self.assertIn('Bob', deathdays[0]['label'])

    def test_deathday_before_death_year_excluded(self):
        # Died in 2026 on May 1 — the 2025 occurrence should not appear
        # window includes May 1, 2026 and May 1, 2027 (both after death year 2026)
        make_starred_person('Recent', day_of_death=1, month_of_death=5, year_of_death=2026)
        deathdays = getDeathdays()
        dates = [d['date'] for d in deathdays]
        self.assertNotIn(date(2025, 5, 1), dates)
        self.assertIn(date(2026, 5, 1), dates)

    def test_deathday_continues_after_death(self):
        # Events continue to appear for years after someone died
        make_starred_person('Continued', day_of_death=15, month_of_death=3, year_of_death=2010)
        deathdays = getDeathdays()
        # Both 2026 and 2027 occurrences should appear
        self.assertEqual(len(deathdays), 2)

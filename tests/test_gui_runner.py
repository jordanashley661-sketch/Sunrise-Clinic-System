"""Verify test evidence never reports a native crash or incomplete case as PASS."""

import unittest
from run_gui_tests import assess_case


class RunnerTests(unittest.TestCase):
    def result(self, **changes):
        row = dict(
            test="example", tests_run=1, failures=0, errors=0, skipped=0, issues=[]
        )
        row.update(changes)
        return row

    def test_complete_success_passes(self):
        self.assertEqual(assess_case("example", 0, self.result())[0], "PASS")

    def test_native_crash_after_passing_assertion_is_error(self):
        self.assertEqual(assess_case("example", -5, self.result())[0], "ERROR")

    def test_missing_result_is_error(self):
        self.assertEqual(assess_case("example", 0, None)[0], "ERROR")

    def test_wrong_case_is_error(self):
        self.assertEqual(assess_case("other", 0, self.result())[0], "ERROR")

    def test_incomplete_case_is_error(self):
        self.assertEqual(
            assess_case("example", 0, self.result(tests_run=0))[0], "ERROR"
        )

    def test_missing_counters_are_error(self):
        self.assertEqual(
            assess_case("example", 0, dict(test="example", tests_run=1))[0], "ERROR"
        )

    def test_failure_and_error_are_preserved(self):
        self.assertEqual(assess_case("example", 1, self.result(failures=1))[0], "FAIL")
        self.assertEqual(assess_case("example", 1, self.result(errors=1))[0], "ERROR")

    def test_skipped_case_is_not_a_pass(self):
        self.assertEqual(assess_case("example", 0, self.result(skipped=1))[0], "ERROR")

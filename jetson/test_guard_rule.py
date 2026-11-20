import unittest

from guard_rule import PhoneRule


def run(rule, frames):
    """frames: list of (person, phone, dt). Returns the alert after each frame."""
    return [rule.update(p, ph, dt) for p, ph, dt in frames]


class PhoneRuleTest(unittest.TestCase):
    def test_alert_after_three_seconds_together(self):
        out = run(PhoneRule(hold=3.0), [(True, True, 0.1)] * 30)
        self.assertFalse(out[28])
        self.assertTrue(out[29])  # 30 x 0.1 = 3.0s

    def test_phone_passing_through_does_not_alert(self):
        out = run(PhoneRule(hold=3.0), [(True, True, 0.1)] * 20 + [(True, False, 0.1)] * 10)
        self.assertFalse(any(out))

    def test_short_dropout_is_forgiven_and_counted(self):
        frames = [(True, True, 0.1)] * 20 + [(True, False, 0.1)] * 3 + [(True, True, 0.1)] * 10
        out = run(PhoneRule(hold=3.0), frames)
        self.assertFalse(out[20 + 3 + 3])  # 2.0 + 0.3 + 0.4 = 2.7s, not yet
        self.assertTrue(out[20 + 3 + 8])   # the 0.3s dropout counted towards the 3s

    def test_long_dropout_resets_the_count(self):
        frames = [(True, True, 0.1)] * 25 + [(True, False, 0.1)] * 17 + [(True, True, 0.1)] * 10
        self.assertFalse(any(run(PhoneRule(hold=3.0), frames)))  # 1.7s > 1.5s gap

    def test_alert_stays_through_a_short_miss_then_clears_when_phone_leaves(self):
        frames = [(True, True, 0.1)] * 35 + [(True, False, 0.1)] * 20
        out = run(PhoneRule(hold=3.0), frames)
        self.assertTrue(out[34])
        self.assertTrue(out[35 + 9])   # 1.0s of misses is forgiven
        self.assertFalse(out[-1])      # 2.0s of misses is not

    def test_alert_clears_when_person_leaves(self):
        frames = [(True, True, 0.1)] * 35 + [(False, False, 0.1)] * 20
        out = run(PhoneRule(hold=3.0), frames)
        self.assertTrue(out[34])
        self.assertFalse(out[-1])

    def test_default_hold_is_one_second_and_ignores_a_brief_pass(self):
        out = run(PhoneRule(), [(True, True, 0.1)] * 11)
        self.assertTrue(out[-1])  # just over 1.0s
        brief = run(PhoneRule(), [(True, True, 0.1)] * 4 + [(True, False, 0.1)] * 20)
        self.assertFalse(any(brief))  # a 0.4s pass does not alert

    def test_phone_without_person_never_alerts(self):
        self.assertFalse(any(run(PhoneRule(hold=3.0), [(False, True, 0.1)] * 100)))


if __name__ == "__main__":
    unittest.main()

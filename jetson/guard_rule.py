"""The phone rule: person + phone seen together for `hold` seconds (default 1.0, was 3.0 in the proposal). Pure logic, no Jetson imports, so it can be tested on a laptop.
Written to run on Python 3.6 (JetPack 4.6)."""


class PhoneRule:
    def __init__(self, hold=1.0, gap=1.5):
        self.hold = hold  # seconds person+phone must be seen together
        self.gap = gap    # longest dropout that is forgiven; a longer one resets the count
        self.together = 0.0
        self.missed = 0.0

    def update(self, person, phone, dt):
        """Feed one frame. Returns True while the alert should be on."""
        if person and phone:
            if self.missed <= self.gap:
                self.together += self.missed  # a forgiven dropout counts as time together
            self.together += dt
            self.missed = 0.0
        else:
            self.missed += dt
            if self.missed > self.gap:
                self.together = 0.0
        return self.together >= self.hold

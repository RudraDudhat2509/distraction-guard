// Distraction Guard - Arduino side.
// Jetson sends one byte over USB serial: 'R' = phone alert, 'G' = all fine.
const int GREEN = 8;
const int RED = 9;
const int BUZZER = 10;

void show(bool alert) {
  digitalWrite(GREEN, alert ? LOW : HIGH);
  digitalWrite(RED, alert ? HIGH : LOW);
  if (alert) tone(BUZZER, 2000);  // passive buzzer needs a tone, not a steady HIGH
  else noTone(BUZZER);
}

void setup() {
  pinMode(GREEN, OUTPUT);
  pinMode(RED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  Serial.begin(9600);
  show(false);
}

void loop() {
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == 'R') show(true);
    else if (c == 'G') show(false);
  }
}

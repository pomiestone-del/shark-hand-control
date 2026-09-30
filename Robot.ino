#include <Servo.h>
#include <string.h>

Servo head;
Servo mouth;
const byte HEAD_PIN = 9;
const byte MOUTH_PIN = 10;
// Wider range, with direction reversed relative to the original mapping.
const int HEAD_LEFT = 120;
const int HEAD_RIGHT = 60;
// Preserve Servo.write() endpoint pulses without rounding every command to degrees.
const int HEAD_LEFT_US = MIN_PULSE_WIDTH + (long)(MAX_PULSE_WIDTH - MIN_PULSE_WIDTH) * HEAD_LEFT / 180;
const int HEAD_RIGHT_US = MIN_PULSE_WIDTH + (long)(MAX_PULSE_WIDTH - MIN_PULSE_WIDTH) * HEAD_RIGHT / 180;
const int MOUTH_CLOSED = 180;
const int MOUTH_OPEN = 0;
const int MOUTH_CLOSED_US = MIN_PULSE_WIDTH + (long)(MAX_PULSE_WIDTH - MIN_PULSE_WIDTH) * MOUTH_CLOSED / 180;
const int MOUTH_OPEN_US = MIN_PULSE_WIDTH + (long)(MAX_PULSE_WIDTH - MIN_PULSE_WIDTH) * MOUTH_OPEN / 180;
const unsigned long COMMAND_TIMEOUT_MS = 500;

unsigned long lastCommand = 0;
bool active = false;
char command[12];
byte length = 0;
bool overflow = false;

void stopMotion() {
  active = false;
}

void processCommand() {
  command[length] = '\0';
  if (strcmp(command, "?") == 0) {
    Serial.println(F("SHARK_READY"));
  } else if (strcmp(command, "S") == 0) {
    stopMotion();
    Serial.println(F("STOPPED"));
  } else if ((command[0] == 'H' || command[0] == 'M') && length >= 2 && length <= 5) {
    int position = 0;
    for (byte i = 1; i < length; ++i) {
      if (command[i] < '0' || command[i] > '9') return;
      position = position * 10 + command[i] - '0';
    }
    if (position > 1000) return;
    if (command[0] == 'M') {
      int pulse = map(position, 0, 1000, MOUTH_CLOSED_US, MOUTH_OPEN_US);
      mouth.writeMicroseconds(pulse);
      if (!mouth.attached()) mouth.attach(MOUTH_PIN);
      lastCommand = millis();
      active = true;
      Serial.print(F("MOK "));
      Serial.print(MOUTH_CLOSED + (MOUTH_OPEN - MOUTH_CLOSED) * (position / 1000.0f), 2);
      Serial.print(' ');
      Serial.println(mouth.readMicroseconds());
      return;
    }
    int targetPulse = map(position, 0, 1000, HEAD_LEFT_US, HEAD_RIGHT_US);
    if (!head.attached()) {
      // Start at the first hand command, never at an imposed center position.
      head.writeMicroseconds(targetPulse);
      head.attach(HEAD_PIN);
    }
    // Apply the latest hand position directly; no software speed ramp.
    head.writeMicroseconds(targetPulse);
    lastCommand = millis();
    active = true;
    Serial.print(F("OK "));
    Serial.print(HEAD_LEFT + (HEAD_RIGHT - HEAD_LEFT) * (position / 1000.0f), 2);
    Serial.print(' ');
    Serial.println(head.readMicroseconds()); // Commanded pulse, not physical feedback.
  }
}

void setup() {
  // Leave both outputs disabled until valid hand commands arrive.
  Serial.begin(115200);
  Serial.println(F("SHARK_READY"));
}

void loop() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      if (!overflow && length) processCommand();
      length = 0;
      overflow = false;
    } else if (length < sizeof(command) - 1 && !overflow) {
      command[length++] = ch;
    } else {
      overflow = true;
    }
  }
  unsigned long now = millis();
  if (active && now - lastCommand > COMMAND_TIMEOUT_MS) stopMotion();
}

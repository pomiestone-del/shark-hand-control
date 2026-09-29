#include <Servo.h>
#include <string.h>

Servo head;
Servo mouth;
const byte HEAD_PIN = 9;
const byte MOUTH_PIN = 10;
// Wider range, with direction reversed relative to the original mapping.
const int HEAD_LEFT = 120;
const int HEAD_RIGHT = 60;
const int HEAD_CENTER = 90;
const int MOUTH_HOLD_US = 1500;
const unsigned long COMMAND_TIMEOUT_MS = 500;

int currentAngle = HEAD_CENTER;
int targetAngle = HEAD_CENTER;
unsigned long lastCommand = 0;
bool active = false;
char command[12];
byte length = 0;
bool overflow = false;

void stopMotion() {
  targetAngle = currentAngle;
  active = false;
}

void processCommand() {
  command[length] = '\0';
  if (strcmp(command, "?") == 0) {
    Serial.println(F("SHARK_READY"));
  } else if (strcmp(command, "S") == 0) {
    stopMotion();
    Serial.println(F("STOPPED"));
  } else if (command[0] == 'H' && length >= 2 && length <= 5) {
    int position = 0;
    for (byte i = 1; i < length; ++i) {
      if (command[i] < '0' || command[i] > '9') return;
      position = position * 10 + command[i] - '0';
    }
    if (position > 1000) return;
    targetAngle = map(position, 0, 1000, HEAD_LEFT, HEAD_RIGHT);
    if (!head.attached()) {
      // Start at the first hand command, never at an imposed center position.
      currentAngle = targetAngle;
      head.write(currentAngle);
      head.attach(HEAD_PIN);
    }
    // Apply the latest hand position directly; no software speed ramp.
    currentAngle = targetAngle;
    head.write(currentAngle);
    lastCommand = millis();
    active = true;
    Serial.print(F("OK "));
    Serial.println(targetAngle);
  }
}

void setup() {
  // Leave head output disabled until the first valid hand command.
  mouth.writeMicroseconds(MOUTH_HOLD_US);
  mouth.attach(MOUTH_PIN);
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

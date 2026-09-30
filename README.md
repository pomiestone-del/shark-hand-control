# Shark Head Gesture Control

English | [简体中文](README.zh-CN.md)

Control a two-servo shark head with a webcam, MediaPipe Hand Landmarker, and an Arduino Uno. Move one hand horizontally to steer the head; open or close your fingers to control the mouth. Camera frames are processed locally and are not recorded or uploaded.

## Current status

This is a development snapshot, not a verified working release. The current source has two known issues:

1. `hand_preview.py` uses the nonexistent OpenCV constant `FONT_HERSHEY_pySIMPLEX` when drawing calibration buttons. It must be `FONT_HERSHEY_SIMPLEX`; otherwise the application raises an error when that line runs, including in preview mode.
2. The firmware sets the mouth to **180° when closed and 0° when open**, but the Python `Mouth target` overlay still calculates a **120° to 0°** range. The firmware determines the output; the overlay is inconsistent.

Intermittent or absent physical head movement remains unresolved. Previous firmware builds, uploads, and serial acknowledgments succeeded, but these do not prove that a servo moved. Fix the startup issue and reconcile the intended mouth range before relying on the run instructions below.

## Hardware and mapping

| Component | Connection / behavior |
|---|---|
| Controller | Arduino Uno, default USB port `COM7` |
| Head servo | Signal on **D9** |
| Mouth servo | Signal on **D10** |
| Camera | Computer webcam, index `0` by default |
| Head mapping | Mirrored image left → 120°, center → 90°, right → 60° |
| Mouth mapping in firmware | Fist → 180°, fully open hand → 0°, continuous values between them |

The head uses the central 70% of the image width, with positions outside that region clamped to the endpoints. `--reverse` reverses the head mapping only.

Match the servo supply voltage and available current to the actual servo specifications. An external servo supply and the Uno must share ground. The configured degree values are command labels, not measured mechanical angles; check the usable range of the mechanism.

## Files

| File | Purpose |
|---|---|
| `Robot.ino` | Firmware uploaded to the Uno |
| `hand_preview.py` | Camera, hand tracking, display, and serial control |
| `hand_mapping.py` | Finger-bend estimation and continuous mouth mapping |
| `hand_landmarker.task` | Local MediaPipe hand model |
| `start-control.cmd` | Start control on COM7 |
| `start-reversed.cmd` | Start with the head direction reversed |
| `start-preview.cmd` | Camera preview without serial control |
| `requirements.txt` | Pinned direct Python dependencies |
| `MODEL.md` | Model source and checksum |
| `.gitignore` | Excludes environments, caches, and logs from Git |

## Setup

The project was developed on Windows with Python 3.10, Arduino AVR core 1.8.8, and Servo library 1.3.0. A clean dependency installation has not been independently verified.

The repository is private and requires access. Clone into a directory named `Robot` so the folder matches the Arduino sketch name:

```powershell
git clone https://github.com/pomiestone-del/shark-hand-control.git Robot
cd Robot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`opencv-contrib-python` supplies `cv2`; do not install an additional OpenCV distribution into the same environment.

Open `Robot.ino` in Arduino IDE, install the **Servo** library and **Arduino Uno** board support, select the actual USB port, and upload. Close Serial Monitor and Serial Plotter before starting Python. Editing the sketch on the computer does not update the board until it is uploaded.

## Run

After addressing the known issues above, run from the project folder in PowerShell or Cursor Terminal:

```powershell
# Control both servos
.\.venv\Scripts\python.exe hand_preview.py --port COM7

# Camera-only preview
.\.venv\Scripts\python.exe hand_preview.py --preview

# Reverse the head direction
.\.venv\Scripts\python.exe hand_preview.py --port COM7 --reverse

# Use another camera
.\.venv\Scripts\python.exe hand_preview.py --port COM7 --camera 1

# Print tracking and acknowledgment diagnostics
.\.venv\Scripts\python.exe hand_preview.py --port COM7 --diagnostics
```

If the dependencies are installed in your system Python, you can use `python` in place of `.\.venv\Scripts\python.exe`.

The `.cmd` launchers prefer the project's `.venv` when present, otherwise they use `python` from PATH. Do not run multiple control windows simultaneously. Press **Q**, **Esc**, or close the camera window to exit.

## Mouth calibration

The application estimates openness from the average PIP joint angle of the four fingers, excluding the thumb. It prefers MediaPipe's 3D world landmarks. Default calibration uses 70° for a fist and 165° for an open hand; this is a geometric estimate and can be affected by occlusion.

With the camera window focused:

1. Hold a fist in view and press **C**, or click **FIST**.
2. Open your hand and press **O**, or click **OPEN**.
3. Check for `FIST SAVED` / `OPEN SAVED`. `NOT SAVED` explains a rejected calibration.

Uppercase and lowercase keys work. Calibration applies only to the current session, and the two calibration values must differ by at least 20°. The default mapping can be used without calibration once the startup issue is fixed.

## Control behavior

- Both servo outputs stay disabled after board startup until their first valid position commands.
- Positions map directly to microsecond pulses, without software smoothing or a speed ramp. Command transmission is capped at 50 updates per second; actual rates depend on frame processing.
- Losing the hand or exiting sends `S`, which stops target updates but **does not detach or power off the servos**. They can continue toward, or hold, the last target.
- The firmware's 500 ms command timeout similarly retains the last pulse output. It is not an emergency stop.
- An observed board restart or missing acknowledgments during tracking causes the Python application to exit rather than reconnect automatically.
- `Arduino target` and `Arduino mouth` show acknowledged commands, not position-sensor measurements.

## Serial protocol

115200 baud, ASCII commands terminated by a newline:

| Command | Meaning / reply |
|---|---|
| `?` | Identity query → `SHARK_READY` |
| `H0` … `H1000` | Normalized head position → `OK <angle> <pulse_us>` |
| `M0` … `M1000` | Mouth openness: 0 = fist, 1000 = open → `MOK <angle> <pulse_us>` |
| `S` | Retain the last output → `STOPPED` |

Current calculated endpoints: head `H0` → 120° / 1781 µs and `H1000` → 60° / 1162 µs; mouth `M0` → 180° / 2400 µs and `M1000` → 0° / 544 µs.

## Troubleshooting

| Symptom | Check |
|---|---|
| OpenCV font constant error | Correct `FONT_HERSHEY_pySIMPLEX` as described above |
| COM7 missing | Reconnect the board and check its actual port in Arduino IDE |
| Port access denied | Close Serial Monitor, Serial Plotter, and other control processes |
| `programmer is not responding` | The upload failed; the new firmware is not confirmed installed |
| No `SHARK_READY` | Verify the selected port and upload the matching `Robot.ino` |
| Camera cannot open | Close other camera apps or try `--camera 1` |
| Hand detected but no motion | Check `USB CONTROL` and whether acknowledged angles change; this does not by itself verify power, wiring, or movement |
| Persistent buzzing, heating, or a blocked mechanism | Disconnect servo power before inspecting the mechanism and supply; do not force a powered shaft |

To change limits, edit the `HEAD_LEFT`, `HEAD_RIGHT`, `MOUTH_CLOSED`, and `MOUTH_OPEN` constants, update any corresponding display calculation, and upload the firmware again. With the current Servo library, `Servo.write(190)` is clamped to 180; a wider physical range requires model-specific pulse calibration.

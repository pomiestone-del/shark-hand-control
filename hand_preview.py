"""Hand control on COM7 by default; use --preview for camera-only mode."""
import argparse
from pathlib import Path
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from hand_mapping import finger_extension, mouth_openness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--reverse', action='store_true', help='Reverse angle mapping')
    parser.add_argument('--port', default='COM7', help='Arduino USB port (default COM7)')
    parser.add_argument('--preview', action='store_true', help='Camera only, no servo commands')
    parser.add_argument('--diagnostics', action='store_true', help='Print tracking and command confirmations every 2 seconds')
    args = parser.parse_args()
    options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(Path(__file__).with_name('hand_landmarker.task'))),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    camera = cv2.VideoCapture(args.camera)
    angle = None
    previous_stamp = -1
    seen_time = None
    connection = None
    last_send = 0.0
    receive_buffer = b''
    acknowledged_angle = None
    acknowledged_pulse = None
    acknowledged_mouth = None
    last_mouth_ack = time.monotonic()
    closed_extension, open_extension = 70.0, 165.0
    last_ack = time.monotonic()
    stop_sent = False
    last_report = 0.0
    window_name = 'Shark hand tracking'
    pending_actions = []
    button_boxes = {}
    calibration_message = 'Click FIST / OPEN buttons, or focus this window and press C / O'

    def on_mouse(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            for action, (x1, y1, x2, y2) in button_boxes.items():
                if x1 <= x <= x2 and y1 <= y <= y2:
                    pending_actions.append(action)

    try:
        if not camera.isOpened():
            raise RuntimeError('Cannot open webcam. Close other camera apps or try --camera 1.')
        if not args.preview:
            import serial
            connection = serial.Serial(args.port, 115200, timeout=0.2, write_timeout=0.5)
            # Uno usually resets when its serial port opens. Require our firmware.
            time.sleep(2.0)
            connection.reset_input_buffer()
            connection.write(b'?\n')
            deadline = time.monotonic() + 6
            ready = False
            while time.monotonic() < deadline:
                if connection.readline().strip() == b'SHARK_READY':
                    ready = True
                    break
            if not ready:
                raise RuntimeError('Arduino did not identify itself. Upload the supplied Robot firmware first.')
            print(f'Arduino ready on {args.port}. Move hand to steer; open/fist for mouth. C/O calibrate fist/open; Q quits.', flush=True)
            last_ack = time.monotonic()
            last_mouth_ack = last_ack
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, on_mouse)
        with vision.HandLandmarker.create_from_options(options) as detector:
            while True:
                ok, frame = camera.read()
                for _ in range(5):
                    if ok:
                        break
                    time.sleep(0.05)
                    ok, frame = camera.read()
                if not ok:
                    raise RuntimeError('Webcam frame unavailable. Check camera connection.')
                # Mirror the display so your physical left is screen left.
                frame = cv2.flip(frame, 1)
                now = time.monotonic()
                stamp = max(previous_stamp + 1, int(now * 1000))
                previous_stamp = stamp
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), stamp)
                if connection is not None and connection.in_waiting:
                    # Buffer complete lines so split USB packets cannot hide resets.
                    receive_buffer += connection.read(connection.in_waiting)
                    while b'\n' in receive_buffer:
                        line, receive_buffer = receive_buffer.split(b'\n', 1)
                        line = line.strip()
                        if line == b'SHARK_READY':
                            raise RuntimeError('Arduino restarted during control. Head output is disabled; check power/USB.')
                        if line.startswith(b'OK '):
                            fields = line.split()
                            acknowledged_angle = float(fields[1])
                            acknowledged_pulse = int(fields[2]) if len(fields) > 2 else None
                            last_ack = now
                        elif line.startswith(b'MOK '):
                            acknowledged_mouth = float(line.split()[1])
                            last_mouth_ack = now
                height, width = frame.shape[:2]
                extension = None
                if result.hand_landmarks:
                    hand = result.hand_landmarks[0]
                    geometry = result.hand_world_landmarks[0] if result.hand_world_landmarks else hand
                    extension = finger_extension(geometry)
                    openness = mouth_openness(extension, closed_extension, open_extension) if extension is not None else None
                    palm_x = sum(hand[i].x for i in (0, 5, 9, 13, 17)) / 5
                    x = max(0.0, min(1.0, (palm_x - 0.15) / 0.70))
                    target = 60.0 + 60.0 * (1.0 - x if args.reverse else x)
                    # Direct position mapping: no interpolation or speed limit.
                    angle = target
                    if connection is not None and now - last_send >= 0.02:
                        position = max(0, min(1000, round((angle - 60) / 60 * 1000)))
                        commands = f'H{position}\n'
                        if openness is not None:
                            commands += f'M{round(openness * 1000)}\n'
                        connection.write(commands.encode('ascii'))
                        last_send = now
                        if seen_time is None:
                            last_ack = now
                            last_mouth_ack = now
                        stop_sent = False
                    if connection is not None and now - last_ack > 2.0:
                        raise RuntimeError('No Arduino acknowledgment for 2 seconds. Control stopped.')
                    if connection is not None and openness is not None and now - last_mouth_ack > 2.0:
                        raise RuntimeError('No mouth acknowledgment. Upload the new mouth-control firmware.')
                    seen_time = now
                    direction = 'LEFT' if palm_x < 0.43 else 'RIGHT' if palm_x > 0.57 else 'CENTER'
                    status = f'{direction} | Position: {(angle - 60) / 60 * 100:.0f}%'
                    for point in hand:
                        cv2.circle(frame, (int(point.x * width), int(point.y * height)), 4, (0, 255, 100), -1)
                    cv2.line(frame, (int(palm_x * width), 80), (int(palm_x * width), height), (0, 220, 255), 2)
                    if openness is not None:
                        cv2.putText(frame, f'Hand open: {openness:.0%} | Mouth target: {120*(1-openness):.1f} deg', (15, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 100), 1)
                else:
                    if connection is not None and not stop_sent:
                        connection.write(b'S\n')
                        stop_sent = True
                    seen_time = None
                    status = 'NO HAND | Holding position'
                    if seen_time is None or now - seen_time > 0.5:
                        status = 'NO HAND | Control inactive'
                cv2.putText(frame, status, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 100), 2)
                mode = 'USB CONTROL' if connection is not None else 'PREVIEW ONLY'
                cv2.putText(frame, f'{mode} | Q / Esc to quit', (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2)
                if connection is not None:
                    ack = 'waiting for hand' if acknowledged_angle is None else f'{acknowledged_angle:.2f} deg'
                    if acknowledged_pulse is not None:
                        ack += f' / {acknowledged_pulse} us'
                    ack += ' (command)'
                    cv2.putText(frame, f'Arduino target: {ack}', (15, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 255), 1)
                    if acknowledged_mouth is not None:
                        cv2.putText(frame, f'Arduino mouth: {acknowledged_mouth:.2f} deg (command)', (15, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 255), 1)
                if args.diagnostics and now - last_report >= 2.0:
                    print(f'TRACK hand={bool(result.hand_landmarks)} finger={extension} head_ack={acknowledged_angle} mouth_ack={acknowledged_mouth} head_ack_age={now-last_ack:.2f}s mouth_ack_age={now-last_mouth_ack:.2f}s', flush=True)
                    last_report = now
                score_text = 'No valid hand detected' if extension is None else f'Finger angle: {extension:.1f} | Fist: {closed_extension:.1f} | Open: {open_extension:.1f}'
                cv2.putText(frame, score_text, (15, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 220, 255), 1)
                cv2.rectangle(frame, (0, height - 105), (width, height), (25, 25, 25), -1)
                cv2.putText(frame, calibration_message, (12, height - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (0, 255, 255), 1)
                button_boxes.clear()
                for action, x1, x2, label in [('c', 15, 215, 'FIST (C)'), ('o', 230, 430, 'OPEN (O)')]:
                    button_boxes[action] = (x1, height - 60, x2, height - 20)
                    cv2.rectangle(frame, (x1, height - 60), (x2, height - 20), (100, 80, 40), -1)
                    cv2.putText(frame, label, (x1 + 15, height - 34), cv2.FONT_HERSHEY_pySIMPLEX, 0.6, (255, 255, 255), 1)
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), ord('Q'), 27):
                    break
                if key in (ord('c'), ord('C'), ord('o'), ord('O')):
                    pending_actions.append(chr(key).lower())
                while pending_actions:
                    action = pending_actions.pop(0)
                    if extension is None:
                        calibration_message = 'NOT SAVED: show your whole hand to the camera'
                    elif action == 'c' and open_extension - extension >= 20:
                        closed_extension = extension
                        calibration_message = f'FIST SAVED: {extension:.1f}. Now open hand and click OPEN.'
                    elif action == 'o' and extension - closed_extension >= 20:
                        open_extension = extension
                        calibration_message = f'OPEN SAVED: {extension:.1f}. Calibration active this session.'
                    elif action == 'c':
                        calibration_message = 'NOT SAVED: curl fingers more, or calibrate OPEN first'
                    else:
                        calibration_message = 'NOT SAVED: straighten fingers more, or calibrate FIST first'
                    print(calibration_message, flush=True)
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
    finally:
        if connection is not None:
            try:
                connection.write(b'S\n')
            except Exception:
                pass
            finally:
                connection.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

"""Hand control on COM7 by default; use --preview for camera-only mode."""
import argparse
from pathlib import Path
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--reverse', action='store_true', help='Reverse angle mapping')
    parser.add_argument('--port', default='COM7', help='Arduino USB port (default COM7)')
    parser.add_argument('--preview', action='store_true', help='Camera only, no servo commands')
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
    last_ack = time.monotonic()
    stop_sent = False
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
            print(f'Arduino ready on {args.port}. Move one hand left/right; Q or Esc quits.', flush=True)
            last_ack = time.monotonic()
        with vision.HandLandmarker.create_from_options(options) as detector:
            while True:
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
                            acknowledged_angle = int(line[3:])
                            last_ack = now
                height, width = frame.shape[:2]
                if result.hand_landmarks:
                    hand = result.hand_landmarks[0]
                    palm_x = sum(hand[i].x for i in (0, 5, 9, 13, 17)) / 5
                    x = max(0.0, min(1.0, (palm_x - 0.15) / 0.70))
                    target = 60.0 + 60.0 * (1.0 - x if args.reverse else x)
                    # Direct position mapping: no interpolation or speed limit.
                    angle = target
                    if connection is not None and now - last_send >= 0.02:
                        position = max(0, min(1000, round((angle - 60) / 60 * 1000)))
                        connection.write(f'H{position}\n'.encode('ascii'))
                        last_send = now
                        if seen_time is None:
                            last_ack = now
                        stop_sent = False
                    if connection is not None and now - last_ack > 2.0:
                        raise RuntimeError('No Arduino acknowledgment for 2 seconds. Control stopped.')
                    seen_time = now
                    direction = 'LEFT' if palm_x < 0.43 else 'RIGHT' if palm_x > 0.57 else 'CENTER'
                    status = f'{direction} | Position: {(angle - 60) / 60 * 100:.0f}%'
                    for point in hand:
                        cv2.circle(frame, (int(point.x * width), int(point.y * height)), 4, (0, 255, 100), -1)
                    cv2.line(frame, (int(palm_x * width), 80), (int(palm_x * width), height), (0, 220, 255), 2)
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
                    ack = 'waiting for hand' if acknowledged_angle is None else f'{acknowledged_angle} deg (command, not sensor)'
                    cv2.putText(frame, f'Arduino target: {ack}', (15, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 255), 1)
                cv2.imshow('Shark hand tracking', frame)
                if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                    break
                if cv2.getWindowProperty('Shark hand tracking', cv2.WND_PROP_VISIBLE) < 1:
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

import cv2
import numpy as np
import mediapipe as mp
from collections import deque

# Face landmarks used for a lightweight head-pose estimate.
mp_face = mp.solutions.face_mesh

NOSE_TIP = 1
CHIN = 152
LEFT_EYE_OUTER = 33
RIGHT_EYE_OUTER = 263
LEFT_MOUTH = 61
RIGHT_MOUTH = 291

# Eye landmark sets used to compute EAR (eye aspect ratio).
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def dist(a, b) -> float:
    return float(np.linalg.norm(a - b))


def eye_ear(pts, eye_idx) -> float:
    """
    EAR drops when the eye closes.
    Using a ratio helps reduce sensitivity to distance from the camera.
    """
    p1 = pts[eye_idx[0]]
    p2 = pts[eye_idx[1]]
    p3 = pts[eye_idx[2]]
    p4 = pts[eye_idx[3]]
    p5 = pts[eye_idx[4]]
    p6 = pts[eye_idx[5]]
    return (dist(p2, p6) + dist(p3, p5)) / (2.0 * dist(p1, p4) + 1e-6)


def wrap_human_angle(deg: float) -> float:
    """
    Keeps angles in a stable range so left/right doesn't flip near 180 degrees.
    """
    deg = (deg + 180.0) % 360.0 - 180.0
    if deg > 90.0:
        deg -= 180.0
    elif deg < -90.0:
        deg += 180.0
    return deg


def head_pose_pnp(pts_2d: np.ndarray, w: int, h: int):
    """
    Estimates pitch/yaw/roll using a small set of face points.
    Two-step solvePnP improves stability compared to a single pass.
    """
    image_points = np.array([
        pts_2d[NOSE_TIP],
        pts_2d[CHIN],
        pts_2d[LEFT_EYE_OUTER],
        pts_2d[RIGHT_EYE_OUTER],
        pts_2d[LEFT_MOUTH],
        pts_2d[RIGHT_MOUTH],
    ], dtype=np.float64)

    model_points = np.array([
        (0.0,   0.0,   0.0),
        (0.0, -63.6, -12.5),
        (-43.3, 32.7, -26.0),
        (43.3,  32.7, -26.0),
        (-28.9, -28.9, -24.1),
        (28.9,  -28.9, -24.1),
    ], dtype=np.float64)

    focal = w
    center = (w / 2.0, h / 2.0)
    camera_matrix = np.array([
        [focal, 0, center[0]],
        [0, focal, center[1]],
        [0, 0, 1]
    ], dtype=np.float64)

    dist_coeffs = np.zeros((4, 1), dtype=np.float64)

    ok, rvec, tvec = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_EPNP
    )
    if not ok:
        return None

    ok, rvec, tvec = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist_coeffs,
        rvec=rvec, tvec=tvec, useExtrinsicGuess=True,
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not ok:
        return None

    R, _ = cv2.Rodrigues(rvec)
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(R)
    pitch, yaw, roll = float(angles[0]), float(angles[1]), float(angles[2])

    pitch = wrap_human_angle(pitch)
    yaw = (yaw + 180.0) % 360.0 - 180.0
    roll = wrap_human_angle(roll)

    return pitch, yaw, roll


class FaceController:
    """
    Reads face pose + eye closure and returns simple actions for the game loop.
    Smoothing + thresholds are used to reduce jitter.
    """

    def __init__(self, cam_index=0):
        self.cap = cv2.VideoCapture(cam_index)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open webcam.")

        self.face_mesh = mp_face.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )

        # Short history buffers reduce noise without adding too much lag.
        self.yaw_hist = deque(maxlen=9)
        self.pitch_hist = deque(maxlen=9)
        self.roll_hist = deque(maxlen=9)
        self.earL_hist = deque(maxlen=5)
        self.earR_hist = deque(maxlen=5)

        # Baselines are set during calibration so input is relative to the user.
        self.baseline_earL = None
        self.baseline_earR = None
        self.baseline_yaw = 0.0
        self.baseline_pitch = 0.0
        self.baseline_roll = 0.0

        # Thresholds trade off responsiveness vs. accidental moves.
        self.INVERT_X = True
        self.YAW_TH = 18.0
        self.PITCH_TH = 20.0
        self.PITCH_DEADZONE = 10.0

        # Requires a short hold before firing a direction.
        self.INTENT_FRAMES = 3
        self._mx_run = 0
        self._my_run = 0
        self._mx_last = 0
        self._my_last = 0

        # Eye-close is detected by a drop from the calibrated EAR baseline.
        self.BLINK_DROP = 0.72

    def calibrate(self):
        """
        Calibration saves a neutral head pose and open-eye EAR for the current user.
        """
        if len(self.earL_hist) > 0:
            self.baseline_earL = float(np.mean(self.earL_hist))
        if len(self.earR_hist) > 0:
            self.baseline_earR = float(np.mean(self.earR_hist))
        if len(self.yaw_hist) > 0:
            self.baseline_yaw = float(np.mean(self.yaw_hist))
        if len(self.pitch_hist) > 0:
            self.baseline_pitch = float(np.mean(self.pitch_hist))
        if len(self.roll_hist) > 0:
            self.baseline_roll = float(np.mean(self.roll_hist))

        self._mx_run = self._my_run = 0
        self._mx_last = self._my_last = 0

    def _apply_intent_filter(self, raw_mx: int, raw_my: int):
        """
        Filters quick spikes so only deliberate holds become moves.
        """
        if raw_mx == 0:
            self._mx_run = 0
            self._mx_last = 0
            mx = 0
        else:
            if raw_mx == self._mx_last:
                self._mx_run += 1
            else:
                self._mx_last = raw_mx
                self._mx_run = 1
            mx = raw_mx if self._mx_run >= self.INTENT_FRAMES else 0

        if raw_my == 0:
            self._my_run = 0
            self._my_last = 0
            my = 0
        else:
            if raw_my == self._my_last:
                self._my_run += 1
            else:
                self._my_last = raw_my
                self._my_run = 1
            my = raw_my if self._my_run >= self.INTENT_FRAMES else 0

        return mx, my

    def read_actions(self):
        """
        Returns movement + eye states each frame.
        The game can keep running even if no face is detected.
        """
        ok, frame = self.cap.read()
        if not ok:
            return None

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = self.face_mesh.process(rgb)

        actions = {
            "move_x": 0, "move_y": 0,
            "yaw": 0.0, "pitch": 0.0, "roll": 0.0,
            "left_eye_closed": False,
            "right_eye_closed": False,
            "face_found": False,
        }

        if not res.multi_face_landmarks:
            return actions

        actions["face_found"] = True
        lm = res.multi_face_landmarks[0].landmark
        pts = np.array([(p.x * w, p.y * h) for p in lm], dtype=np.float32)

        pose = head_pose_pnp(pts, w, h)
        if pose is not None:
            pitch, yaw, roll = pose
            self.pitch_hist.append(pitch)
            self.yaw_hist.append(yaw)
            self.roll_hist.append(roll)

            pitch_s = float(np.mean(self.pitch_hist)) - self.baseline_pitch
            yaw_s = float(np.mean(self.yaw_hist)) - self.baseline_yaw
            roll_s = float(np.mean(self.roll_hist)) - self.baseline_roll

            actions["pitch"] = pitch_s
            actions["yaw"] = yaw_s
            actions["roll"] = roll_s

            raw_mx = 0
            if yaw_s < -self.YAW_TH:
                raw_mx = -1
            elif yaw_s > self.YAW_TH:
                raw_mx = 1
            if self.INVERT_X:
                raw_mx *= -1

            raw_my = 0
            if pitch_s < -self.PITCH_TH:
                raw_my = 1
            elif pitch_s > self.PITCH_TH:
                raw_my = -1
            elif abs(pitch_s) < self.PITCH_DEADZONE:
                raw_my = 0

            mx, my = self._apply_intent_filter(raw_mx, raw_my)
            actions["move_x"] = mx
            actions["move_y"] = my

        earL = eye_ear(pts, LEFT_EYE)
        earR = eye_ear(pts, RIGHT_EYE)
        self.earL_hist.append(earL)
        self.earR_hist.append(earR)
        earL_s = float(np.mean(self.earL_hist))
        earR_s = float(np.mean(self.earR_hist))

        if self.baseline_earL is not None:
            actions["left_eye_closed"] = earL_s < self.baseline_earL * self.BLINK_DROP
        if self.baseline_earR is not None:
            actions["right_eye_closed"] = earR_s < self.baseline_earR * self.BLINK_DROP

        return actions

    def release(self):
        """
        Clean shutdown avoids camera lock issues on reruns.
        """
        try:
            self.face_mesh.close()
        except Exception:
            pass
        self.cap.release()

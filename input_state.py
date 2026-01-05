from dataclasses import dataclass
from typing import Optional


@dataclass
class InputState:
    # Face-loss tracking
    last_face_seen_time: float = 0.0

    # Movement arming
    move_armed: bool = True
    neutral_run: int = 0

    # BOTH eyes hold (place)
    both_hold_start: Optional[float] = None
    both_hold_armed: bool = True

    # Right-only hold (reset)
    right_only_hold_start: Optional[float] = None
    right_only_hold_armed: bool = True

    def on_calibrate(self):
        self.move_armed = True
        self.neutral_run = 0

        self.both_hold_start = None
        self.both_hold_armed = True

        self.right_only_hold_start = None
        self.right_only_hold_armed = True

    #  movement helpers 
    def update_neutral_and_arm(self, mx: int, my: int, neutral_frames_required: int):
        if mx == 0 and my == 0:
            self.neutral_run += 1
            if self.neutral_run >= neutral_frames_required:
                self.move_armed = True
        else:
            self.neutral_run = 0

    def consume_move_arm_if_moved(self, moved: bool):
        if moved:
            self.move_armed = False

    # hold helpers
    def handle_right_only_hold(self, now: float, right_closed: bool, left_closed: bool, reset_hold_seconds: float) -> bool:
        """
        Returns True if reset should trigger this frame.
        """
        if right_closed and (not left_closed):
            if self.right_only_hold_start is None:
                self.right_only_hold_start = now
                self.right_only_hold_armed = True

            if (now - self.right_only_hold_start) >= reset_hold_seconds and self.right_only_hold_armed:
                self.right_only_hold_armed = False
                return True
            return False

        # not holding right-only
        self.right_only_hold_start = None
        self.right_only_hold_armed = True
        return False

    def handle_both_hold(self, now: float, right_closed: bool, left_closed: bool, place_hold_seconds: float, game_over: bool) -> bool:
        """
        Returns True if "place" should trigger this frame.
        """
        if game_over:
            # if game ended, ignore placing
            self.both_hold_start = None
            self.both_hold_armed = True
            return False

        if left_closed and right_closed:
            if self.both_hold_start is None:
                self.both_hold_start = now
                self.both_hold_armed = True

            if (now - self.both_hold_start) >= place_hold_seconds and self.both_hold_armed:
                self.both_hold_armed = False
                return True
            return False

        # not holding both
        self.both_hold_start = None
        self.both_hold_armed = True
        return False

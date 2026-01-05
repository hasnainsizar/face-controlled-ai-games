import time
import pygame

import config as cfg
from face_controller import FaceController
from ttt_game import TicTacToeGame
from input_state import InputState


def choose_axis_no_diagonal(mx: int, my: int, yaw: float, pitch: float):
    # Head pose can briefly register both axes; force a single axis to keep control predictable.
    if mx != 0 and my != 0:
        if abs(yaw) >= abs(pitch):
            my = 0
        else:
            mx = 0
    return mx, my


def draw_difficulty_select(screen, font_big, font_small, selected, remaining_s):
    # Use a dedicated selection screen so gestures for "start" don't conflict with gameplay inputs.
    screen.fill((15, 15, 20))
    title = font_big.render("Select Difficulty", True, (240, 240, 240))
    screen.blit(title, (screen.get_width() / 2 - title.get_width() / 2, 140))

    hint = font_small.render("Turn head LEFT/RIGHT to choose. Auto-lock in 5s.", True, (220, 220, 220))
    screen.blit(hint, (screen.get_width() / 2 - hint.get_width() / 2, 230))

    easy_col = (80, 140, 255) if selected == "EASY" else (200, 200, 200)
    hard_col = (80, 140, 255) if selected == "HARD" else (200, 200, 200)

    easy = font_big.render("EASY", True, easy_col)
    hard = font_big.render("HARD", True, hard_col)

    screen.blit(easy, (160, 340))
    screen.blit(hard, (420, 340))

    countdown = font_small.render(f"Locking in: {int(remaining_s) + 1}s", True, (220, 220, 220))
    screen.blit(countdown, (screen.get_width() / 2 - countdown.get_width() / 2, 470))


def main():
    pygame.init()
    screen = pygame.display.set_mode((cfg.WIN_W, cfg.WIN_H))
    pygame.display.set_caption(cfg.TITLE)
    clock = pygame.time.Clock()
    font_big = pygame.font.SysFont(None, 90)
    font_small = pygame.font.SysFont(None, 26)

    face = FaceController(cam_index=0)
    game = TicTacToeGame(difficulty="HARD")
    state = InputState()

    status = "Press C to calibrate (eyes open, face forward)."
    calibrated = False
    running = True

    # Auto-reset keeps the experience continuous for hands-free play.
    GAME_RESET_DELAY = 5.0
    game_end_time = None

    # Difficulty is selected before gameplay to avoid accidental "place" gestures during setup.
    selecting = True
    select_start_time = None
    SELECT_LOCK_SECONDS = 5.0
    selected_difficulty = "HARD"

    while running:
        clock.tick(cfg.FPS)
        now = time.time()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False

                if event.key == pygame.K_c:
                    face.calibrate()
                    calibrated = True
                    status = "Calibrated. Head moves (1 step/gesture). BOTH eyes=PLACE. Right-only 3s=RESET."
                    # Reset gesture state after calibration so the first input is not misread.
                    state.on_calibrate()
                    selecting = True
                    select_start_time = now

        actions = face.read_actions()
        if actions is None:
            status = "Webcam read failed."
            game.draw(screen, status, pygame.font.SysFont(None, 140), font_small)
            pygame.display.flip()
            continue

        if actions["face_found"]:
            state.last_face_seen_time = now

        # Grace period avoids freezing controls on brief tracking drops.
        face_lost_too_long = (now - state.last_face_seen_time) > cfg.FACE_LOSS_GRACE_SECONDS
        if face_lost_too_long:
            status = "No face detected. Center yourself."
            game.draw(screen, status, pygame.font.SysFont(None, 140), font_small)
            pygame.display.flip()
            continue

        if not actions["face_found"]:
            game.draw(screen, status, pygame.font.SysFont(None, 140), font_small)
            pygame.display.flip()
            continue

        if not calibrated:
            status = "Face detected. Press C to calibrate."
            game.draw(screen, status, pygame.font.SysFont(None, 140), font_small)
            pygame.display.flip()
            continue

        if selecting:
            if select_start_time is None:
                select_start_time = now

            mx = actions["move_x"]  # -1 left, +1 right

            # "Arming" prevents rapid re-triggering when the head stays turned.
            state.update_neutral_and_arm(mx, 0, cfg.NEUTRAL_FRAMES_REQUIRED)

            if state.move_armed and mx != 0:
                if mx == -1:
                    selected_difficulty = "EASY"
                elif mx == 1:
                    selected_difficulty = "HARD"
                state.consume_move_arm_if_moved(True)

            remaining = SELECT_LOCK_SECONDS - (now - select_start_time)
            if remaining <= 0:
                game.difficulty = selected_difficulty
                selecting = False
                status = f"Difficulty locked: {game.difficulty}. Start playing!"
                state.on_calibrate()
            else:
                draw_difficulty_select(screen, font_big, font_small, selected_difficulty, remaining)
                pygame.display.flip()
                continue

        left_closed = actions["left_eye_closed"]
        right_closed = actions["right_eye_closed"]

        # Manual reset is available as a fallback if tracking or timing feels off.
        if state.handle_right_only_hold(now, right_closed, left_closed, cfg.RESET_HOLD_SECONDS):
            game.reset()
            state.on_calibrate()
            game_end_time = None

            selecting = True
            select_start_time = now
            selected_difficulty = game.difficulty
            status = "Reset! Re-select difficulty (head left/right)."

        # Auto-reset supports quick iteration without needing keyboard input.
        if game.winner is not None:
            if game_end_time is None:
                game_end_time = now

            remaining = GAME_RESET_DELAY - (now - game_end_time)
            if remaining > 0:
                remaining_int = int(remaining) + 1
                status = f"Game over: {game.winner}. Auto reset in {remaining_int}s."
            else:
                game.reset()
                state.on_calibrate()
                game_end_time = None

                selecting = True
                select_start_time = now
                selected_difficulty = game.difficulty
                status = "New round. Re-select difficulty (head left/right)."
                game.draw(screen, status, pygame.font.SysFont(None, 140), font_small)
                pygame.display.flip()
                continue

        # Place is a hold gesture to reduce accidental clicks from normal blinking.
        if game.winner is None:
            if state.handle_both_hold(now, right_closed, left_closed, cfg.PLACE_HOLD_SECONDS, game_over=False):
                placed = game.place_x()

                if placed:
                    game.maybe_ai_turn()

                    if game.winner == "X":
                        status = "You win! Auto reset in 5s"
                    elif game.winner == "O":
                        status = "AI wins! Auto reset in 5s"
                    elif game.winner == "DRAW":
                        status = "Draw! Auto reset in 5s"
                    else:
                        status = "Placed X. Your turn."
                else:
                    status = "Cell taken. Move cursor then hold BOTH eyes."

        if game.winner is None:
            mx = actions["move_x"]
            my = actions["move_y"]
            mx, my = choose_axis_no_diagonal(mx, my, actions["yaw"], actions["pitch"])

            state.update_neutral_and_arm(mx, my, cfg.NEUTRAL_FRAMES_REQUIRED)

            moved = False
            if state.move_armed:
                if mx == -1:
                    game.move_cursor(-1, 0)
                    moved = True
                elif mx == 1:
                    game.move_cursor(1, 0)
                    moved = True
                elif my == 1:      # UP
                    game.move_cursor(0, 1)
                    moved = True
                elif my == -1:     # DOWN
                    game.move_cursor(0, -1)
                    moved = True

            state.consume_move_arm_if_moved(moved)

        game.draw(screen, status, pygame.font.SysFont(None, 140), font_small)
        pygame.display.flip()

    face.release()
    pygame.quit()


if __name__ == "__main__":
    main()

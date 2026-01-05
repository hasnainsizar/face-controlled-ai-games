import pygame
import random

class TicTacToeGame:
    def __init__(self, difficulty="HARD"):
        # Difficulty is set once per round so AI behavior is predictable and testable
        self.difficulty = difficulty  # "EASY" or "HARD"
        self.reset()

    def reset(self):
        # Centralized reset keeps game restarts consistent (manual + auto reset)
        self.board = [[None, None, None] for _ in range(3)]
        self.cursor = [1, 1]
        self.winner = None
        self.win_line = None

    # AI (Easy / Hard)
    def ai_move_easy(self):
        # Easy mode intentionally ignores strategy to provide contrast with HARD
        empties = [(r, c) for r in range(3) for c in range(3) if self.board[r][c] is None]
        return random.choice(empties) if empties else None

    def ai_move_smart(self, ai="O", human="X"):
        board = self.board

        def empties():
            # Isolated helper keeps board scanning readable
            return [(r, c) for r in range(3) for c in range(3) if board[r][c] is None]

        def is_win(p):
            # Explicit checks favor clarity over compact tricks (interview-friendly)
            for r in range(3):
                if board[r][0] == board[r][1] == board[r][2] == p:
                    return True
            for c in range(3):
                if board[0][c] == board[1][c] == board[2][c] == p:
                    return True
            if board[0][0] == board[1][1] == board[2][2] == p:
                return True
            if board[0][2] == board[1][1] == board[2][0] == p:
                return True
            return False

        # First priority: win immediately if possible
        for r, c in empties():
            board[r][c] = ai
            if is_win(ai):
                board[r][c] = None
                return (r, c)
            board[r][c] = None

        # Second priority: block opponent’s immediate win
        for r, c in empties():
            board[r][c] = human
            if is_win(human):
                board[r][c] = None
                return (r, c)
            board[r][c] = None

        # Center is strongest early-game position
        if board[1][1] is None:
            return (1, 1)

        # Corners maximize future fork potential
        corners = [(0, 0), (0, 2), (2, 0), (2, 2)]
        open_corners = [p for p in corners if board[p[0]][p[1]] is None]
        if open_corners:
            return random.choice(open_corners)

        # Edges are lowest priority but prevent stalling
        edges = [(0, 1), (1, 0), (1, 2), (2, 1)]
        open_edges = [p for p in edges if board[p[0]][p[1]] is None]
        if open_edges:
            return random.choice(open_edges)

        return None

    def check_winner(self):
        b = self.board
        candidates = []

        # Group checks allow win-line extraction for rendering
        for r in range(3):
            candidates.append(([(r, 0), (r, 1), (r, 2)],
                               [b[r][0], b[r][1], b[r][2]]))

        for c in range(3):
            candidates.append(([(0, c), (1, c), (2, c)],
                               [b[0][c], b[1][c], b[2][c]]))

        candidates.append(([(0, 0), (1, 1), (2, 2)],
                           [b[0][0], b[1][1], b[2][2]]))
        candidates.append(([(0, 2), (1, 1), (2, 0)],
                           [b[0][2], b[1][1], b[2][0]]))

        for cells, vals in candidates:
            if vals[0] is not None and vals[0] == vals[1] == vals[2]:
                return vals[0], cells

        # Draw is evaluated last to preserve win priority
        if all(b[r][c] is not None for r in range(3) for c in range(3)):
            return "DRAW", None

        return None, None

    def place_x(self):
        # Explicit failure return avoids side effects in face-controlled input
        r, c = self.cursor
        if self.board[r][c] is not None:
            return False

        self.board[r][c] = "X"
        self.winner, self.win_line = self.check_winner()
        return True

    def maybe_ai_turn(self):
        # AI turn is gated here to keep main loop simple
        if self.winner is not None:
            return

        if self.difficulty == "EASY":
            mv = self.ai_move_easy()
        else:
            mv = self.ai_move_smart()

        if mv:
            r, c = mv
            self.board[r][c] = "O"

        self.winner, self.win_line = self.check_winner()

    def move_cursor(self, dx, dy):
        # Bounds checks prevent cursor drift from noisy head input
        if dx == -1:
            self.cursor[1] = max(0, self.cursor[1] - 1)
        elif dx == 1:
            self.cursor[1] = min(2, self.cursor[1] + 1)

        if dy == -1:
            self.cursor[0] = min(2, self.cursor[0] + 1)
        elif dy == 1:
            self.cursor[0] = max(0, self.cursor[0] - 1)

    def draw(self, screen, status_text, font_big, font_small):
        # Rendering is kept stateless so visuals reflect game state only
        screen.fill((15, 15, 20))
        w, h = screen.get_size()
        grid_size = min(w, h) * 0.8
        x0 = (w - grid_size) / 2
        y0 = (h - grid_size) / 2
        cell = grid_size / 3

        for i in range(1, 3):
            pygame.draw.line(screen, (200, 200, 200),
                             (x0 + i * cell, y0), (x0 + i * cell, y0 + grid_size), 3)
            pygame.draw.line(screen, (200, 200, 200),
                             (x0, y0 + i * cell), (x0 + grid_size, y0 + i * cell), 3)

        cr, cc = self.cursor
        rect = pygame.Rect(x0 + cc * cell, y0 + cr * cell, cell, cell)
        pygame.draw.rect(screen, (80, 140, 255), rect, 5)

        for r in range(3):
            for c in range(3):
                val = self.board[r][c]
                if val is None:
                    continue
                text = font_big.render(val, True, (240, 240, 240))
                tx = x0 + c * cell + cell / 2 - text.get_width() / 2
                ty = y0 + r * cell + cell / 2 - text.get_height() / 2
                screen.blit(text, (tx, ty))

        # Win line provides immediate visual feedback without extra UI elements
        if self.win_line is not None and self.winner in ("X", "O"):
            win_color = (255, 0, 0) if self.winner == "X" else (0, 255, 0)

            def cell_center(rr, cc):
                return (x0 + cc * cell + cell / 2, y0 + rr * cell + cell / 2)

            (r1, c1), (_, _), (r3, c3) = self.win_line
            p1 = cell_center(r1, c1)
            p2 = cell_center(r3, c3)

            pygame.draw.line(screen, win_color, p1, p2, 12)
            pygame.draw.circle(screen, win_color, (int(p1[0]), int(p1[1])), 10)
            pygame.draw.circle(screen, win_color, (int(p2[0]), int(p2[1])), 10)

        st = font_small.render(status_text, True, (220, 220, 220))
        screen.blit(st, (10, 10))

        diff = font_small.render(f"Difficulty: {self.difficulty}", True, (220, 220, 220))
        screen.blit(diff, (10, 36))

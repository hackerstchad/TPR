#!/usr/bin/env python3
"""
TPR - Terminal Particle Rain
Auteur: hackers_tchad
Simulation cmatrix avancee, verte, multithreadee, auto-demarrage.
Lancee sans input, sans arguments --, sur une seule page terminal.
"""

import sys
import time
import random
import shutil
import threading
import signal

# Configuration globale
AUTEUR = "hackers_tchad"
TITRE = "TPR"
YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Palette verte cmatrix
def green_intensity(level):
    """Retourne un code ANSI vert selon l'intensite 0-5."""
    levels = [
        "\033[38;5;22m",   # tres sombre
        "\033[38;5;28m",   # sombre
        "\033[38;5;34m",   # moyen
        "\033[38;5;40m",   # clair
        "\033[38;5;46m",   # tres clair
        "\033[38;5;82m",   # blanc-vert
    ]
    return levels[max(0, min(len(levels) - 1, level))]

RESET = "\033[0m"
CLEAR = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

# Caracteres style cmatrix (katakana + latin + chiffres)
MATRIX_CHARS = (
    "アイウエオカキクケコサシスセソタチツテトナニヌネノ"
    "ハヒフヘホマミムメモヤユヨラリルレロワヲン"
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
)


class CMatrixEngine:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = True
        self.size = shutil.get_terminal_size((80, 24))
        self.columns = self.size.columns
        self.lines = self.size.lines
        # Grille de caracteres: chaque cellule contient (char, intensity_age)
        self.grid = [[(" ", 0) for _ in range(self.columns)] for _ in range(self.lines)]
        # Liste des trainées actives: (col, head_row, speed, length, alive)
        self.trails = []
        self.frame_count = 0
        self.start_time = time.time()
        self.max_trails = max(40, self.columns // 2)
        self._spawn_initial_trails()

    def _spawn_initial_trails(self):
        for _ in range(self.max_trails):
            self._spawn_trail()

    def _spawn_trail(self):
        col = random.randint(0, max(0, self.columns - 1))
        speed = random.choice([0.3, 0.5, 0.7, 1.0, 1.3])
        length = random.randint(3, max(5, self.lines // 2))
        head_row = random.randint(-self.lines, 0)
        self.trails.append({
            "col": col,
            "head": float(head_row),
            "speed": speed,
            "length": length,
            "alive": True,
        })

    def resize(self):
        with self.lock:
            new_size = shutil.get_terminal_size((80, 24))
            if new_size.columns != self.columns or new_size.lines != self.lines:
                self.columns = new_size.columns
                self.lines = new_size.lines
                self.grid = [[(" ", 0) for _ in range(self.columns)] for _ in range(self.lines)]
                self.trails = []
                self.max_trails = max(40, self.columns // 2)
                self._spawn_initial_trails()

    def update(self):
        with self.lock:
            # Vieillir / attenuer toutes les cellules
            for r in range(self.lines):
                for c in range(self.columns):
                    ch, age = self.grid[r][c]
                    if ch != " ":
                        age += 1
                        if age > 5:
                            self.grid[r][c] = (" ", 0)
                        else:
                            self.grid[r][c] = (ch, age)

            # Mettre a jour chaque trainee
            for trail in self.trails:
                if not trail["alive"]:
                    continue
                trail["head"] += trail["speed"]
                head = int(trail["head"])
                col = trail["col"]
                length = trail["length"]

                # Dessiner la trainee
                for offset in range(length):
                    row = head - offset
                    if 0 <= row < self.lines and 0 <= col < self.columns:
                        if offset == 0:
                            # Tete blanche-verte
                            self.grid[row][col] = (random.choice(MATRIX_CHARS), 0)
                        else:
                            # Corps qui s'estompe
                            self.grid[row][col] = (random.choice(MATRIX_CHARS), min(offset, 5))

                # Marquer morte si sortie de l'ecran
                if head - length > self.lines + 2:
                    trail["alive"] = False

            # Reanimation / nouvelles trainees
            self.trails = [t for t in self.trails if t["alive"]]
            while len(self.trails) < self.max_trails:
                self._spawn_trail()

            self.frame_count += 1

    def _render_row(self, row_index):
        """Rend une ligne avec degrade vert."""
        parts = []
        for c in range(self.columns):
            ch, age = self.grid[row_index][c]
            if ch == " ":
                parts.append(" ")
            else:
                parts.append(green_intensity(age) + ch + RESET)
        return "".join(parts)

    def render(self):
        with self.lock:
            lines = []
            # Bandeau superieur: TPR + auteur + URL
            banner_text = f" {TITRE} | auteur: {AUTEUR} | {YOUTUBE_URL} "
            banner = banner_text.center(self.columns)[:self.columns]
            lines.append("\033[48;5;22m\033[38;5;82m" + banner + RESET)

            for r in range(self.lines - 1):
                lines.append(self._render_row(r))

            # Bandeau inferieur avec FPS approximatif et duree
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            footer_text = f" frames: {self.frame_count} | uptime: {elapsed:.1f}s | fps: {fps:.1f} "
            footer = footer_text.center(self.columns)[:self.columns]
            lines.append("\033[48;5;22m\033[38;5;82m" + footer + RESET)

            return CLEAR + HIDE_CURSOR + "\n".join(lines)


class MultiTerminalSimulator:
    """
    Simule l'ouverture de "plus de 1000 terminaux" en divisant l'ecran
    en mini-fenetres (split-screen) au sein d'un seul terminal.
    """
    def __init__(self, splits=120):
        self.splits = splits
        self.lock = threading.Lock()
        self.running = True
        self.size = shutil.get_terminal_size((80, 24))
        self.engines = [CMatrixEngine() for _ in range(splits)]
        self.threads = []

    def resize(self):
        with self.lock:
            new_size = shutil.get_terminal_size((80, 24))
            if new_size.columns != self.size.columns or new_size.lines != self.size.lines:
                self.size = new_size
                for engine in self.engines:
                    engine.resize()

    def _update_engine(self, engine):
        while self.running:
            engine.update()
            time.sleep(0.03)

    def start(self):
        for engine in self.engines:
            t = threading.Thread(target=self._update_engine, args=(engine,), daemon=True)
            t.start()
            self.threads.append(t)

    def stop(self):
        self.running = False
        for t in self.threads:
            t.join(timeout=0.5)

    def _split_layout(self):
        """Determine la grille (cols x rows) pour afficher les mini terminaux."""
        # On vise environ un ratio 16/9 par mini-fenetre
        best = (1, 1)
        best_ratio_diff = float("inf")
        for cols in range(1, self.splits + 1):
            if self.splits % cols != 0:
                continue
            rows = self.splits // cols
            if rows == 0:
                continue
            mini_w = self.size.columns / cols
            mini_h = self.size.lines / rows
            ratio = mini_w / mini_h if mini_h else 1
            diff = abs(ratio - 2.0)
            if diff < best_ratio_diff:
                best_ratio_diff = diff
                best = (cols, rows)
        return best

    def _render_mini(self, engine, mini_w, mini_h):
        """Rend un moteur cmatrix redimensionne a mini_w x mini_h."""
        out = []
        # On se base sur la grille interne, tronquee/dupliquee aux dimensions mini
        grid = engine.grid
        src_h = min(len(grid), mini_h)
        src_w = min(len(grid[0]) if grid else 0, mini_w)
        for r in range(mini_h):
            row_parts = []
            src_r = min(r, src_h - 1) if src_h else 0
            for c in range(mini_w):
                src_c = min(c, src_w - 1) if src_w else 0
                if grid and src_r < len(grid) and src_c < len(grid[src_r]):
                    ch, age = grid[src_r][src_c]
                else:
                    ch, age = " ", 0
                if ch == " ":
                    row_parts.append(" ")
                else:
                    row_parts.append(green_intensity(age) + ch + RESET)
            out.append("".join(row_parts))
        return out

    def render(self):
        with self.lock:
            self.size = shutil.get_terminal_size((80, 24))
            cols, rows = self._split_layout()
            mini_w = self.size.columns // cols
            mini_h = self.size.lines // rows

            # Recuperer chaque mini rendu
            mini_screens = []
            for idx in range(self.splits):
                mini = self._render_mini(self.engines[idx], mini_w, mini_h)
                mini_screens.append(mini)

            # Composer l'ecran final
            final_lines = []
            for row_idx in range(rows):
                for h in range(mini_h):
                    line_parts = []
                    for col_idx in range(cols):
                        idx = row_idx * cols + col_idx
                        if idx < len(mini_screens):
                            mini = mini_screens[idx]
                            if h < len(mini):
                                line_parts.append(mini[h])
                            else:
                                line_parts.append(" " * mini_w)
                        else:
                            line_parts.append(" " * mini_w)
                    final_lines.append("".join(line_parts))

            # Ajouter un bandeau TPR/hackers_tchad en overlay si assez de place
            if self.size.lines > 3 and self.size.columns > 40:
                overlay = f" [{TITRE}] by {AUTEUR} - {YOUTUBE_URL} ".center(self.size.columns)[:self.size.columns]
                final_lines[0] = "\033[48;5;22m\033[38;5;82m" + overlay + RESET

            return CLEAR + HIDE_CURSOR + "\n".join(final_lines)


def main():
    # Pas d'input, pas d'arguments --
    try:
        # Mode multi-fenetre par defaut (simule 100+ terminaux sur une page)
        sim = MultiTerminalSimulator(splits=120)
        sim.start()

        def on_resize(signum, frame):
            sim.resize()

        signal.signal(signal.SIGWINCH, on_resize)

        # Auto-demarrage immédiat, pas d'input
        while True:
            sys.stdout.write(sim.render())
            sys.stdout.flush()
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(SHOW_CURSOR + CLEAR)
        sys.stdout.flush()


if __name__ == "__main__":
    main()

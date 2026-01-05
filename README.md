"A hands-free Tic-Tac-Toe game controlled using head movement and eye gestures"

**Face-Controlled Tic-Tac-Toe**

This project is a hands-free version of Tic-Tac-Toe controlled using head movement and eye gestures via a webcam.
The goal was to explore alternative input methods while keeping the gameplay simple and reliable.

- How It Works

    Head movement controls the cursor (one step per gesture)

    Both eyes closed (hold) places a move

    Right eye closed (hold) resets the game

    A short calibration step adapts the controls to each user

    Input smoothing, thresholds, and cooldowns are used to reduce noise and accidental actions.

- Difficulty Modes

    Easy: random moves

    Hard: rule-based strategy (win, block, center, corners)

    Difficulty is selected at the start of each round using head movement and locks automatically after a short timer.

- Design Choices

    No keyboard or mouse input during gameplay

    Intent filtering to prevent repeated or diagonal moves

    Automatic game reset after completion

    Clear separation between input handling, game logic, and rendering

    The project prioritizes stability and clarity over complexity.

    Tech Stack consists of Python, OpenCV, MediaPipe and Pygame

- Running the Project

    pip install opencv-python mediapipe pygame numpy
    python main.py

- Notes

    This project was built as a learning exercise to better understand real-time input handling, noise filtering, and state-driven game design.
    Future improvements could include adaptive difficulty, accessibility tuning, or additional games using the same input system.
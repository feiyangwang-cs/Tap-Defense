# Tap Defense

A voice-controlled tower defense game built with Python, Pygame, and AWS. This project combines a classic tap-based game with a voice-activated AI companion that can control the game and provide (sarcastic) commentary.

## Features

*   **Classic Tower Defense Gameplay:** Tap to defeat enemies as they move along a path.
*   **Voice Control:** Use your voice to interact with the game.
*   **AI Companion:** A sarcastic and playful AI bot powered by AWS Lex and Bedrock (Claude 3 Haiku).
*   **Multiple Difficulty Levels:** Choose from easy, normal, and hard modes.
*   **Dynamic UI:** The game features a main menu, pause/resume functionality, and a game-over screen.
*   **Raspberry Pi Support:** Designed to run on a Raspberry Pi with a PiTFT display.

## Architecture

The project consists of three main components that run concurrently:

1.  **Game (`tap_denfense_real_enemy.py`):** The main game logic, built with Pygame.
2.  **Voice Bot (`bot/bot.py`):** Handles voice input, intent recognition (AWS Lex), and response generation (AWS Bedrock).
3.  **Game State API (`game_state/service.py`):** A Flask server that acts as a bridge between the game and the bot, allowing them to communicate and share state.

The components communicate as follows:

```
+-----------+       +-------------------+       +-------------+
|           |       |                   |       |             |
| Game      +-----> | Game State API    | <-----+ Voice Bot   |
| (Pygame)  |       | (Flask)           |       | (AWS Lex)   |
|           |       |                   |       |             |
+-----------+       +-------------------+       +-------------+
```

## Setup


1.  **Install dependencies:**
    The project uses a `makefile` to streamline the installation process.
    ```bash
    make install
    ```
    This will install the Python packages listed in `requirements.txt`.

2.  **AWS Credentials:**
    The voice bot requires AWS credentials to interact with Lex and Bedrock. Make sure you have your AWS credentials configured. This can be done by creating a `.env` file in the root of the project with the following content:
    ```
    AWS_REGION="us-east-1"
    LEX_BOT_ID="YOUR_LEX_BOT_ID"
    LEX_ALIAS_ID="YOUR_LEX_ALIAS_ID"
    LEX_LOCALE_ID="en_US"
    LEX_SESSION_ID="pi_voice_session"
    ```

## Running the Game

To run the game, including the game state API server and the voice bot, use the following command:

```bash
make run
```

This will:
1.  Start the Game State API server.
2.  Start the Voice Bot.
3.  Start the game.

To run the components individually:
*   **Game State API:** `make api`
*   **Voice Bot:** `make bot`
*   **Game:** `make game`

## Voice Commands

The following voice commands are supported:

*   **Change Difficulty:**
    *   "Set difficulty to easy/normal/hard"
*   **Change Volume:**
    *   "Set volume to [0-100]"
*   **Game Control:**
    *   "Start the game"
    *   "Pause the game"
    *   "Resume the game"
    *   "Restart the game"
    *   "Exit the game"

The bot will also provide proactive commentary on the game's state.

## Project Structure

```
.
├── bot/                  # Voice bot implementation
│   ├── bot.py            # Main bot logic
│   ├── persona.py        # Bot's persona and replies
│   └── ...
├── game_state/           # Game state API
│   ├── api.py            # API client
│   └── service.py        # Flask API server
├── src/                  # Game assets (images, sounds)
├── tap_denfense_real_enemy.py # Main game file
├── makefile              # Makefile for easy installation and execution
└── requirements.txt      # Python dependencies
```

PYTHON ?= python3
ROOT := $(shell pwd)

.PHONY: all install api bot run clean

all: run

install:
	$(PYTHON) -m pip install -r requirements.txt

api:
	$(PYTHON) $(shell pwd)/game_state/service.py

bot:
	$(PYTHON) -m bot.bot

game:
	sudo $(PYTHON) $(shell pwd)/tap_denfense_real_enemy.py

run:
	@echo "==> Starting GameState API server on 127.0.0.1:5050 ..."
	@$(PYTHON) game_state/service.py & \
	sleep 1; \
	echo "==> Starting Voice Bot..."; \
	$(PYTHON) -m bot.bot & \
	sleep 1; \
	echo "==> Starting Game NOW!!! ..."; \
	sudo $(PYTHON) tap_denfense_real_enemy.py

clean:
	@echo "==> Removing __pycache__ directories..."
	@find . -name "__pycache__" -type d -prune -exec rm -rf {} +

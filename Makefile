SHELL := /bin/sh

VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip
OLLAMA_MODE ?= cloud
OLLAMA_BASE_URL ?= https://ollama.com/api
OLLAMA_MODEL ?= qwen3:30b

.PHONY: setup test run ollama-check ollama-pull

setup:
	test -d "$(VENV)" || python3 -m venv "$(VENV)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m unittest discover -s tests -v

run:
	if [ "$(OLLAMA_MODE)" = "local" ]; then $(MAKE) ollama-check; fi
	OLLAMA_MODE="$(OLLAMA_MODE)" OLLAMA_BASE_URL="$(OLLAMA_BASE_URL)" OLLAMA_MODEL="$(OLLAMA_MODEL)" $(PYTHON) main.py

ollama-check:
	@if [ "$(OLLAMA_MODE)" != "local" ]; then \
		echo "Skipping local Ollama check because OLLAMA_MODE=$(OLLAMA_MODE)."; \
		exit 0; \
	fi
	@BASE_URL="$(OLLAMA_BASE_URL)"; \
	case "$$BASE_URL" in \
		*/api) TAGS_URL="$$BASE_URL/tags" ;; \
		*) TAGS_URL="$$BASE_URL/api/tags" ;; \
	esac; \
	curl -fsS "$$TAGS_URL" >/dev/null || { \
		echo "Ollama is not running at $$TAGS_URL. Start Ollama or switch to cloud mode before launching the app."; \
		exit 1; \
	}

ollama-pull:
	@if [ "$(OLLAMA_MODE)" != "local" ]; then \
		echo "Skipping model pull because OLLAMA_MODE=$(OLLAMA_MODE). Cloud mode does not require a local model download."; \
		exit 0; \
	fi
	ollama pull "$(OLLAMA_MODEL)"

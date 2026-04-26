SHELL := powershell.exe
.SHELLFLAGS := -NoProfile -Command

VENV ?= .venv
PYTHON := $(VENV)\Scripts\python.exe
PIP := $(PYTHON) -m pip
OLLAMA_MODE ?= local
OLLAMA_BASE_URL ?= http://localhost:11434
OLLAMA_MODEL ?= qwen3:30b

.PHONY: setup test run ollama-check ollama-pull

setup:
	if (-not (Test-Path "$(VENV)")) { python -m venv "$(VENV)" }
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m unittest discover -s tests -v

run:
	if ("$(OLLAMA_MODE)" -eq "local") { $(MAKE) ollama-check }
	$$env:OLLAMA_MODE = "$(OLLAMA_MODE)"; $$env:OLLAMA_BASE_URL = "$(OLLAMA_BASE_URL)"; $$env:OLLAMA_MODEL = "$(OLLAMA_MODEL)"; $(PYTHON) main.py

ollama-check:
	if ("$(OLLAMA_MODE)" -ne "local") { Write-Output "Skipping local Ollama check because OLLAMA_MODE=$(OLLAMA_MODE)."; exit 0 }
	$$baseUrl = "$(OLLAMA_BASE_URL)".TrimEnd("/"); if ($$baseUrl.EndsWith("/api")) { $$tagsUrl = "$$baseUrl/tags" } else { $$tagsUrl = "$$baseUrl/api/tags" }; try { Invoke-WebRequest -UseBasicParsing $$tagsUrl | Out-Null } catch { Write-Output "Ollama is not running at $$tagsUrl. Start the Ollama app before launching the simulation."; exit 1 }

ollama-pull:
	if ("$(OLLAMA_MODE)" -ne "local") { Write-Output "Skipping model pull because OLLAMA_MODE=$(OLLAMA_MODE). Cloud mode does not require a local model download."; exit 0 }
	ollama pull "$(OLLAMA_MODEL)"

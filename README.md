# 334-Final-Project
# Generative Agents Simulation

## Project Overview
This project is inspired by the Stanford HAI research on "Generative Agents." It aims to create a Linux-based simulation environment where autonomous computational agents exhibit human-like behavior. Instead of hard-coded scripts, agents utilize a Large Language Model (LLM) to perceive their surroundings, maintain a memory stream, reflect on experiences, and plan future actions.

## Core Features (MVP)
* **Memory Stream:** A persistent log of agent experiences and observations.
* **Architecture Loop:** Implementation of Perception -> Retrieval -> Reflection -> Planning -> Action.
* **Environment Simulator:** A basic text-based or 2D grid environment where agents can interact (very simple).
* **LLM Integration:** Connection to an inference engine (e.g., OpenAI API or a local Llama model).

## Tech Stack
* **Language:** Python 3.10 
* **Environment:** Linux (Ubuntu/Debian recommended).
* **LLM Framework:** LangChain or OpenAI Python SDK.
* **Storage:** SQLite or JSON (for the initial Memory Stream implementation).
* **Environment Simulation:** Custom Python scripts or a basic framework like Pygame.

## Getting Started (Linux Setup)
1. **Clone the repository:**
https://github.com/IsaacSShade/334-Final-Project.git

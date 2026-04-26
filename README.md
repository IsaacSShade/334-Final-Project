<div id="top"></div>

<!--
*** Thanks for checking out the Best-README-Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Don't forget to give the project a star!
*** Thanks again! Now go create something AMAZING! :D
-->

<!-- PROJECT SHIELDS -->

<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]

<br />
<div align="center">
  <h3 align="center">334 Final Project</h3>
  <h1 align="center">Generative Agents Simulation</h1>
  <p align="center">
    By Aiden Tabrah, Rohan Kanumuri, and Carson Frost
  </p>

  <p align="center">
    A Linux-based simulation environment where autonomous agents exhibit human-like behavior using LLM-driven perception, memory, reflection, planning, and action.
    <br />
    <a href="https://github.com/IsaacSShade/334-Final-Project"><strong>Explore the repo »</strong></a>
    <br />
    <br />
    <a href="https://github.com/IsaacSShade/334-Final-Project">View Project</a>
    ·
    <a href="https://github.com/IsaacSShade/334-Final-Project/issues">Report Bug</a>
    ·
    <a href="https://github.com/IsaacSShade/334-Final-Project/issues">Request Feature</a>
  </p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#core-features-mvp">Core Features (MVP)</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li><a href="#getting-started-linux-setup">Getting Started (Linux Setup)</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

---

## About The Project

This project is inspired by the Stanford HAI research on **Generative Agents**. The goal is to create a simulation environment where autonomous computational agents behave in more human-like ways.

Rather than relying on rigid, hard-coded scripts, each agent uses a Large Language Model (LLM) to perceive its surroundings, maintain memories, reflect on past experiences, plan future actions, and act within a simulated environment.

The project is meant to explore how believable agent behavior can emerge from a structured architecture and a shared simulation space.

<p align="right">(<a href="#top">back to top</a>)</p>

## Core Features (MVP)

* **Character Creation Screen**  
  A setup interface for defining agent names, personalities, traits, or other starting attributes.

* **Shared Environment**  
  A simple environment where agents can exist, observe, and interact with the world and each other.

* **Agent Interaction Interface**  
  A consistent interface that allows agents to interpret the environment and choose actions.

* **Simulation Loop and Orchestrator**  
  A main control loop that manages time steps, agent turns, state updates, and overall simulation flow.

<p align="right">(<a href="#top">back to top</a>)</p>

## Built With

This project is planned around the following tools and technologies:

* **Python 3.10**
* **Linux** (Ubuntu/Debian recommended)
* **Ollama Local** (recommended default)
* **Ollama Cloud** (optional)
* **SQLite** or **JSON** for initial memory and state storage
* **Custom Python scripts** or **Pygame** for simulation and environment logic

<p align="right">(<a href="#top">back to top</a>)</p>

## Getting Started (Linux Setup)

1. **Clone the repository**
   ```bash
   git clone https://github.com/IsaacSShade/334-Final-Project.git
   cd 334-Final-Project
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up the local Ollama app**

   Install and launch the Ollama desktop app for your platform so the local API is available at `http://localhost:11434`.

   Recommended local workflow:
   ```bash
   make ollama-check
   make ollama-pull
   ```

   The project now defaults to local Ollama mode, so no API key is required for normal development.

   Optional cloud override:
   ```bash
   OLLAMA_MODE=cloud OLLAMA_BASE_URL=https://ollama.com/api python main.py
   ```
   If you explicitly use cloud mode, you must also provide `OLLAMA_API_KEY`.

5. **Run the project**
   ```bash
   make run
   ```

Eventually this will all become part of a Makefile

<p align="right">(<a href="#top">back to top</a>)</p>

## Roadmap

We used a github Project as our project management tool, view it here: https://github.com/users/IsaacSShade/projects/2

- [ ] Create a character creation screen
- [ ] Create an environment for AIs to interact with
- [ ] Provide an interface for AIs to interact with the environment
- [ ] Create the main simulation loop and orchestrator
- [ ] Create a makefile for automating project setup and running/testing

<p align="right">(<a href="#top">back to top</a>)</p>

## License

We can figure this out later

<p align="right">(<a href="#top">back to top</a>)</p>

## Acknowledgments

* Inspired by Stanford HAI research on **Generative Agents**
* Built as part of **CPSC 334 Final Project**

<p align="right">(<a href="#top">back to top</a>)</p>

---

[contributors-shield]: https://img.shields.io/github/contributors/IsaacSShade/334-Final-Project.svg?style=for-the-badge
[contributors-url]: https://github.com/IsaacSShade/334-Final-Project/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/IsaacSShade/334-Final-Project.svg?style=for-the-badge
[forks-url]: https://github.com/IsaacSShade/334-Final-Project/network/members
[stars-shield]: https://img.shields.io/github/stars/IsaacSShade/334-Final-Project.svg?style=for-the-badge
[stars-url]: https://github.com/IsaacSShade/334-Final-Project/stargazers
[issues-shield]: https://img.shields.io/github/issues/IsaacSShade/334-Final-Project.svg?style=for-the-badge
[issues-url]: https://github.com/IsaacSShade/334-Final-Project/issues

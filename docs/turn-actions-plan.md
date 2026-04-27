# Turn Actions Plan

## Purpose

This document defines a simple, modular plan for implementing the first three character turn actions:

1. Move to a different room
2. Start and carry a conversation
3. Change the visible details of a room

The goal is **not** to build the full orchestrator yet. The goal is to create a clean action layer that the future orchestrator can call with a small surface area. The orchestrator owns turn order, unseen-event delivery, and room backlog assembly. This plan only covers what happens once an action is chosen.

## Scope for This Work

In scope:

- Action service design for movement, conversation, and room updates
- Shared request/response contracts for individual actions
- Database additions needed to persist canonical action results
- Test strategy that fits the current `unittest` and GitHub Actions setup

Out of scope:

- Full turn scheduling across all characters
- Per-character room-event backlog creation or delivery
- Building start-of-turn room summaries from prior events
- A bundled multi-action executor that runs a full character turn
- Reflection, long-term planning, or memory ranking logic beyond basic conversation memory writes
- UI polish
- Final prompt engineering for every model edge case

## Design Goals

- Make each action callable from a thin orchestrator API
- Keep each action isolated in its own module
- Use structured inputs and outputs, not free-form parsing
- Keep behavioral guardrails in prompts instead of building a heavy validation layer
- Persist important state changes so other characters can observe them later
- Make action logic testable without the UI running
- Stay close to the current codebase instead of introducing a heavy framework

## Orchestrator Integration

This branch should expose thin action handlers that the orchestrator can call after it decides which actions occur.

Example shape:

```python
movement_result = movement_action.execute(request)
conversation_result = conversation_action.execute(request)
room_update_result = room_update_action.execute(request)
```

The orchestrator plan owns:

- whether an action should run
- in what order actions run inside a turn
- what unseen room events are delivered at the start of a turn
- how canonical events are grouped into a per-character backlog

## Proposed Module Layout

Recommended new files:

```text
sim/
  actions/
    __init__.py
    movement.py
    conversation.py
    room_update.py
    schemas.py
```

Test layout:

```text
tests/
  test_movement_action.py
  test_conversation_action.py
  test_room_update_action.py
```

Why this shape:

- each action file owns one behavior
- `schemas.py` keeps data contracts explicit

## Shared Contracts

Use dataclasses or small typed classes for the action layer.

### `ActionContext`

This is the read-only context each action receives.

Suggested fields:

- `turn_number`
- `character`
- `current_room`
- `characters_in_current_room`
- `room_event_backlog`

`room_event_backlog` should be assembled by the orchestrator from unseen room-local events. The action layer consumes it but does not build or deliver it.

This lets the action logic see:

- where the character currently is
- who is nearby
- what happened in the room while it was not this character's turn

Action-specific visibility should be added in per-action request objects, not the shared base context.

### Orchestrator-Owned Turn Bundles

Any bundled multi-action contract such as `PlannedActions` or `TurnActionResult` belongs to the orchestrator layer, not this branch.

This branch should stay focused on per-action request/response contracts such as:

- `MoveActionRequest`
- `ConversationActionRequest`
- `RoomUpdateActionRequest`

Recommended specialization:

- `MoveActionRequest` includes `available_rooms`
- `ConversationActionRequest` stays scoped to the current room and current occupants, and includes the full shared conversation state for each exchange
- `RoomUpdateActionRequest` stays scoped to the current room and current room description

### `ActionResult`

Each action should return a consistent result object.

Suggested fields:

- `action_type`
- `success`
- `summary`
- `events_created`
- `state_changes`
- `warnings`

## Action 1: Movement

### Goal

Allow a character to stay in place or move to any other existing room.

### Inputs the actor should see

- current room name and description
- other characters currently in the room
- all rooms with descriptions
- room-local backlog entries supplied by the orchestrator

### Recommended behavior

1. Build a movement context for the character
2. Ask for a structured movement decision
3. If the decision is `stay`, return with no state change and no event
4. Validate the target room
5. If valid, update `current_room_id`
6. Create event logs for leaving and entering
7. Return a result summary

### Basic checks

- target room must exist
- staying in place is valid
- movement should fail cleanly if the character or room no longer exists

### Persistence needs

Current schema already supports `characters.current_room_id` and `events`.

No room-connection table is needed because all rooms are globally reachable.

### Event examples

- `"Alice left the kitchen for the living room."`
- `"Alice entered the living room from the kitchen."`

## Action 2: Conversation

### Goal

Allow one character to initiate a conversation with another character in the same room and carry it back and forth up to a hard cap.

### KISS v1 rules

- only one initiated conversation action per acting character per turn
- both characters must be in the same room when the conversation starts
- the conversation is synchronous inside the action call
- hard cap: `50` exchanges total
- soft wrap-up guidance starts before the cap

### Recommended conversation loop

1. Initiator selects a target character in the same room
2. Create conversation context for both participants
3. Generate one message at a time in alternating order
4. After each message, check termination conditions
5. Append the message to one shared transcript visible to both speakers
6. Stop when the conversation ends or reaches the cap
7. Persist transcript rows, memory writes, and summary events

### Termination design

Do **not** rely on vague natural-language detection alone.

Each generated message should return structured fields:

- `utterance`
- `should_end: bool`
- `end_reason: str | None`

Recommended `end_reason` values:

- `natural_close`
- `goodbye`
- `topic_exhausted`
- `refused`
- `interrupted`
- `max_turns`

### Prompt pressure for wrap-up

Recommended thresholds:

- exchanges `1-29`: normal conversation
- exchanges `30-39`: mild instruction to start narrowing the topic
- exchanges `40-49`: strong instruction to conclude naturally
- exchange `50`: force termination with `end_reason="max_turns"`

### Context continuity for both participants

The conversation service should maintain one canonical in-memory conversation state for the duration of the action.

Suggested shared state:

- `conversation_id`
- `room_id`
- `turn_number`
- `initiator_id`
- `recipient_id`
- `exchange_count`
- `transcript`
- `conversation_goal`
- `closing_pressure`

Each LLM call for either speaker should receive:

- that speaker's own internal character details
- the other participant's visible physical details only
- the current room description
- the same full transcript so far
- a short system instruction describing the current wrap-up pressure

That means both participants always respond against the same complete conversation history instead of separate partial views, while still preserving private character information.

Recommended KISS rule:

- pass the entire transcript every exchange in v1
- if token pressure becomes an issue later, replace older lines with rolling summaries

### Memory write plan

The conversation action should be responsible for producing conversation-derived memory records for both participants before returning.

Recommended flow:

1. persist the full transcript in `conversation_messages`
2. generate a short per-conversation summary
3. generate one participant-specific memory text for the initiator
4. generate one participant-specific memory text for the recipient
5. store those memory rows through `sim/core/database.py`

Recommended v1 memory policy:

- create one `short_term` memory for each participant at the end of the conversation
- set `source_event_id` to the conversation summary event
- set `created_turn` to the current turn

Suggested memory examples:

- initiator memory: `"I talked with Bob in the kitchen about settling into the house."`
- recipient memory: `"Alice asked me about the move, and we wrapped up on friendly terms."`

This keeps memory writing simple and deterministic without introducing full reflection or memory scoring.

### Persistence needs

Using only the current `events` table will be too thin for debugging and later memory use.

Recommended new tables:

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    turn_number INTEGER NOT NULL,
    room_id TEXT NOT NULL,
    initiator_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    status TEXT NOT NULL,
    exchange_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT,
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (initiator_id) REFERENCES characters(id),
    FOREIGN KEY (recipient_id) REFERENCES characters(id)
);

CREATE TABLE conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    speaker_id TEXT NOT NULL,
    exchange_number INTEGER NOT NULL,
    message TEXT NOT NULL,
    should_end INTEGER NOT NULL DEFAULT 0,
    end_reason TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (speaker_id) REFERENCES characters(id)
);
```

Recommended database methods:

- `create_conversation(...)`
- `append_conversation_message(...)`
- `complete_conversation(...)`
- `create_memory(...)`
- `create_event(...)`

### Ollama integration

The conversation service should not call Ollama directly. It should depend on a thin `llm_client` interface so the same action code works with either Ollama Cloud or local Ollama.

Recommended interface shape:

```python
reply = llm_client.generate_chat(
    system_prompt=system_prompt,
    messages=messages,
    response_schema=ConversationReplySchema,
)
```

Recommended provider behavior:

- `llm_client.py` chooses Ollama Cloud or local Ollama from configuration
- conversation code only knows about structured request/response contracts
- tests replace `llm_client` with a fake deterministic client

That keeps the "free via Ollama" requirement compatible with CI and unit testing.

### Recommended default model

Use `qwen3:30b` as the default model for this PR.

Why this model:

- it is a strong fit for role-playing, multi-turn dialogue, and instruction following
- it is positioned by Ollama's official library as a strong agent-capable model
- it is a better fit for this simulation workload than a coding-only model

Recommended fallback:

- if local hardware cannot support `qwen3:30b`, fall back to `qwen3:8b`

Recommended configuration:

- `OLLAMA_MODEL=qwen3:30b`
- `OLLAMA_MODE=cloud` by default
- `OLLAMA_BASE_URL=https://ollama.com/api` by default
- switch to `OLLAMA_MODE=local` and `OLLAMA_BASE_URL=http://localhost:11434` when running against a local Ollama instance

### Event examples

- `"Alice started a conversation with Bob in the kitchen."`
- `"Alice and Bob talked in the kitchen and wrapped up naturally."`

### Important edge cases

- target is no longer in the room
- target is the acting character
- conversation ends immediately because one character refuses
- malformed model response
- transcript reaches 50 exchanges

## Action 3: Room Update

### Goal

Allow a character to meaningfully change a room's description while keeping the room's identity stable.

This action should support changes like:

- unpacking boxes
- decorating for a holiday
- making a room look messy or lived in
- leaving visible evidence of a fire or accident
- blowing the room up and leaving it ruined
- rebuilding the room later into something cleaner or restored

The room name or identity should not change, but the description can change dramatically over time.

### Recommended room model

Keep this simple:

- room identity stays fixed by the room's stable identifier and name
- the mutable part is the room description
- every character can influence that description on their turn

This avoids duplicating concepts like `base_description` and `room_rules`, and it does not require replacing the current room structure other developers are already using.

### Prompt guardrails

Keep this simple: the room update prompt should instruct the model to:

- only describe changes to the current room
- keep the room name unchanged
- avoid describing changes to other rooms
- always return a usable replacement description

Allowed changes can be mild or extreme:

- visual appearance
- clutter
- decorations
- cleanliness
- signs of recent use
- major damage
- total destruction
- later rebuilding or restoration

### Suggested implementation approach

Use a simple two-step flow:

1. Generate a proposed update in structured form
2. If the response parses and includes a usable description, write it to the database

Suggested structured fields:

- `new_description`
- `change_summary`
- `change_tags`

If the model response is malformed or empty, treat the action as a no-op and move on.

### Persistence needs

Keep the existing room structure intact.

Recommended v1 approach:

- continue using the existing room record
- treat the room name or stable identifier as permanent
- update the existing room description field when a change is accepted

Optional later additions if the team wants more traceability:

- `last_modified_by`
- `last_modified_turn`
- a room-change history table

### Event examples

- `"Alice updated the living room by unpacking the last moving boxes."`
- `"Bob decorated the dining room for a holiday gathering."`

## Orchestrator-Owned Room Backlog

The backlog behavior you described belongs in the orchestrator plan, not here.

This branch should assume:

- the orchestrator delivers unseen room-local events at the start of a character turn
- action handlers can read that backlog through `ActionContext`
- action handlers emit canonical events, but do not fan them out to other characters

That separation keeps action code small and prevents this branch from absorbing turn-engine behavior.

## Suggested Database Direction

Keep `sim/core/database.py` as the single database gateway for now, but extend it with focused methods instead of burying SQL inside action modules.

Recommended additions:

- `get_room(room_id)`
- `get_all_rooms()`
- `get_characters_in_room(room_id)`
- `create_conversation(...)`
- `append_conversation_message(...)`
- `complete_conversation(...)`
- `create_memory(...)`
- `update_room_description(...)`
- `create_event(...)`

Backlog-specific reads or delivery cursors belong to the orchestrator branch.

## Orchestrator Interaction Rules

The orchestrator should treat these actions as independent services.

This branch should assume:

1. the orchestrator has already chosen whether the action runs
2. the orchestrator provides the correct `ActionContext`
3. the action handler performs prompt execution, persistence, and canonical event creation
4. the orchestrator decides how those events are delivered to later actors

## Makefile Plan

Add a root `Makefile` so the repo can be set up, tested, and launched with short commands that mirror the README setup flow.

Recommended targets:

- `make setup`
- `make test`
- `make run`
- `make ollama-check`
- `make ollama-pull`

Recommended behavior:

- `setup` creates `.venv`, upgrades `pip`, and installs `requirements.txt`
- `test` runs the unit test suite
- `run` launches `python main.py`
- `ollama-pull` downloads the configured default model
- `ollama-check` pings the configured Ollama endpoint and prints a clear message if it is unreachable

Recommended variables:

- `VENV=.venv`
- `PYTHON=$(VENV)/bin/python`
- `PIP=$(PYTHON) -m pip`
- `OLLAMA_BASE_URL ?= https://ollama.com/api`
- `OLLAMA_MODEL ?= qwen3:30b`
- `OLLAMA_MODE ?= cloud`

Recommended local-Ollama check:

- when `OLLAMA_MODE=local`, `make run` should call `ollama-check` first
- `ollama-check` should probe `$(OLLAMA_BASE_URL)/api/tags`
- if the endpoint is unreachable, print a user-facing message such as:
  `"Ollama is not running at $(OLLAMA_BASE_URL). Start Ollama or switch to cloud mode before launching the app."`

Recommended cloud behavior:

- default to Ollama Cloud for model-backed actions
- if the project is configured for Ollama Cloud, skip the local-running check
- keep the same `llm_client` interface and change only configuration

Recommended app-side behavior:

- before the first model-backed action, if `OLLAMA_MODE=local`, ping the configured Ollama endpoint
- if it is unavailable, surface a clear console or UI message instead of failing silently
- treat the turn action as unavailable until Ollama becomes reachable

This keeps developer workflow simple and makes setup, testing, and launch easy to demo.

## Testing Plan

The current project already uses `unittest` and a GitHub Actions workflow. Stay with that for now.

### Unit tests

Add direct tests for:

- movement success and stay behavior
- invalid movement targets
- conversation termination behavior
- conversation transcript continuity for both speakers
- conversation memory creation for both participants
- forced termination at 50 exchanges
- room update parsing and persistence behavior

### Integration tests

Use temporary SQLite databases to verify:

- movement updates `current_room_id` and creates events
- conversation writes transcript rows, summary events, and participant memories
- room updates persist the new room description

### Contract tests

Because LLM output can drift, add parser/contract tests for structured responses:

- missing fields
- wrong types
- invalid enum values
- oversized text

These are high-value tests for CI because they catch prompt/response-shape breakage early.

## CI/CD Plan

You already have `.github/workflows/tests.yml` running `python -m unittest discover tests`.

Recommended follow-up improvements:

1. Keep all new action tests inside `tests/` so they automatically run in CI
2. Change the workflow command to `python -m unittest discover -s tests -v` for clearer logs
3. Optionally add a fast syntax gate such as `python -m compileall sim tests`
4. Add schema migration tests if you introduce migration scripts later
5. Keep the `Makefile` targets aligned with CI commands so local and CI workflows match

This keeps the CI story simple but visibly professional for the project demo.

## Single PR Scope

This work should stay in one PR.

Recommended contents of the PR:

- add action schemas
- add database methods
- avoid room-schema churn unless traceability fields are later needed
- implement movement service
- add movement events
- implement synchronous conversation loop
- add transcript persistence
- add participant-specific memory writes
- add Ollama-backed `llm_client` integration behind an interface
- implement room update service
- add prompt instructions for room-update guardrails
- add description persistence and tests
- add the root `Makefile` for setup, testing, Ollama checks, model pull, and app launch
- add app-side notification when local Ollama is required but unavailable
- add unit and integration tests for the action layer

## Recommended Initial Acceptance Criteria

Movement is done when:

- a character can stay or move to any existing room
- invalid moves fail safely
- movement creates visible events for later turns

Conversation is done when:

- a character can target another character in the same room
- the loop terminates cleanly
- both speakers receive the same complete transcript context throughout the loop
- the transcript, summary event, and participant memories are persisted
- the 50-exchange cap is enforced

Room update is done when:

- a character can change the room description
- the room name remains unchanged
- the updated description is visible to later actors

## Final Recommendation

The cleanest implementation is:

- one service per action
- one database layer for persistence
- prompt-driven guardrails with only minimal mechanical checks in code
- one default model choice for the branch instead of delaying the decision
- one simple `Makefile` for setup, test, model prep, and launch
- a strict boundary where the orchestrator owns turn flow and room-event backlog delivery

That gives you a good CI/CD story, keeps the code reviewable, and avoids coupling this branch to turn orchestration or backlog fan-out logic.

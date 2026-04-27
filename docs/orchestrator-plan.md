# Orchestrator Plan

## Purpose

This document defines the plan for the actual simulation orchestrator now that the action layer already exists.

The action branch added:

- `sim/actions/movement.py`
- `sim/actions/conversation.py`
- `sim/actions/room_update.py`
- `sim/actions/schemas.py`
- `sim/agents/conversation_agent.py`
- `sim/agents/room_update_agent.py`
- `sim/services/llm_client.py`
- conversation persistence in `sim/core/database.py`
- tests for movement, conversation, room updates, and the Ollama client

The orchestrator work should build on those files, not replace them.

## Current Code State

As of April 26, 2026, the repo already has a real action layer but still does not have a real turn engine.

What exists now:

- `Simulation` owns runtime state, database setup, and the Ollama client
- `Database` persists rooms, characters, events, memories, conversations, and conversation messages
- movement, conversation, and room-update actions can already execute independently
- `ActionContext` already exists and includes `room_event_backlog`
- the Pygame window still runs a blank loop
- `Simulation.step()` still only increments a tick counter and appends `"simulation advanced"`
- there is no orchestrator object yet
- there is no action-selection agent yet
- there is no unseen-event backlog implementation yet
- there are no start/pause/resume/stop UI controls yet

I also re-ran the current suite from the project root:

- `python -m unittest discover -s tests -v`
- result: 15 tests passed

## What This Plan Should Optimize For

- keep the existing action modules as the execution surface
- add only the missing orchestration layer
- keep prompt-building concerns in `sim/agents/`
- keep transport/configuration concerns in `sim/services/llm_client.py`
- keep SQL in `sim/core/database.py`
- make backlog delivery and room summaries deterministic enough to test

## Boundary Between Action Layer and Orchestrator

The action layer already owns:

- movement execution
- synchronous conversation execution
- room description updates
- transcript persistence
- memory writes after conversations
- canonical event creation for action results

The orchestrator should own:

- turn order
- action selection per character
- when each action is called
- start-of-turn backlog delivery
- building the `ActionContext`
- carrying state forward from one actor to the next within the same world turn
- UI-visible turn results

The orchestrator should not:

- duplicate action logic already implemented in `sim/actions/`
- move prompt logic out of the current agent files unless there is a real blocker
- bury new SQL directly inside orchestrator methods

## Recommended File Additions

Keep the current structure and add only the missing pieces:

```text
sim/
  core/
    orchestrator.py
  agents/
    turn_planner_agent.py
  services/
    room_backlog.py
  ui/
    layout.py
    scene_state.py
tests/
  test_orchestrator.py
  test_room_backlog.py
```

Optional later additions:

```text
sim/
  services/
    room_summary.py
```

Do not introduce a new `prompts/` tree or a second action framework in this PR. The repo already has a workable shape.

## Orchestrator Object

Recommended constructor shape:

```python
class Orchestrator:
    def __init__(self, database: Database, llm_client: OllamaClient) -> None:
        ...
```

Recommended owned dependencies:

- `MovementAction`
- `ConversationAction`
- `RoomUpdateAction`
- `TurnPlannerAgent`
- `RoomBacklogService`

Recommended `Simulation` integration:

```python
self.orchestrator = Orchestrator(
    database=self.database,
    llm_client=self.llm_client,
)
```

Then `Simulation.step()` should delegate instead of writing a placeholder tick log.

## Turn Contract

One call to `orchestrator.run_turn()` should execute one full world turn across all active characters.

Recommended flow:

1. Increment the turn number.
2. Load the current room and character state from the database.
3. Determine the actor order for this turn.
4. For each actor:
   1. reload the actor from the database
   2. reload the actor's current room
   3. deliver unseen room-local events for that actor/room
   4. build the `ActionContext`
   5. ask the planner for the next action
   6. execute that action
   7. rebuild context and ask again until the actor ends the turn or exhausts the three action types
5. Collect public summaries for the UI and event log.
6. Return a small result object for `Simulation`.

The important rule is not a fixed global order. The important rule is:

- each action type can be used at most once per actor turn
- the planner can choose the next unused action after each completed action

That better matches the game logic because movement, conversation, and room updates can all change what makes sense next.

## Turn Planning Layer

The repo does not yet have a component that decides which actions a character wants to take. That is the main missing piece between `Simulation.step()` and the action services.

### Recommended new agent

Add:

- `sim/agents/turn_planner_agent.py`

Its job should be to make one action decision at a time against the actor's current context.

### Why sequential replanning is better

Do not make the actor commit to all actions at the very start of the turn.

That would be brittle because context can change after each action:

- after a conversation, the actor may want to leave
- after moving, the actor may want to update the new room
- after entering a new room, different conversation targets may be available

So the orchestrator should let the actor re-decide after each completed action.

### Recommended planner contract

Each planner call should answer:

- what single action to do next
- the action-specific payload
- whether the actor wants to end the turn now

Example shape:

```json
{
  "next_action": "move",
  "move_target_room_id": "kitchen",
  "conversation_target_character_id": null,
  "room_update_intent": null,
  "end_turn": false
}
```

After that action resolves, the orchestrator should rebuild context and ask again.

### Recommended per-turn flow

For each actor:

1. build current context
2. ask planner for the next action
3. execute the chosen action if valid
4. reload actor and room state from the database
5. rebuild context with any new room, occupants, and backlog effects
6. ask again until:
   - the actor returns `end_turn = true`
   - no valid action is selected
   - all three optional action types have already been used

### Action usage rule

To stay aligned with the issue wording, each action type should be available at most once per actor turn:

- one move or stay decision
- one conversation initiation
- one room update

That still allows a valid sequence like:

1. talk with someone in the current room
2. move to another room
3. update that new room

or:

1. move first
2. talk in the new room
3. end turn without a room update

### Why this shape

It preserves the current action modules while giving the orchestrator the flexibility to react to changed world state inside the same actor turn.

## Actor Context

Use the existing `ActionContext` dataclass in `sim/actions/schemas.py` as the baseline shared context.

Current fields already fit the orchestrator:

- `turn_number`
- `character`
- `current_room`
- `characters_in_current_room`
- `room_event_backlog`

Do not replace that object in the orchestrator PR unless there is a concrete need.

## Room Backlog

This is still the trickiest orchestrator requirement, and it is not implemented yet.

### Required behavior

If `A` acts before `D` in the same room on turn 6, `D` should see `A`'s room-local events when `D`'s turn starts.

If `B` acts before `C` in the same room, `B` should not retroactively see `C`'s later actions until `B`'s next turn.

If a character moves into a different room during their own turn, they should immediately receive the unseen backlog for the destination room before choosing their next same-turn action.

The backlog should only include room-local events that happened since that character last took a turn. Older room history should not be replayed just because the character never consumed it.

That means backlog delivery must be:

- room-local
- per-character
- based on canonical events
- limited to events newer than the actor's last completed turn
- consumed at turn start
- also consumable immediately after entering a new room mid-turn

### Recommended implementation

Add a small `RoomBacklogService` that works from:

- the actor's last completed turn
- room-scoped canonical events
- an in-memory set of event ids already delivered to that actor during the current turn

Recommended persisted field:

- `characters.last_completed_turn INTEGER NOT NULL DEFAULT 0`

Recommended behavior:

- when an actor begins their turn, record `turn_floor = character.last_completed_turn`
- backlog queries only return events for the relevant room where `turn_number > turn_floor`
- if the actor moves mid-turn, query the destination room using that same `turn_floor`
- within the same actor turn, avoid duplicate deliveries by tracking which event ids have already been shown to that actor
- when the actor finishes their turn, update `last_completed_turn` to the current turn number

Recommended service responsibilities:

- load room events newer than the actor's last completed turn
- return them as backlog lines for `ActionContext.room_event_backlog`
- suppress duplicates already delivered during the actor's active turn
- help the orchestrator mark the actor's turn as completed at the end

This keeps the source of truth simple:

- `events` stays canonical
- `last_completed_turn` defines the oldest turn the actor should care about
- per-turn delivered event ids prevent repeated backlog lines inside the same active turn

### Delivery rule

The orchestrator should deliver backlog in two places:

1. at the start of the actor's turn for their current room
2. immediately after a successful move, for the destination room, before the planner is asked what to do next

That second delivery is required so the actor can enter a room, see what is already happening there, and then make an informed same-turn choice about conversation or room updates.

### Important cutoff rule

If a character last acted on turn `5`, then on turn `6` they should only receive room-local events with `turn_number > 5`.

They should not receive:

- older events from turn `5` or earlier
- old destination-room history they happened to never see
- repeated copies of events already delivered earlier in their current turn

## "What Just Happened" Logic

The action branch already assumes `room_event_backlog` exists. The orchestrator should make that field real.

For v1, do not overbuild this.

Recommended behavior:

- backlog is the primary start-of-turn awareness mechanism
- backlog is also the primary post-move awareness mechanism
- the orchestrator passes raw backlog lines into `ActionContext`
- if needed, add a small derived summary later for prompt compression

That means the first orchestrator PR does not need a complex room-summary engine. Backlog delivery alone already solves the main gameplay problem you described.

Optional follow-up:

- once the backlog is working, add `room_summary.py` to condense long recent event lists for prompts

## Event Model Guidance

The current `events` table only stores:

- `turn_number`
- `character_id`
- `room_id`
- `log`

That is enough to start backlog delivery.

Recommended approach for the orchestrator PR:

- keep the current event schema working as-is
- do not block orchestrator work on adding typed event payloads

Optional later improvement:

- add nullable `event_type`
- add nullable `payload_json`

That would help richer room summaries later, but it should be treated as a follow-up unless backlog logic becomes too brittle with text-only events.

## Simulation Integration

`Simulation` already has:

- `database`
- `llm_client`
- runtime flags
- a `db_path` override useful for tests

Recommended changes:

1. construct `Orchestrator` in `__post_init__`
2. replace placeholder logic in `step()`
3. keep `start` and `pause` in `Simulation`, with `start` also serving as resume
4. add two explicit reset methods with different scopes
5. keep `update(dt)` as the frame/timer loop that calls `step()`

Recommended `step()` behavior:

```python
def step(self) -> None:
    result = self.orchestrator.run_turn()
    self.tick_count = result.turn_number
    self.event_log.extend(result.public_log_entries)
    self.event_log = self.event_log[-50:]
```

## UI Integration

The current window is still blank. For this project, the UI needs to show the simulation state clearly enough that someone can watch characters occupy rooms and move between them turn by turn.

### Required world display

The main simulation view should show:

- all rooms at once as rectangles in a grid-like layout
- each room labeled with its room id or room name
- each character as a small colored token inside their current room
- the current turn number
- `Start`, `Pause`, `Reset Simulation`, and `Reset World` controls
- a recent-event or status area
- an Ollama warning message when model-backed actions are unavailable

### Room grid layout

All rooms should be displayed simultaneously in a responsive grid.

Recommended behavior:

- each room renders as an empty bordered rectangle
- room rectangles are laid out in a global grid that adapts to the number of rooms
- the global room grid recomputes when the window is resized

Recommended KISS layout rule:

- `columns = ceil(sqrt(room_count))`
- `rows = ceil(room_count / columns)`
- compute room rectangle sizes from the available drawable area after reserving space for controls and status text

That gives a simple dynamic layout without introducing a complex layout engine.

### Character token rendering

Each character should render as a small box inside the room rectangle they currently occupy.

Required token behavior:

- the token is a small filled square or rounded rectangle
- the token color is stable for that character across frames
- the first letter of the character's name is centered inside the token
- if multiple characters share a room, their tokens are arranged in a dynamic sub-grid inside that room

Important implementation rule:

- do not generate a new random color every frame
- derive a stable pseudo-random color from the character id or name so the same character always keeps the same color

### In-room character grid

Each room needs its own dynamic layout for occupants.

Recommended behavior:

- if a room has `n` characters, compute a square-ish sub-grid for just that room
- token positions update when room occupancy changes
- token positions also update when the window is resized

Recommended KISS layout rule:

- `token_columns = ceil(sqrt(character_count))`
- `token_rows = ceil(character_count / token_columns)`
- tokens are placed inside the room's inner content area with padding

This allows:

- one centered token when a room has one occupant
- a compact expanding grid when more people enter
- a visibly empty room rectangle when no one is present

### Visible movement between rooms

Characters should visibly move from room to room, not just disappear from one rectangle and appear in another on the next frame.

Recommended v1 animation behavior:

- when a character's `current_room_id` changes, animate the token from the old room position to the new room position
- use a short fixed transition such as `0.25` to `0.4` seconds
- the movement path can be a simple straight-line interpolation in v1
- after the animation completes, the token settles into its destination slot within the destination room's occupant grid

Important UI ownership rule:

- the orchestrator only changes the world state
- the UI detects room changes between scene snapshots and handles the animation locally

### UI state contract

The UI should render from one simulation snapshot, not from ad hoc database calls and not from direct action-module access.

Recommended `Simulation` method:

- `get_scene_state()` or `get_world_snapshot()`

Recommended snapshot contents:

- current turn number
- all rooms
- all characters
- each character's current room id
- recent public event log entries
- current runtime flags such as running and paused
- current startup warning, if any

### Suggested UI helper files

To keep `sim/ui/window.py` maintainable, split layout and animation state out of it.

Recommended responsibilities:

- `sim/ui/layout.py`
  - compute the global room grid rectangles
  - compute token slots within each room
  - recompute layouts when the window changes size
- `sim/ui/scene_state.py`
  - store the last rendered snapshot
  - detect room changes for characters
  - keep in-flight token animation state

`window.py` should stay focused on:

- the Pygame event loop
- window resize handling
- button handling
- calling `simulation.update(dt)`
- requesting the latest scene snapshot
- drawing from layout and scene-state helpers

### Controls and HUD

Recommended UI scope:

- add `Start`, `Pause`, `Reset Simulation`, and `Reset World` buttons to `sim/ui/window.py`
- surface current turn number
- surface recent event log
- surface the Ollama startup warning if model-backed actions are unavailable

Recommended control behavior:

- `Start` begins turn advancement when the simulation is idle
- `Start` also doubles as resume when the simulation is paused
- `Pause` should not interrupt the active character mid-turn; it should let the current character finish their full turn and then stop before the next character begins
- if the simulation is paused between characters, clicking `Start` resumes with the next character in the current turn, or starts the next turn if the pause happened after the last character
- `Reset Simulation` clears turn progress, event history, conversations, and memories, but keeps the current rooms and characters
- `Reset World` clears the whole simulation state, including rooms and characters

Recommended runtime behavior:

- `pause()` should request a pause at the next safe boundary between character turns, not in the middle of one actor's multi-action sequence
- `start()` should work for both first launch and resume from pause
- `reset_simulation()` should preserve room and character records while clearing derived history/state
- `reset_world()` should fully clear rooms, characters, and derived state

### Resize behavior

The window should respond to resize events by recomputing:

- the global room grid
- each room's occupant token grid
- token label placement

The layout should preserve padding and avoid letting tokens spill outside room bounds.

### Recommended initial rendering style

For the first UI pass, keep the visuals simple:

- neutral or dark background
- outlined room rectangles
- centered room labels
- solid-color character tokens
- single-letter token labels
- simple straight-line movement animation

Do not block the orchestrator work on advanced styling.

Important boundary:

- the UI should only call `Simulation`
- the UI should render from scene snapshots derived from `Simulation`
- the UI should never call `MovementAction`, `ConversationAction`, or `RoomUpdateAction` directly

## Database Changes Needed for Orchestrator Work

The action branch already added the conversation tables and supporting methods. The orchestrator PR should stay narrow.

Recommended required additions:

- `characters.last_completed_turn`
- database method to fetch room events newer than a given turn
- database method to update a character's completed-turn marker

Implement all of the following methods unless they already exist in `sim/core/database.py`:

- `get_room_events_since_turn(room_id, after_turn, limit=None)`
- `update_character_last_completed_turn(character_id, turn_number)`
- `get_character(character_id)` using the new `last_completed_turn` field

Database rule for this work:

- if a method is listed in this section and it is missing, add it
- if an equivalent method already exists, reuse it instead of creating a duplicate
- keep `Database` as the single SQL gateway for orchestrator-related reads and writes

## Testing Plan

The action branch already proved the isolated services. The orchestrator tests should focus on coordination behavior.

### Unit tests

- orchestrator supports sequential replanning within one actor turn
- actor can talk, then move, then update a new room in the same turn
- each action type can run at most once per actor turn
- actor later in the same room receives earlier actor backlog events
- actor who enters a new room mid-turn receives destination-room backlog before replanning
- actor only receives room-local backlog newer than their own last completed turn
- actor does not receive events that happen after their turn until next turn
- `Simulation.step()` delegates to the orchestrator
- `Start` and `Pause` gate turn advancement correctly at character boundaries
- `Reset Simulation` preserves rooms and characters while clearing derived history/state
- `Reset World` clears the full world state

### Integration tests

Use temporary SQLite databases and fake model clients to verify:

- a full turn across multiple characters
- movement changes later conversation eligibility
- conversation can change the actor's later choice in the same turn
- conversation events become visible to later actors in the same room
- destination-room backlog is delivered immediately after movement and affects the actor's next same-turn decision
- backlog excludes older room history from before the actor's last completed turn
- room updates are visible to later actors after the update commits
- backlog delivery is idempotent within the actor's active turn
- simulation reset clears history without deleting rooms and characters
- world reset clears rooms and characters as well

### Keep using the current test style

Stay with:

- `unittest`
- temporary per-test SQLite databases
- fake LLM clients

That already matches the existing suite and keeps CI simple.

## CI/CD Notes

The current repo now has a root `Makefile`, but one operational detail matters:

- tests must run from the project root

I verified:

- running `python -m unittest discover -s tests -v` from `Linux and DevOps/334-Final-Project` passes
- running discovery from the parent directory fails because `sim` is not importable there

So the orchestrator PR should keep CI and local commands anchored to the repo root.

Recommended CI follow-up:

- keep `python -m unittest discover -s tests -v`
- optionally add `python -m compileall sim tests`

## Recommended PR Scope Now

Because the action layer already landed, the orchestrator should be its own PR.

Recommended contents:

- add `sim/core/orchestrator.py`
- add `sim/agents/turn_planner_agent.py`
- add `last_completed_turn` support to `Database`
- wire `Simulation.step()` into the orchestrator
- add orchestrator and backlog tests
- add room-grid rendering, character-token rendering, and UI controls only if that remains reviewable in the same PR

If UI controls make the PR noisy, split them into a follow-up PR after the turn engine lands.

## Acceptance Criteria

The orchestrator work is done when:

- one call to `Simulation.step()` advances one full world turn
- each actor can independently choose up to the three existing actions
- the actor can re-decide after each completed action inside the same turn
- action execution uses the current action modules, not duplicate logic
- later actors in the same room receive unseen earlier room events that turn
- actors who enter a room mid-turn receive that room's unseen backlog before their next decision
- backlog only includes room-local events newer than the actor's own last completed turn
- earlier actors do not see later events until their next turn
- conversations and room updates persist through the existing database layer
- the event log shown by `Simulation` reflects real turn outcomes instead of placeholder tick text
- `Pause` waits for the current character to finish before stopping advancement
- `Reset Simulation` clears history/memory while preserving rooms and characters
- `Reset World` clears rooms and characters too

## Final Recommendation

The correct move now is not to redesign the action layer. It is to add the missing turn engine around the code that already exists.

The cleanest orchestrator implementation is:

- one orchestrator object in `sim/core/orchestrator.py`
- one planner agent that returns a minimal structured action plan
- one backlog service backed by event cursors
- zero duplicate action logic
- small, coordination-focused tests

That keeps the repo modular, respects the work already merged, and directly addresses the still-open simulation problem.

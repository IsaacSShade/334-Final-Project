from sim.core.simulation import Simulation
from sim.ui.window import Window


def run_app():
  simulation = Simulation()
  startup_warning = simulation.get_model_startup_warning()
  if startup_warning:
    simulation.event_log.append(startup_warning)
    print(startup_warning)

  simulation.load_from_db()
  _run_startup_menu(simulation)

  window = Window(simulation)
  window.run()


def _run_startup_menu(simulation: Simulation) -> None:
  """
  Purpose:
    Offer the user a small console menu before launching the pygame window
    so rooms can be managed without leaving the app. Room mutations are
    written through to the database, so the window's own load_from_db
    on launch will see them.

  Inputs:
    simulation: The Simulation that the menu mutates.

  Outputs:
    None.
  """
  menu = (
    "\n=== Startup Menu ===\n"
    "1) Manage rooms\n"
    "2) Start simulation\n"
  )
  while True:
    print(menu)
    choice = input("Choose an option: ").strip()
    if choice == "1":
      simulation.manage_rooms()
    elif choice == "2" or choice.lower() in {"start", "run", "go", ""}:
      return
    else:
      print("Unknown option. Please choose 1-2.")

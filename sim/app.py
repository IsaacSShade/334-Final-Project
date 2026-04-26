from sim.core.simulation import Simulation
from sim.ui.window import Window

def run_app():
  simulation = Simulation()
  startup_warning = simulation.get_model_startup_warning()
  if startup_warning:
    simulation.event_log.append(startup_warning)
    print(startup_warning)
  window = Window(simulation)
  window.run()

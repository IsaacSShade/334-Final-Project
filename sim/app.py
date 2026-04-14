from sim.core.simulation import Simulation
from sim.ui.window import Window

def run_app():
  simulation = Simulation()
  window = Window(simulation)
  window.run()

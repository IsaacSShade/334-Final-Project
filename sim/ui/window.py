import sys
import pygame


class Window:
	"""
	Purpose:
		Create and run the main pygame window for the project.

	Inputs:
		simulation: The Simulation object that stores the current app/sim state.

	Outputs:
		None. Opens a window and keeps it alive until the user closes it.
	"""

	def __init__(self, simulation) -> None:
		"""
		Purpose:
			Initialize the window wrapper and store the simulation reference.

		Inputs:
			simulation: The Simulation object used by the app.

		Outputs:
			None.
		"""

		self.simulation = simulation
		self.width = 1280
		self.height = 720
		self.title = "DevOps Town" # We need to replace this later with a real name lol

	def run(self) -> None:
		"""
		Purpose:
			Start the pygame app loop, update the simulation, and draw a blank screen.

		Inputs:
			None.

		Outputs:
			None. Opens the window and runs until closed.
		"""

		pygame.init()

		screen = pygame.display.set_mode((self.width, self.height))
		pygame.display.set_caption(self.title)
		clock = pygame.time.Clock()

		running = True
		while running:
			dt = clock.tick(60) / 1000.0

			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					running = False

			self.simulation.update(dt)

			screen.fill((20, 20, 28))
			pygame.display.flip()

		pygame.quit()
		sys.exit()

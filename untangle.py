#!/usr/bin/python

# Untangle game, ported to python and cairo
# Copyright (C) 2008 Darrick J. Wong

import gtk
import math
import sys

def distance(x1, y1, x2, y2):
	"""Calculate the distance between two points."""
	return math.hypot(x2 - x1, y2 - y1)

class Vertex:
	def __init__(self, x, y):
		"""Create a vertex with specified coordinates."""
		self.x = x
		self.y = y

	def clamp(self):
		"""Clamp coordinates."""
		def clamp(n):
			"""Clamp value between 0 and 1."""
			if n < 0:
				return 0
			elif n > 1:
				return 1
			return n
		self.x = clamp(self.x)
		self.y = clamp(self.y)

class Edge:
	def __init__(self, v1, v2):
		"""Create an edge between two vertices."""
		self.v1 = v1
		self.v2 = v2
		self.collision = False

	def __str__(self):
		return "(%f, %f) -> (%f, %f)" % (self.v1.x, self.v1.y, self.v2.x, self.v2.y)

VERTEX_RADIUS = 5
class App:
	def __init__(self, is_editor):
		"""Create program controller."""
		self.vertices = []
		self.edges = []
		self.window = gtk.Window()
		self.canvas = GameFace()
		self.drag_vertex = None
		self.keymap = {
			gtk.keysyms.Tab: self.tab_key_press,
			gtk.keysyms.Up: self.arrow_key_press,
			gtk.keysyms.Down: self.arrow_key_press,
			gtk.keysyms.Left: self.arrow_key_press,
			gtk.keysyms.Right: self.arrow_key_press,
			gtk.keysyms.q: self.q_key_press,
		}
		editor_keymap = {
			gtk.keysyms.n: self.n_key_press,
			gtk.keysyms.s: self.s_key_press,
			gtk.keysyms.l: self.l_key_press,
		}
		self.is_editor = is_editor
		if self.is_editor:
			self.keymap.update(editor_keymap)
		self.level = 0

	def pollinate(self):
		"""Create a default set of vertices/edges."""
		v1 = Vertex(0.2, 0.2)
		v2 = Vertex(0.8, 0.2)
		v3 = Vertex(0.8, 0.8)
		v4 = Vertex(0.2, 0.8)

		e1 = Edge(v1, v2)
		e2 = Edge(v2, v3)
		e3 = Edge(v3, v4)
		e4 = Edge(v4, v1)
		e5 = Edge(v1, v3)
		e6 = Edge(v2, v4)

		self.vertices = [v1, v2, v3, v4]
		self.edges = [e1, e2, e3, e4, e5, e6]
		self.drag_vertex = None
		assert self.check_sanity()

		self.find_collisions()

	def save(self, fname):
		"""Save the current game."""
		fp = file(fname, "w")
		for vertex in self.vertices:
			fp.write("v: %f, %f\n" % (vertex.x, vertex.y))
		for edge in self.edges:
			fp.write("e: %d, %d\n" % (self.vertices.index(edge.v1), self.vertices.index(edge.v2)))
		fp.close()

	def load(self, fname):
		"""Load a game."""
		fp = file(fname, "r")
		vertices = []
		edges = []
		for line in fp:
			if line.startswith("v:"):
				args = line.split(" ")
				state = 0
				for arg in args:
					if state == 0 and arg == "v:":
						state = state + 1
					elif state == 1:
						arg = arg.strip(", ")
						x = float(arg)
						state = state + 1
					elif state == 2:
						arg = arg.strip(", ")
						y = float(arg)
						state = state + 1
					elif state == 3:
						break;
				if state == 3:
					v = Vertex(x, y)
					vertices.append(v)
			elif line.startswith("e:"):
				args = line.split(" ")
				state = 0
				for arg in args:
					if state == 0 and arg == "e:":
						state = state + 1
					elif state == 1:
						arg = arg.strip(", ")
						x = int(arg)
						state = state + 1
					elif state == 2:
						arg = arg.strip(", ")
						y = int(arg)
						state = state + 1
					elif state == 3:
						break;
				if state == 3:
					e = Edge(vertices[x], vertices[y])
					edges.append(e)
		fp.close()
		self.vertices = vertices
		self.edges = edges
		self.drag_vertex = None
		if not self.check_sanity():
			self.vertices = []
			self.edges = []
		self.canvas.queue_draw()

	def check_sanity(self):
		"""Check for obvious errors."""
		known_edges = []
		for edge in self.edges:
			if (edge.v1, edge.v2) in known_edges:
				print "Error, multiple edges between two vertices."
				return False
			known_edges.append((edge.v1, edge.v2))
			known_edges.append((edge.v2, edge.v1))
		for vertex in self.vertices:
			vertex.clamp()
		return True

	def find_collisions(self):
		"""Figure out which lines intersect."""
		def is_between(a, x0, x1):
			"""Determine if a is between x0 and x1."""
			if a > max(x0, x1):
				return False
			if a < min(x0, x1):
				return False
			return True

		for edge in self.edges:
			edge.collision = False

		for e1 in self.edges:
			for e2 in self.edges:
				if e1 == e2:
					continue

				numerator_a = (e2.v2.x - e2.v1.x)*(e1.v1.y - e2.v1.y) - (e2.v2.y - e2.v1.y)*(e1.v1.x - e2.v1.x)
				numerator_b = (e1.v2.x - e1.v1.x)*(e1.v1.y - e2.v1.y) - (e1.v2.y - e1.v1.y)*(e1.v1.x - e2.v1.x)
				denominator = (e2.v2.y - e2.v1.y)*(e1.v2.x - e1.v1.x) - (e2.v2.x - e2.v1.x)*(e1.v2.y - e1.v1.y)

				#print "--------"
				#print e1, e2
				#print numerator_a, numerator_b, denominator
				# Deal with edges that have common points
				verts = set()
				for vert in [e1.v1, e1.v2, e2.v1, e2.v2]:
					verts.add((vert.x, vert.y))
				if len(verts) == 3:
					# Three vertices means they're attached to the same point
					#print "3 verts, go away?"
					if numerator_a == 0 and numerator_b == 0 and denominator == 0:
						e1.collision = True
						e2.collision = True
					continue
				elif len(verts) == 2:
					# Coincident
					e1.collision = True
					e2.collision = True
					continue

				# Deal with all other lines
				# Shamelessly stolen from http://local.wasp.uwa.edu.au/~pbourke/geometry/lineline2d/
				#print "--------"
				# Coincident or parallel lines
				if denominator == 0:
					# Test for coincidence
					if numerator_a == 0 and numerator_b == 0:
						e1.collision = True
						e2.collision = True
						continue
					# Parallel
					continue

				ua = numerator_a / denominator
				ub = numerator_b / denominator

				# Intersection of line segments
				if ua > 0 and ua < 1 and ub > 0 and ub < 1:
					e1.collision = True
					e2.collision = True

	def is_solved(self):
		"""Determine if the puzzle is solved (i.e. no collisions)"""
		self.find_collisions()
		for edge in self.edges:
			if edge.collision:
				return False
		return True

	def run_gtk(self):
		"""Start GTK app."""
		self.canvas.draw_hook = self.draw
		self.canvas.press_hook = self.mouse_down
		self.canvas.release_hook = self.mouse_up
		self.canvas.move_hook = self.mouse_move
		self.window.add(self.canvas)
		self.window.connect("destroy", gtk.main_quit)
		self.window.connect("key_press_event", self.key_press)
		self.window.show_all()
		gtk.main()

	def draw(self, context, rect):
		"""Draw game elements."""
		global VERTEX_RADIUS
		self.find_collisions()

		# Draw outer box
		context.set_line_width(1)
		context.rectangle(rect.x, rect.y, rect.width, rect.height)
		context.set_source_rgb(0.8, 0.8, 1)
		context.fill_preserve()
		context.set_source_rgb(0, 0, 0)
		context.stroke()

		# Draw lines
		context.set_line_width(2)
		for edge in self.edges:
			x1 = rect.width * edge.v1.x + rect.x
			y1 = rect.height * edge.v1.y + rect.y
			x2 = rect.width * edge.v2.x + rect.x
			y2 = rect.height * edge.v2.y + rect.y
			context.move_to(x1, y1)
			context.line_to(x2, y2)
			if edge.collision:
				context.set_source_rgb(1, 0, 0)
			else:
				context.set_source_rgb(0, 0, 0)
			context.stroke()

		# Draw vertices
		for vertex in self.vertices:
			x = rect.width * vertex.x + rect.x
			y = rect.height * vertex.y + rect.y
			context.arc(x, y, VERTEX_RADIUS, 0, 2.0 * math.pi)
			context.set_source_rgb(1, 1, 1)
			context.fill_preserve()
			if vertex == self.drag_vertex:
				context.set_source_rgb(0, 0, 1)
			else:
				context.set_source_rgb(0, 0, 0)
			context.stroke()

	def mouse_down(self, x, y, button):
		"""Figure out if we need to start a drag."""
		rect = self.canvas.game_rect
		for vertex in self.vertices:
			draw_x = rect.width * vertex.x + rect.x
			draw_y = rect.height * vertex.y + rect.y
			dist = distance(x, y, draw_x, draw_y)
			if dist < VERTEX_RADIUS:
				if button == 1:
					self.drag_vertex = vertex
					self.canvas.queue_draw()
					return True
				elif button == 2 and self.is_editor:
					if self.drag_vertex == None:
						return False
					elif self.drag_vertex == vertex:
						return False
					e = Edge(self.drag_vertex, vertex)
					self.edges.append(e)
					self.canvas.queue_draw()
					return False
		self.drag_vertex = None
		return False

	def win(self):
		"""Win the game."""
		print "Yay, you won!"
		self.level = self.level + 1
		try:
			self.load("game%d.txt" % self.level)
		except:
			print "No more levels!"
			gtk.main_quit()

	def mouse_up(self, x, y):
		"""End drag operation."""
		self.canvas.queue_draw()
		if not self.is_editor and self.is_solved():
			self.win()

	def mouse_move(self, x, y):
		"""Drag a vertex somewhere."""
		assert self.drag_vertex != None

		# Translate to game coordinates
		rect = self.canvas.game_rect
		game_x = float(x - rect.x) / rect.width;
		game_y = float(y - rect.y) / rect.height;

		# Update vertex location
		self.drag_vertex.x = game_x
		self.drag_vertex.y = game_y
		self.drag_vertex.clamp()
		self.canvas.queue_draw()

	def key_press(self, widget, event):
		"""Dispatch key presses."""
		if self.keymap.has_key(event.keyval):
			self.keymap[event.keyval](widget, event)

	def tab_key_press(self, widget, event):
		"""Handle tab keys."""
		if self.drag_vertex == None:
			self.drag_vertex = self.vertices[0]
		else:
			idx = self.vertices.index(self.drag_vertex)
			idx = idx + 1
			if idx >= len(self.vertices):
				idx = 0
			self.drag_vertex = self.vertices[idx]
		self.canvas.queue_draw()


	def arrow_key_press(self, widget, event):
		"""Handle arrow key press."""
		if self.drag_vertex == None:
			return
		if event.keyval == gtk.keysyms.Up:
			self.drag_vertex.y = self.drag_vertex.y - 0.01
		elif event.keyval == gtk.keysyms.Down:
			self.drag_vertex.y = self.drag_vertex.y + 0.01
		elif event.keyval == gtk.keysyms.Left:
			self.drag_vertex.x = self.drag_vertex.x - 0.01
		elif event.keyval == gtk.keysyms.Right:
			self.drag_vertex.x = self.drag_vertex.x + 0.01
		self.drag_vertex.clamp()
		self.canvas.queue_draw()

	def n_key_press(self, widget, event):
		"""Create new vertex."""
		v = Vertex(0.5, 0.5)
		self.vertices.append(v)
		self.drag_vertex = v
		self.canvas.queue_draw()

	def s_key_press(self, widget, event):
		"""Save game."""
		self.save("game.txt")
		print "Saved game to 'game.txt'."

	def l_key_press(self, widget, event):
		"""Load game."""
		self.load("game.txt")
		print "Loaded game from 'game.txt'."

	def q_key_press(self, widget, event):
		"""Quit game."""
		gtk.main_quit()

class GameFace(gtk.DrawingArea):
	def __init__(self):
		"""Create custom GTK drawing area."""
		super(GameFace, self).__init__()		
		self.connect("expose_event", self.expose)
		self.add_events(gtk.gdk.EXPOSURE_MASK |
			gtk.gdk.LEAVE_NOTIFY_MASK |
			gtk.gdk.BUTTON_PRESS_MASK |
			gtk.gdk.BUTTON_RELEASE_MASK |
			gtk.gdk.POINTER_MOTION_MASK |
			gtk.gdk.KEY_PRESS_MASK |
			gtk.gdk.POINTER_MOTION_HINT_MASK)

		self.connect("button_press_event", self.button_press)
		self.connect("button_release_event", self.button_release)
		self.connect("motion_notify_event", self.mouse_move)
		self.is_dragging = False
		self.game_rect = gtk.gdk.Rectangle(0, 0, 1, 1)

		self.draw_hook = None
		self.press_hook = None
		self.release_hook = None
		self.move_hook = None

	def button_press(self, widget, event):
		"""Dispatch button press event to controller and start drag if desired."""
		if event.type == gtk.gdk.BUTTON_PRESS:
			if self.press_hook != None:
				res = self.press_hook(event.x, event.y, event.button)
			else:
				res = False
			if res:
				self.is_dragging = True
				self.grab_add()

	def button_release(self, widget, event):
		"""Dispatch button release event to controller."""
		if event.button == 1 and event.type == gtk.gdk.BUTTON_RELEASE and self.is_dragging:
			self.release_hook(event.x, event.y)
			self.grab_remove()
			self.is_dragging = False

	def mouse_move(self, widget, event):
		"""Dispatch mouse movement events to controller."""
		pos = self.get_pointer()
		if self.is_dragging:
			self.move_hook(pos[0], pos[1])

	def expose(self, widget, event):
		"""Figure out canvas size and redraw."""
		context = widget.window.cairo_create()
		
		# set a clip region for the expose event
		context.rectangle(event.area.x, event.area.y,
				  event.area.width, event.area.height)
		context.clip()
		
		self.draw(context)
		
		return False
	
	def draw(self, context):
		"""Draw items."""
		if self.draw_hook != None:
			rect = self.get_allocation()
			rect.x = rect.x + 2
			rect.y = rect.y + 2
			rect.width = rect.width - 4
			rect.height = rect.height - 4
			if rect.width > rect.height:
				rect.x = rect.x + (rect.width - rect.height) / 2
				rect.width = rect.height
			elif rect.height > rect.width:
				rect.y = rect.y + (rect.height - rect.width) / 2
				rect.height = rect.width
			self.game_rect = rect
			self.draw_hook(context, rect)

def print_help():
	"""Print help."""
	print "Usage: %s [-e [gamefile]]" % sys.argv[0]
	print ""
	print "-e:         Invoke editor mode."
	print "gamefile:   Edit a specific game file."

def main():
	"""Main routine."""
	editor = False
	file = "game0.txt"
	if len(sys.argv) > 1:
		if sys.argv[1] == "-e":
			editor = True
		else:
			print_help()
			return
	if len(sys.argv) > 2:
		if editor:
			file = sys.argv[2]
		else:
			print_help()
			return

	app = App(editor)
	try:
		app.load(file)
	except:
		app.pollinate()
	app.run_gtk()

if __name__ == "__main__":
	main()

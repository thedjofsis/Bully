class state():
	def __init__(self):
		# state of the node
		# [Down, Election, Reorganization, Normal]
		self.state = 'Normal'
		# coordinator of the node (if coordinator, has it's own id. Otherwise the id of the coordinator node)
		self.coord = 0
		# the node which recently made this node halt (election started by a higher priority node)
		self.halt = -1
		# list of nodes which this node believes to be in operation
		self.Up = []
from state import state
import zerorpc
import gevent

class bully():
	def __init__(self, addr, config_file):
		self.S = state()
		self.S.state = 'Normal'

		self.check_servers_greenlet = None

		self.addr = addr

		#The sort function here arranges the addresses in an ascending order like a dictionary.
		#The first address in this list is least priority and last entry is highest priority
		self.servers = sorted([line for line in open(config_file).read().strip().split('\n')])
		print 'My addr: %s' % self.addr
		print 'Server list: %s' % (str(self.servers))

		self.n = len(self.servers)

		self.connections = []

		#this is the place where we can say we are assigning priority variable, according to the order in the list
		for i, server in enumerate(self.servers):
			if server == self.addr:
				self.priority = i
				self.connections.append(self)
			else:
				c = zerorpc.Client(timeout=5)
				c.connect('tcp://' + server)
				self.connections.append(c)

	def are_you_there(self):
		return True

	def are_you_normal(self):
		if self.S.state == 'Normal':
			return True
		else:
			return False

	def halt(self, j):
		self.S.state = 'Election'
		self.S.halt = j

	def new_coordinator(self, j):
		print 'call new_coordinator'
		if self.S.halt == j and self.S.state == 'Election':
			self.S.coord = j
			self.S.state = 'Reorganization'

	def ready(self, j, x=None):
		print 'call ready'
		if self.S.coord == j and self.S.state == "Reorganization":
			self.S.state = 'Normal'

	def election(self):
		print 'Check the states of higher priority nodes:'

		for i, server in enumerate(self.servers[self.priority + 1:]):
			try:
				self.connections[self.priority + 1 + i].are_you_there()
				if self.check_servers_greenlet is None:
					self.S.coord = self.priority + 1 + i
					self.S.state = 'Normal'
					self.check_servers_greenlet = self.pool.spawn(self.check())
				return
			except zerorpc.TimeoutExpired:
				print '%s Timeout! 1 (checking for election)' % server

		print 'halt all lower priority nodes including this node:'
		self.halt(self.priority)
		self.S.state = 'Election'
		print 'I am ', self.S.state
		self.S.halt = self.priority
		self.S.Up = []
		for i, server in enumerate(self.servers[self.priority::-1]):
			try:
				self.connections[i].halt(self.priority)
			except zerorpc.TimeoutExpired:
				print '%s Prompt: I have halted myself' % server
				continue
			self.S.Up.append(self.connections[i])

		# reached the election point, now inform other nodes of new coordinator
		print 'inform all nodes of new coordinator:'
		self.S.coord = self.priority
		self.S.state = 'Reorganization'
		print 'I am ', self.S.state
		for j in self.S.Up:
			try:
				j.new_coordinator(self.priority)
			except zerorpc.TimeoutExpired:
				print 'Timeout! 3 (election has to be restarted)'
				self.election()
				return

		# Reorganization
		for j in self.S.Up:
			try:
				j.ready(self.priority)
			except zerorpc.TimeoutExpired:
				print 'Timeout! 4'
				self.election()
				return

		self.S.state = 'Normal'
		# print '[%s] Starting ZeroRPC Server' % self.servers[self.priority]
		self.check_servers_greenlet = self.pool.spawn(self.check())

	def recovery(self):
		self.S.halt = -1
		self.election()

	def check(self):
		while True:
			print 'My address is ', self.addr
			if self.S.coord == self.priority:
				print 'I am Coordinator'
			else:
				print 'I am Normal'

			gevent.sleep(10)
			
			if self.S.state == 'Normal' and self.S.coord == self.priority:
				for i, server in enumerate(self.servers):
					if i != self.priority:
						try:
							ans = self.connections[i].are_you_normal()
							# print '%s : are_you_normal = %s' % (server, ans)
						except zerorpc.TimeoutExpired:
							print '%s Timeout! 5 (normal node unreachable)' % server
							continue

						if not ans:
							self.election()
							return
			elif self.S.state == 'Normal' and self.S.coord != self.priority:
				print 'check coordinator\'s state'
				try:
					result = self.connections[self.S.coord].are_you_there()
					print 'Is the coordinator %s up = %s' % (self.servers[self.S.coord], result)
				except zerorpc.TimeoutExpired:
					print 'coordinator down, start election.'
					self.timeout()

	def timeout(self):
		if self.S.state == 'Normal' or self.S.state == 'Reorganization':
			try:
				self.connections[self.S.coord].are_you_there()
			except zerorpc.TimeoutExpired:
				print '%s Timeout! 6' % self.servers[self.S.coord]
				self.election()
		else:
			self.election()

	def initialize(self):
		self.pool = gevent.pool.Group()
		self.recovery_greenlet = self.pool.spawn(self.recovery)
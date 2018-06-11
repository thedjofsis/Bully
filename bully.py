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

		self.serverListBackup = [];

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

	def areYouThere(self):
		return True

	def areYouNormal(self):
		if self.S.state == 'Normal':
			return True
		else:
			return False

	def halt(self, j):
		self.S.state = 'Election'
		self.S.halt = j

	def newCoordinator(self, j):
		print 'call new coordinator'
		if self.S.halt == j and self.S.state == 'Election':
			self.S.coord = j
			self.S.state = 'Reorganization'

	def ready(self, j, x=None):
		print 'I am ready'
		if self.S.coord == j and self.S.state == "Reorganization":
			self.S.state = 'Normal'

	def election(self):
		print 'Check the states of higher priority nodes:'

		for i, server in enumerate(self.servers[self.priority + 1:]):
			try:
				self.connections[self.priority + 1 + i].areYouThere()
				if self.check_servers_greenlet is None:
					self.S.coord = self.priority + 1 + i
					self.S.state = 'Normal'
					self.check_servers_greenlet = self.pool.spawn(self.check())
				return
			except zerorpc.TimeoutExpired:
				print "%s Timeout 1! Server offline, can't choose this as a coordinator" % server

		print 'halt all lower priority nodes including this node:'
		self.halt(self.priority)
		self.S.state = 'Election'
		print 'I am ', self.S.state
		self.S.halt = self.priority
		self.S.Up = []
		self.serverListBackup = []
		for i, server in enumerate(self.servers[self.priority::-1]):
			try:
				self.connections[i].halt(self.priority)
				print '%s server halted successfully!' % server
			except zerorpc.TimeoutExpired:
				print '%s Timeout 2! server not reachable, cannot halt' % server
				continue
			self.S.Up.append(self.connections[i])
			self.serverListBackup.append(self.servers[i])

		# reached the election point, now inform other nodes of new coordinator
		print 'inform all nodes of new coordinator:'
		self.S.coord = self.priority
		self.S.state = 'Reorganization'
		print 'I am ', self.S.state
		for i, j in enumerate(self.S.Up):
			try:
				j.newCoordinator(self.priority)
				print '%s server received new coordinator!' % self.serverListBackup[i]
			except zerorpc.TimeoutExpired:
				print '%s Timeout 3! server not reachable, election has to be restarted' % self.serverListBackup[i]
				self.election()
				return

		# Reorganization
		for i, j in enumerate(self.S.Up):
			try:
				j.ready(self.priority)
				print '%s server is ready' % self.serverListBackup[i]
			except zerorpc.TimeoutExpired:
				print '%s Timeout 4! server lost connection, election has to be restarted' % self.serverListBackup[i]
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

			gevent.sleep(5)
			
			if self.S.state == 'Normal' and self.S.coord == self.priority:
				for i, server in enumerate(self.servers):
					if i != self.priority:
						try:
							ans = self.connections[i].areYouNormal(param=None)
							print '%s node is Up!' % server
						except zerorpc.TimeoutExpired:
							print '%s Timeout 5! normal node unreachable' % server
							continue

						if not ans:
							print '%s this node is not normal! starting election'
							self.election()
							return
			elif self.S.state == 'Normal' and self.S.coord != self.priority:
				print 'check coordinator\'s state'
				try:
					result = self.connections[self.S.coord].areYouThere()
					print '%s coordinator is up' % self.servers[self.coord]
				except zerorpc.TimeoutExpired:
					print '%s coordinator down, start election' % self.servers[self.coord]
					self.timeout()

	def timeout(self):
		if self.S.state == 'Normal' or self.S.state == 'Reorganization':
			try:
				self.connections[self.S.coord].areYouThere()
				print '%s coordinator alive' % self.servers[self.coord]
			except zerorpc.TimeoutExpired:
				print '%s Timeout 6! coordinator down, start election' % self.servers[self.S.coord]
				self.election()
		else:
			print 'starting election'
			self.election()

	def initialize(self):
		self.pool = gevent.pool.Group()
		self.recovery_greenlet = self.pool.spawn(self.recovery)
import zerorpc
import sys
from state import state
from bully import bully


addr = sys.argv[1]
bully = bully(addr, 'server_config_local')
# bully = bully(addr, 'server_config_local_connected')
# bully = bully(addr, 'server_config_multi')
s = zerorpc.Server(bully)
s.bind('tcp://' + addr)
bully.initialize()
# initialize server
print '[%s] initializing Server' % addr
s.run()
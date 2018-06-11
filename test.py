import zerorpc

c = zerorpc.Client(timeout=5)
c.connect('tcp://127.0.0.1:9001')

print c.areYouThere()
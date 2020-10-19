import pdb

##__________________________________________________________________||
class StreamOut:
    def __init__(self, queue):
        self.queue = queue
    def write(self, s):
        self.queue.put(s)
    def flush(self):
        pass

class StreamIn:
    def __init__(self, queue):
        self.queue = queue
    def readline(self):
        return self.queue.get()

##__________________________________________________________________||
def run_pdb(statement, queue_in, queue_out):
    stdin = StreamIn(queue_in)
    stdout = StreamOut(queue_out)
    p = pdb.Pdb(stdin=stdin, stdout=stdout)
    p.run(statement)
    queue_out.put(None)

##__________________________________________________________________||

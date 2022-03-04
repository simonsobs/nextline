import threading


class PdbCIRegistry:
    """Hold the list of active pdb command interfaces"""

    def __init__(self):
        self._dict = {}
        self.condition = threading.Condition()

    def add(self, trace_id, pdb_ci):
        with self.condition:
            self._dict[trace_id] = pdb_ci

    def remove(self, trace_id):
        with self.condition:
            pdb_ci = self._dict.pop(trace_id)

    def get_ci(self, trace_id):
        with self.condition:
            return self._dict.get(trace_id, None)

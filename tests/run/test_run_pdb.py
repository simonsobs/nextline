from unittest.mock import Mock

from nextline import run_pdb

##__________________________________________________________________||
statement = """
print("here")
print("there")
"""

commands = ['n', 'n', 'n', 'n']

##__________________________________________________________________||
def test_run_pdb(snapshot):
    queue_in = Mock()
    queue_in.get.side_effect = commands
    queue_out = Mock()
    run_pdb(statement, queue_in, queue_out)
    snapshot.assert_match(queue_out.put.call_args_list)

##__________________________________________________________________||

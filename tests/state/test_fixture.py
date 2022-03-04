def test_monkey_patch_trace(monkey_patch_trace):
    MockTrace = monkey_patch_trace
    trace = MockTrace()
    assert trace() is None

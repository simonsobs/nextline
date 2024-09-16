from . import module_b


def func_a() -> None:
    module_b.func_b()
    return

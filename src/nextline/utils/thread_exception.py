from threading import Thread


class ExcThread(Thread):
    """Wrap Thread so to raise exception at join

    The implementation based on
    https://www.geeksforgeeks.org/handling-a-threads-exception-in-the-caller-thread-in-python/

    """

    def run(self) -> None:
        self.exc = None
        try:
            return super().run()
        except BaseException as e:
            self.exc = e

    def join(self, timeout: float | None = None) -> None:
        ret = super().join(timeout)
        if self.exc:
            raise self.exc
        return ret

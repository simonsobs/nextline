from __future__ import annotations

from tblib import pickling_support  # type: ignore
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from .context import Context

pickling_support.install()


class Machine:
    """State machine

                 .-------------.
                 |   Created   |---.
                 '-------------'   |
                       |           |
                       V           |
                 .-------------.   |
            .--->| Initialized |---.
    reset() |    '-------------'   |
            |      |   | run()     |
            |------'   |           |
            |          v           |
            |    .-------------.   |
            |    |   Running   |   |
            |    '-------------'   |
            |          | finish()  |
            |          |           |
            |          V           |
            |    .-------------.   |  close()  .-------------.
            '----|  Finished   |-------------->|   Closed    |
                 '-------------'               '-------------'

    """

    def __init__(self, context: Context):
        self._context = context
        self._state: State = Created(self._context)

    def __repr__(self):
        # e.g., "<Machine 'running'>"
        return f"<{self.__class__.__name__} {self.state_name!r}>"

    @property
    def state_name(self) -> str:
        """e.g., "initialized", "running","""
        try:
            return self._state.name
        except BaseException:
            return "unknown"

    async def initialize(self) -> None:
        """Enter the initialized state"""
        self._state = await self._state.initialize()

    async def run(self) -> None:
        """Enter the running state"""
        self._state = await self._state.run()

    def interrupt(self) -> None:
        self._state.interrupt()

    def terminate(self) -> None:
        self._state.terminate()

    def kill(self) -> None:
        self._state.kill()

    async def finish(self) -> None:
        """Enter the finished state"""
        self._state = await self._state.finish()

    def exception(self) -> Optional[BaseException]:
        ret = self._state.exception()
        return ret

    def result(self) -> Any:
        return self._state.result()

    async def reset(self, *args, **kwargs) -> None:
        """Enter the initialized state"""
        self._state = await self._state.reset(*args, **kwargs)

    async def close(self) -> None:
        """Enter the closed state"""
        self._state = await self._state.close()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.close()


class StateObsoleteError(Exception):
    """Operation on an obsolete state object."""

    pass


class StateMethodError(Exception):
    """Irrelevant operation on the state."""

    pass


class ObsoleteMixin:
    def assert_not_obsolete(self):
        if self.is_obsolete():
            raise StateObsoleteError(f"The state object is obsolete: {self!r}")

    def is_obsolete(self):
        return getattr(self, "_obsolete", False)

    def obsolete(self):
        self._obsolete = True


class State(ObsoleteMixin):
    """The base state class in the Nextline state machine"""

    name = "state"

    def __init__(self):
        self._context: Context

    def __repr__(self):
        # e.g., "<Initialized 'initialized'>"
        items = [self.__class__.__name__, repr(self.name)]
        if self.is_obsolete():
            items.append("obsolete")
        return f'<{" ".join(items)}>'

    async def initialize(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def run(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def finish(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def reset(self, *_, **__) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def close(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def interrupt(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def terminate(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def kill(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def exception(self) -> Optional[BaseException]:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def result(self) -> Any:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")


class Created(State):
    """The state "created" """

    name = "created"

    def __init__(self, context: Context):
        self._context = context

    async def initialize(self) -> Initialized:
        self.assert_not_obsolete()
        next = await Initialized.create(self)
        self.obsolete()
        return next

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        next = await Closed.create(self)
        self.obsolete()
        return next


class Initialized(State):
    """The state "initialized", ready to run"""

    name = "initialized"

    @classmethod
    async def create(cls, prev: State):
        self = cls(prev)
        await self._context.initialize(self)
        return self

    def __init__(self, prev: State):
        self._context = prev._context

    async def run(self) -> Running:
        self.assert_not_obsolete()
        next = await Running.create(self)
        self.obsolete()
        return next

    async def reset(self, *args, **kwargs) -> Initialized:
        self.assert_not_obsolete()
        await self._context.reset(*args, **kwargs)
        next = await Initialized.create(self)
        self.obsolete()
        return next

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        next = await Closed.create(self)
        self.obsolete()
        return next


class Running(State):
    """The state "running", the script is being executed."""

    name = "running"

    @classmethod
    async def create(cls, prev: State):
        self = cls(prev)
        await self._context.run(self)
        return self

    def __init__(self, prev: State):
        self._context = prev._context

    async def finish(self) -> Finished:
        self.assert_not_obsolete()
        next = await Finished.create(self)
        self.obsolete()
        return next

    def interrupt(self) -> None:
        self._context.interrupt()

    def terminate(self) -> None:
        self._context.terminate()

    def kill(self) -> None:
        self._context.kill()


class Finished(State):
    """The state "finished", the script execution has finished"""

    name = "finished"

    @classmethod
    async def create(cls, prev: State):
        self = cls(prev)
        await self._context.finish(self)
        return self

    def __init__(self, prev: State):
        self._context = prev._context

    def exception(self) -> Optional[BaseException]:
        """Return the exception of the script execution

        Return None if no exception has been raised.

        """
        return self._context.exception

    def result(self) -> Any:
        """Return the result of the script execution

        None in the current implementation as the build-in function
        exec() returns None.

        Re-raise the exception if an exception has been raised in the
        script execution.

        """

        if exc := self._context.exception:
            raise exc

        return self._context.result

    async def finish(self) -> Finished:
        self.assert_not_obsolete()
        return self

    async def reset(self, *args, **kwargs) -> Initialized:
        self.assert_not_obsolete()
        await self._context.reset(*args, **kwargs)
        next = await Initialized.create(self)
        self.obsolete()
        return next

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        next = await Closed.create(self)
        self.obsolete()
        return next


class Closed(State):
    """The state "closed" """

    name = "closed"

    @classmethod
    async def create(cls, prev: State):
        self = cls(prev)
        await self._context.close(self)
        return self

    def __init__(self, prev: State):
        self._context = prev._context

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        return self

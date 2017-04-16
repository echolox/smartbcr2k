"""
Provides a wrapper (Shell) to encapsulate an object and schedule all method
calls on this object to be executed in a Thread internal to the shell.

The calls are placed on a queue that is constantly consumed inside the Shell's
main_loop. This way method calls on the object can happen asynchronously.

The encapsulated object does not need any special attributes or inherit from
any kind of interface. If it relies on any kind of update method that needs
to be called periodically, such a method can be provided in the Shell constructor.
"""
from queue import Queue, Empty
from time import sleep
from threading import Thread


yield_thread = lambda: sleep(0)

class WrappedCall(object):
    """
    Wraps a bound method that doesn't expect a return value.
    When the wrapped method is called, the bound method and
    args and kwargs are placed on the queue to be consumed
    inside the shell's main_loop.
    """
    def __init__(self, method, queue):
        self._m = method
        self._q = queue

    def __call__(self, *args, **kwargs):
        self._q.put_nowait((self._m, args, kwargs))


class Shell(object):
    """
    Wraps an object for thread safe communication via a queue on the object.
    """

    _internals = ["_internals", "_o", "_q", "_u", "_running", "_thread"]

    def __init__(self, o, o_update=lambda: None, auto_start=True):
        # The object to be wrapped
        self._o = o
        # Provide an update method that should be called in the main_loop
        self._u = o_update

        # The internal call queue
        self._q = Queue()

        # We need a main_loop to constantly check the queue. This is the
        # flag that keeps the loop alive
        self._running = True

        # All method calls on the wrapped object will happen in this thread
        # along with the provided update_method
        self._thread = Thread(target=self.main_loop, daemon=True)

        if auto_start:
            self.start()

    def start(self):
        """
        Starts the main_loop in the Shell's thread.
        """
        self._running = True
        self._thread.start()

    def main_loop(self):
        """
        Handle method calls from the queue und call the provided
        update method.
        """
        while self._running:
            try:
                # Handle incoming calls from the queue
                while True:
                    call, args, kwargs = self._q.get_nowait()
                    call(*args, **kwargs)
            except Empty:
                # until nothing's left on it
                pass

            # Run the update function from the encapsulated object
            self._u()

            # Yield thread time
            yield_thread()

    def __getattr__(self, name):
        """
        Provides the typical attribute access by forwarding them
        to the encapsulated object. If the requested attribute is
        a method (callable) we wrap it before returning it.
        """
        if name in Shell._internals:
            return self.__getattribute__(name)
        o = self._o
        attr = self._o.__getattribute__(name)
        if callable(attr):
            return WrappedCall(attr, self._q) 
        else:
            return attr

    def __setattr__(self, name, value):
        """
        Forward to the encapsulated object
        """
        if name in Shell._internals:
            object.__setattr__(self, name, value)
        setattr(self._o, name, value)

if __name__ == "__main__":
    class A(object):
        def __init__(self):
            self.q = Queue()
            self.x = 10

        def test(self, y):
            print(self.x, y * self.x)

    s = Shell(A())
    s.x = 500
    print(s.x)
    s.test(25)

    try:
        while True:
            pass
    except KeyboardInterrupt:
        pass

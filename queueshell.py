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
from uuid import uuid4

yield_thread = lambda: sleep(0)

class WrappedCall(object):
    """
    Wraps a bound method that doesn't expect a return value.
    When the wrapped method is called, the bound method and
    args and kwargs are placed on the queue to be consumed
    inside the shell's main_loop.
    """
    def __init__(self, method, queue, result_queue):
        self._m = method
        self._q = queue
        self._rq = result_queue

    def __call__(self, *args, **kwargs):
        if "_returns" in kwargs and kwargs["_returns"]:
            # We want the return value of the method and
            # therefore block after placing the call
            # and wait for a result on the shell's
            # result queue.
            del kwargs["_returns"]
            self._q.put_nowait((self._m, self._rq, args, kwargs))
            return self._rq.get() 
        else:
            # This method call isn't expected to return a
            # value so we can won't block
            pass


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
                    call, result_queue, args, kwargs = self._q.get_nowait()
                    result = call(*args, **kwargs)
                    result_queue.put(result)
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

        attr = self._o.__getattribute__(name)

        if callable(attr):
            return WrappedCall(attr, self._q, Queue()) 
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
            print("IN TEST", self.x, y * self.x)

        def more(self):
            return self.x * -100

        def full(self, a, b="Dan"):
            print("Hey I'm", b,", my a is", a, "and my x is", self.x)
            print("I'm now returning some fixed value")
            return 55

    s = Shell(A())

    print("SETTING X")
    s.x = 500
    print()

    print("GETTING X")
    print(s.x)
    print()

    print("CALLING TEST")
    s.test(25)
    print()

    print("RETURN TEST")
    print(s.more(_returns=True))
    print()

    print("FULL TEST")
    print(s.full(11, b="Arin", _returns=True))
    print()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        pass

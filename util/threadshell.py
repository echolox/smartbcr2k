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

from colorama import Back, Fore, Style, init

init()

from util import eprint

TICK_RATE = 1  # in ms  # set to 0 to just yield to other threads
yield_thread = lambda: sleep(TICK_RATE / 1000.)

class ShellResult(Queue):
    pass


class ShellCall(object):
    """
    Wraps a bound method. When the wrapped method is called,
    the bound method and args and kwargs are placed on the queue
    to be consumed inside the shell's main_loop.

    If you want to use the result of the Call, you will need to call
    get() on it. Effectively this behaves like a Future.
    """
    def __init__(self, method, queue):
        self._m = method
        self._q = queue

    def __call__(self, *args, **kwargs):
        result = ShellResult()
        self._q.put_nowait((self._m, result, args, kwargs))
        return result


class Shell(object):
    """
    Wraps an object for thread asynchronous calls via a Queue In The Shell (tm)
    """

    _internals = ["_internals", "_o", "_q", "_u", "_running", "_thread", "_start", "_main_loop", "_stop"]

    def __init__(self, o, o_update=lambda: None, auto_start=True):
        # The object to be wrapped
        self._o = o
        # Provide an update method that should be called in the main_loop
        self._u = o_update

        # The internal call queue
        self._q = Queue()

        # We need a main_loop to constantly check the queue. This is the
        # flag that keeps the loop alive
        self._running = False

        # All method calls on the wrapped object will happen in this thread
        # along with the provided update_method
        self._thread = Thread(target=self._main_loop, daemon=True)

        if auto_start:
            self._start()

    def _start(self):
        """
        Starts the main_loop in the Shell's thread.
        """
        self._running = True
        self._thread.start()

    def _stop(self):
        self._running = False

    def _main_loop(self):
        """
        Handle method calls from the queue und call the provided
        update method.
        """
        while self._running:
            try:
                # Handle incoming calls from the queue ...
                max_calls = 50
                while max_calls > 0:  # ... till a max is reached ...
                    call, result, args, kwargs = self._q.get_nowait()
                    max_calls -= 1
                    result.put(call(*args, **kwargs))
            except Empty:
                # ... or until nothing's left
                pass

            # Run the update function from the encapsulated object
            # setting a maximum on calls above assures the update
            # function won't starve
            try:
                self._u()
            except Exception as e:
                eprint(self, e)

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
            return ShellCall(attr, self._q) 
        else:
            return attr

    def __setattr__(self, name, value):
        """
        Forward to the encapsulated object
        """
        if name in Shell._internals:
            object.__setattr__(self, name, value)
        setattr(self._o, name, value)

    def __eq__(self, other):
        return self._o == other

    def __repr__(self):
        color = Fore.GREEN if self._running else Fore.RED
        return color + "Shell(%s)" % repr(self._o)

    def __str__(self):
        return self.__repr__()

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
    print(s.more().get())
    print()

    print("FULL TEST")
    print(s.full(11, b="Arin").get())
    print()

    print("> Entering infinite loop. Ctrl+C to exit")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("STOPPING THE SHELL")
        s._stop()

    import time
    import sys
    print("KILLED", end="")
    for _ in range(3):
        sys.stdout.flush()
        time.sleep(0.5)
        print(".", end="")

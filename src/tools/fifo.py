#! /usr/bin/python3
# -*- coding: utf-8 -*-

import threading
from time import monotonic as _time


class Fifo(object):
    
    def __init__(self, max_num, event: threading.Event):
        self.inp, self.outp, self.ept, self.ful = 0, 0, None, None
        self.total = max_num
        self.reset(event)
        self.mininum = self.ept.get_mininum()

    def chk_ful(self):
        assert self.ful.acquire(), "non-blocking"
        return self.inp

    def push(self):
        self.inp += 1
        if self.inp == self.total:
            self.inp = 0
        self.ept.release()
        return self.inp

    def chk_ept(self):
        assert self.ept.acquire(), "non-blocking"
        return self.outp

    def pop(self):
        self.outp += 1
        if self.outp == self.total:
            self.outp = 0
        self.ful.release()
        return self.outp

    def reset(self, event: threading.Event):
        self.inp = 0
        self.outp = 0
        self.ept = CustomSemaphore(event, 0)
        self.ful = CustomSemaphore(event, self.total)


class CustomSemaphore(threading.Semaphore):
    _mininum = 5
    _timeout = 2

    def get_mininum(self):
        return self._mininum

    def __init__(self, event: threading.Event, value=1):
        if value < self._mininum:
            value = self._mininum
        super(CustomSemaphore, self).__init__(value=value)
        self.event = event

    def acquire(self, blocking=True, timeout=None):
        """Acquire a semaphore, decrementing the internal counter by one.

        When invoked without arguments: if the internal counter is larger than
        zero on entry, decrement it by one and return immediately. If it is zero
        on entry, block, waiting until some other thread has called release() to
        make it larger than zero. This is done with proper interlocking so that
        if multiple acquire() calls are blocked, release() will wake exactly one
        of them up. The implementation may pick one at random, so the order in
        which blocked threads are awakened should not be relied on. There is no
        return value in this case.

        When invoked with blocking set to true, do the same thing as when called
        without arguments, and return true.

        When invoked with blocking set to false, do not block. If a call without
        an argument would block, return false immediately; otherwise, do the
        same thing as when called without arguments, and return true.

        When invoked with a timeout other than None, it will block for at
        most timeout seconds.  If acquire does not complete successfully in
        that interval, return false.  Return true otherwise.

        """
        if not blocking and timeout is not None:
            raise ValueError("can't specify timeout for non-blocking acquire")
        rc = False
        endtime = None
        with self._cond:
            while self._value == self._mininum:
                if not self.event.is_set() or not blocking:
                    break
                if timeout is not None:
                    if endtime is None:
                        endtime = _time() + timeout
                    else:
                        timeout = endtime - _time()
                        if timeout <= 0:
                            break
                self._cond.wait(self._timeout)
            else:
                self._value -= 1
                rc = True
        return rc

    def release(self):
        """Release a semaphore, incrementing the internal counter by one.

        When the counter is zero on entry and another thread is waiting for it
        to become larger than zero again, wake up that thread.

        """
        with self._cond:
            self._value += 1
            self._cond.notify()

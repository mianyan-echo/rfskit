import queue
import threading


class Queue(queue.Queue):

    def __init__(self, maxsize=0, count=1):
        """
        :param maxsize: 队列大小
        :param count:
            count >= 2, 调用count次m_get后删除元素
            count < 2, 直接取出
        """
        super().__init__(maxsize)
        self._count = 1 if count < 1 else count
        self._value = list(range(count))
        self.not_end = threading.Condition(self.mutex)
        self.flag = 1
        self.unfinished_tasks = count

    def m_get(self, sign=0, timeout=1):
        with self.not_empty:
            while not self._qsize():
                if not self.not_empty.wait(timeout):
                    return False

            if self._count < 2:
                item = self._get()
                self.not_full.notify()
                return True, item[0]

            if sign in self._value:
                if self.flag == self._count:
                    item = self._get()
                    self.not_full.notify()
                    self.not_end.notify_all()
                    self.flag = 1
                    return True, item[0]
                else:
                    # item = list(self.queue)[0]
                    item = self.queue[0]  # deque支持索引取值
                    self.flag += 1
                    self.not_end.wait()
                    return False, item[0]
        return False

    def lookup(self, timeout=1):
        with self.not_empty:
            while not self._qsize():
                if not self.not_empty.wait(timeout):
                    return False

            data = self.queue[-1]
            if data[1]:
                data[1] = False
                return data[0]
            return False

    def m_put(self, item, timeout=1):
        with self.not_full:
            if self.maxsize > 0:
                while self._qsize() >= self.maxsize:
                    if not self.not_full.wait(timeout):
                        return False
            self._put([item, True])
            self.not_empty.notify_all()
            return True


class Undefined:
    @classmethod
    def m_put(cls, *args, **kwargs):
        return True

    @classmethod
    def m_get(cls, *args, **kwargs):
        return False

    @classmethod
    def lookup(cls, *args, **kwargs):
        return False


if __name__ == '__main__':
    import socket
    import time

    _tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _tcp_server.connect(('127.0.0.1', 5002))
    for i in range(10):
        with open('D:/test_0.data', 'rb') as fp:
            _data = fp.read(526336)
            while _data:
                time.sleep(0.05)
                _tcp_server.sendall(_data)
                _data = fp.read(526336)
    _tcp_server.close()

import socket
from typing import Union
from threading import Event, Lock
import numpy as np
import serial

from .xdma import Xdma

from .tools.dqueue import Undefined, Queue
from .tools.utils import APIBaseType
from .tools.printLog import *


class RFSInterfaceMeta(APIBaseType):
    _METHODS = frozenset({
        "recv_cmd", "send_cmd",
        "read_data", "write_data", "pre_read", "pre_write", "lookup_data",
        "accept", "close", "set_timeout"
    })
    _ATTRS = {
        "queue_size": 10
    }


class CmdInterfaceBusy(RuntimeError):
    def __str__(self):
        return f'{self.__class__.__name__}: {self.args[0]}'


class DataNoneInterface(metaclass=RFSInterfaceMeta, _root=True):
    def accept(self, target_id=None, *args):
        pass

    def recv_cmd(self, size=1024):
        pass

    def send_cmd(self, data):
        return len(data)

    def close(self):
        pass

    def __del__(self):
        self.close()

    def set_timeout(self, value=2):
        pass

    def get_number(self):
        pass

    def update_number(self):
        pass


class CommandSerialInterface(metaclass=RFSInterfaceMeta, _root=True):
    _target_id = 'COM0'
    _target_baud_rate = 115200
    _timeout = 5

    def __init__(self):
        """
        串口指令收发接口

        """
        self._device_serial = None

    def accept(self, target_id=None, *args):
        _target_id = self._target_id if target_id is None else target_id
        if self._device_serial is not None:
            self._device_serial.close()
        if args:
            self._device_serial = serial.Serial(target_id, *args)
        else:
            self._device_serial = serial.Serial(port=_target_id,
                                                baudrate=int(self._target_baud_rate),
                                                timeout=self._timeout)

    def recv_cmd(self, size=1024):
        return self._device_serial.read(size)

    def send_cmd(self, data):
        self._device_serial: serial.Serial
        return self._device_serial.write(data)

    def close(self):
        try:
            self._device_serial.close()
        except Exception as e:
            pass

    def __del__(self):
        self.close()

    def set_timeout(self, value):
        self._device_serial.timeout = value


class CommandTCPInterface(metaclass=RFSInterfaceMeta, _root=True):
    _local_port = 5000
    _remote_port = 5001
    _target_id = "192.168.1.161"
    _serial_num = 1
    _timeout = 5

    def __init__(self):
        """
        网络指令收发接口
        """
        self._tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.set_timeout(self._timeout)
        self._target_id = self._target_id
        self._recv_addr = (self._target_id, self._remote_port)

        self.busy_lock = Lock()

    def accept(self, target_id=None, *args):
        _target_id = self._target_id if target_id is None else target_id
        self._target_id = _target_id
        with self.busy_lock:
            self.close()
            self._tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.set_timeout(self._timeout)
            self._recv_addr = (self._target_id, self._remote_port)
            if args:
                self._tcp_server.connect((_target_id, *args))
            else:
                self._tcp_server.connect((_target_id, self._remote_port))
        self._recv_addr = (_target_id, self._remote_port)

    def recv_cmd(self, size=1024):
        with self.busy_lock:
            return self._tcp_server.recv(size)

    def send_cmd(self, data):
        if self.busy_lock.locked():
            # printColor('等待上一条指令处理完成')
            raise CmdInterfaceBusy('等待上一条指令处理完成')
        with self.busy_lock:
            return self._tcp_server.send(data)

    def close(self):
        try:
            self._tcp_server.shutdown(socket.SHUT_RDWR)
            self._tcp_server.close()
        except Exception as e:
            pass

    def __del__(self):
        self.close()

    def set_timeout(self, value=2):
        self._tcp_server.settimeout(value)

    def get_number(self):
        return self._serial_num

    def update_number(self):
        self._serial_num += 1


class DataTCPInterface(metaclass=RFSInterfaceMeta, _root=True):
    _local_port = 6001
    _remote_port = 5002
    _conn_ip = "192.168.1.161"
    _serial_num = 1
    _timeout = None
    queue_size = 10
    DISCONNECT = 0

    def __init__(self):
        """
        网络数据上下行接口

        """
        self.fd = None
        self.read_put_queue: Union[type, Queue] = Undefined
        self.read_get_queue: Union[type, Queue] = Undefined
        self.stop_event: Union[None, Event] = None

        self._tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._tcp_server.bind(('0.0.0.0', self._local_port))
        self._tcp_server.listen(1)
        self._recv_server = None
        self._recv_addr = (self._conn_ip, self._remote_port)
        self.set_timeout(self._timeout)

    def accept(self, stop_event: Event, queue=Queue):
        self._recv_server, self._recv_addr = self._tcp_server.accept()
        self.read_put_queue = queue(self.queue_size)
        # self.read_get_queue = queue(self.queue_size)
        self.stop_event = stop_event
        printColor('已建立连接', 'green')

    def read_data(self) -> Union[bool, np.ndarray]:
        result = self.read_put_queue.m_get()
        if not result:
            return False
        return result[1]

    def lookup_data(self) -> Union[bool, np.ndarray]:
        return self.read_put_queue.lookup()

    def pre_read(self, size=1024):
        fd = self._recv_server.recv(size, socket.MSG_WAITALL)
        if len(fd) < size:
            return self.DISCONNECT
        fd = np.frombuffer(fd, dtype='u4')

        while not self.stop_event.is_set():
            if self.read_put_queue.m_put(fd):
                break
        return size

    def write_data(self):
        return

    def pre_write(self, data):
        self.fd = data

    def close(self):
        try:
            # self._tcp_server.close()
            self._recv_server.shutdown(socket.SHUT_RDWR)
            self._recv_server.close()
        except Exception as e:
            pass

    def close_recv(self):
        try:
            self._recv_server.shutdown(socket.SHUT_RDWR)
            self._recv_server.close()
        except Exception as e:
            pass

    def __del__(self):
        self.close()

    def set_timeout(self, value=2):
        self._tcp_server.settimeout(value)

    def get_number(self):
        return self._serial_num

    def update_number(self):
        self._serial_num += 1

    @property
    def recv_server(self):
        return self._recv_server


class XdmaInterface(metaclass=RFSInterfaceMeta, _root=True):
    _board_id = 0
    chnl = 0
    xdma_length = 16 * 1024 ** 2
    queue_size = 10

    def __init__(self):
        """
        XDMA数据上下行接口

        """
        super(XdmaInterface, self).__init__()
        self.xdma = Xdma()
        self.fd_list = self.buffer_list = []
        self.read_wait_queue: Union[type, Queue] = Undefined
        self.read_enable_queue: Union[type, Queue] = Undefined
        self.read_stop_event: Union[type, Event] = Undefined
        self.err_cnt = 0
        self.last_buffer_index = None

    def accept(self, stop_event: Event, queue=Queue):
        self.xdma.open_board(self._board_id)
        self.fd_list = [self.xdma.alloc_buffer(self._board_id, self.xdma_length) for _ in range(self.queue_size)]
        self.buffer_list = [self.xdma.get_buffer(fd, self.xdma_length) for fd in self.fd_list]
        self.read_stop_event = stop_event
        self.read_wait_queue = queue(self.queue_size)
        self.read_enable_queue = queue(self.queue_size)
        [self.read_wait_queue.m_put(buf_index) for buf_index in range(self.queue_size)]
        printColor('已开启DMA', 'green')

    def pre_read(self, *args, **kwargs):
        buf_index = self.read_wait_queue.m_get()
        if buf_index is None:
            return False

        result = self.xdma.stream_read(self._board_id, self.chnl, self.fd_list[buf_index],
                                       self.xdma_length, stop_event=self.read_stop_event.is_set, flag=self.err_cnt)
        self.err_cnt += 1
        if not result:
            return False

        while not self.read_stop_event.is_set():
            if self.read_enable_queue.m_put(buf_index):
                return self.xdma_length

        return False

    def read_data(self, size=1024):
        # 为满足调用reda_data是唯一可以从循环队列中取数的操作
        # 将上次read的数据放入等待队列
        last_buffer_index = self.last_buffer_index
        if self.last_buffer_index is not None:
            while not self.read_stop_event.is_set():
                if self.read_wait_queue.m_put(last_buffer_index):
                    break

        buf_index = self.read_enable_queue.m_get()
        if not buf_index:
            return False

        self.last_buffer_index = buf_index[1]

        return self.buffer_list[buf_index[1]]

    def lookup_data(self):
        buf_index = self.read_enable_queue.lookup()
        if not buf_index:
            return False
        return self.buffer_list[buf_index]

    def write_data(self, data):
        pass

    def close(self):
        result = all(self.xdma.free_buffer(fd) for fd in self.fd_list)
        result = result and self.xdma.close_board(self._board_id)
        return result

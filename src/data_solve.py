import time
import threading
import os
from typing import Union

import numpy as np

from .interface import DataTCPInterface, XdmaInterface
from .tools.data_unpacking import UnPackage
from .tools.printLog import *


class DataSolve:
    # 数据处理
    _weave_length_byte = 256
    _weave_length = _weave_length_byte // 4  # 4Byte
    _board = 0
    _channel_num = 8
    # _least_common_multiple = np.lcm.reduce((1, 2, 3, 4, 6))
    _dma_size = 1024 ** 2 * 15  # 4Byte  需要为(1, 2, 3, 4, 6)的公倍数, 解交织时
    _buf_count = 10
    _error_message = ""
    _files = None
    _queue = None
    _dma_channel_num = 0
    _left_size = 0
    _write_start_time = 0
    _prev_count = 0
    _info = None

    def __init__(self, rfs_kit, server: Union[DataTCPInterface, XdmaInterface],
                 upload_event=threading.Event(), download_event=threading.Event()):
        self.rfs_kit = rfs_kit
        self.server = server
        self._files = []
        self.__upload_data_length = 0
        self.__prev_data_length = 0
        self.__start_upload_time = 0
        self.__write_speed = 0
        self.__download_speed = 0
        # self._cache = Queue(1024)
        self.upload_stop_event = upload_event
        self.download_stop_event = download_event

    def upload_status(self):
        now = time.time()
        upload_data_length = self.__upload_data_length
        data_length = upload_data_length - self.__prev_data_length
        upload_speed = 0 if not self.__start_upload_time else data_length / (now - self.__start_upload_time) / 1024 ** 2
        self.__start_upload_time = time.time()
        self.__prev_data_length = upload_data_length
        return [upload_speed, self.__write_speed, upload_data_length]

    def start_solve(self, auto_write_file=True, filepath=None, write_file=True, file_name=''):
        # self._cache = Queue(1024)
        # 启动数据接收线程
        _thread = threading.Thread(target=self.wait_connect, daemon=True)
        _thread.start()

        if not auto_write_file:
            return True

        if filepath is None:
            filepath = f"{file_name}_{time.strftime('%Y%m%d_%H-%M-%S', time.localtime())}"
        if not os.path.exists(filepath):
            os.mkdir(filepath)

        filename = f'data-{file_name}_0.data'
        self._files.append(open(f'{filepath}/{filename}', 'wb'))
        _thread = threading.Thread(target=self.write, args=(self._files[-1], write_file), daemon=True)
        _thread.start()

        # _thread = threading.Thread(target=self.solve, args=([True]*16, ))
        # _thread.start()

        self.rfs_kit.save_icd(filepath)
        return True

    def wait_connect(self):
        self.upload_stop_event.clear()
        disconnect = DataTCPInterface.DISCONNECT
        try:
            self.server.accept(self.upload_stop_event)
            printColor('已建立连接', 'green')

            while not self.upload_stop_event.is_set():
                if self.server.pre_read(1024):
                    header = self.server.lookup_data()
                    break
            info = UnPackage.get_pack_info(0, header)
            self._info = info
            once_package = info[0] * info[7]
            if once_package > 1024 ** 2 * 16:
                printWarning('解析包长过大，按16M接收')
                once_package = 1024 ** 2 * 16
            printInfo(f'包长度{once_package}')
            while not self.upload_stop_event.is_set():
                if self.server.pre_read(once_package - 1024):
                    break

            self.__start_upload_time = time.time()
            self.__upload_data_length = 0
            self.__prev_data_length = 0
            # self.server.recv_server.settimeout(5)
            while not self.upload_stop_event.is_set():
                # 接收数据
                result = self.server.pre_read(once_package)
                # if _data is False:
                #     continue
                if result == disconnect:
                    printInfo('数据连接已断开')
                    break
                self.__upload_data_length += result
        except Exception as e:
            self.upload_stop_event.set()
            self.server.close()
            printException(e)
        self.upload_stop_event.set()

    def write(self, file, write_file):
        """
        数据存储

        :param file:
        :param write_file:
        :return:
        """
        try:
            start_time = time.time()
            data_length = 0
            self.__write_speed = 0
            while not self.upload_stop_event.is_set():
                _data = self.server.read_data()
                if write_file and isinstance(_data, np.ndarray):
                    file.write(_data)
                    data_length += _data.size * 4
                    end_time = time.time()
                    if end_time - start_time > 1:
                        self.__write_speed = data_length / (end_time - start_time) / 1024 ** 2
                        # us_signal.status_trigger.emit((1, 1, data_length/(time.time() - start_time)/1024**2))
                        start_time = time.time()
                        data_length = 0
        except AssertionError as e:
            printDebug(e)
        except Exception as e:
            printException(e)
        finally:
            file.close()
            printColor("文件保存完成", 'green')
            # us_signal.status_trigger.emit((0, 0))

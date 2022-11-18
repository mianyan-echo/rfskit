from functools import lru_cache
from typing import Union

import numpy as np
from scipy.signal import chirp


class ChannelInfo:
    def __init__(self, pack):
        self.__pack = pack
        self.data_bit_width = 16  # 单个数据bit位宽
        self.chnl_id = None  # 当前包通道编号

        # 0：uint32；1：int32；2：uint8；3：int8；4：uint16；5：int16；6：QI拼接，分别为int16；
        # 7：single（32bit浮点）；8：QI拼接，分别为single；9：uin64 10：QI拼接，分别为int32；
        # 11：double（64bit浮点）；12：QI拼接，分别为double；其他：预留
        self.frame_data_type = 5

    def __setattr__(self, key, value):
        if key != '_ChannelInfo__pack':
            self.__pack.frame_head.cache_clear()
            self.__pack.frame_tail.cache_clear()
        super(ChannelInfo, self).__setattr__(key, value)


class PackingError(RuntimeError):
    pass


class Packing:
    frame_tag_head = b'\x01\xdc\xef\x18'
    frame_tag_tail = b'\x18\xef\xdc\x01'

    _data_type_relate = {
        0: [np.uint32, 32, False],
        1: [np.int32, 32, False],
        2: [np.uint8, 8, False],
        3: [np.int8, 8, False],
        4: [np.uint16, 16, False],
        5: [np.int16, 16, False],
        6: [np.uint32, 32, True]  # complex类型, IQ int16组合
    }

    def __init__(self):
        self.frame_prt = 0  # PRT计数，从0自增
        self.frame_length = 0  # 数据包长信息，单位Byte，含包头与包尾；
        self.frame_mode = 0  # 0：交织打包，1：数据段打包；
        self.has_frame_tail = 0  # 0：无包尾，1：有包尾；
        self.frame_head_length = 0  # 0：包头长度256Byte；1：包头长度32Byte；
        self.longlong_frame_head = 0  # 0：不使能超长包头；1：使能超长包头512Byte。
        self.single_frame_head = 0  # 1：单包头交织打包；仅当该位为0时，bit0有效。
        self.interweave_size = 256  # 仅在数据交织打包模式下有效，单位Byte，默认256Byte.
        self.__channel_num = 0  # 数据流内通道数
        self.channels = []
        self.loop_mode = 0  # PRT/连续模式,未用到,为0
        self.segment_length = 0  # 总数据段长度,未用到,为0
        self.mirror_mode = 0  # 数据下行时有效，1：所有通道镜像一个通道的数据
        self.reserve_1 = 0  # 预留

    def __setattr__(self, key, value):
        """
        清空缓存的包头包尾

        :param key:
        :param value:
        :return:
        """
        self.frame_head.cache_clear()
        self.frame_tail.cache_clear()
        super(Packing, self).__setattr__(key, value)

    @property
    def channel_num(self):
        return self.__channel_num

    @channel_num.setter
    def channel_num(self, value: int):
        self.channels = [ChannelInfo(self) for _ in range(value)]
        self.__channel_num = value

    def packing_data(self, data: Union[np.ndarray, list], extra_data: Union[np.ndarray, list, None]=None) -> np.ndarray:
        """

        :param data: 要打包的数据，各通道数据长度应对齐，通道数量应与配置的通道数一致
        :param extra_data: 包头包尾中的额外数据
        :return:
        """
        self.check_data(data)

        if isinstance(data, list):
            data = np.array([np.frombuffer(data[i], dtype='u4') for i in range(len(data))])

        if isinstance(extra_data, list):
            extra_data = np.array([np.frombuffer(extra_data[i], dtype='u4') for i in range(len(extra_data))])

        if self.single_frame_head == 1:
            raise PackingError('单包头交织打包暂不支持')
        elif self.frame_mode == 0:
            data = self.__splice_frame_head(data, extra_data)

            interweave_32 = self.interweave_size // 4
            assert data.size % interweave_32 == 0, '总数据长度不能被交织力度整除'
            data = data.reshape(self.channel_num, data.shape[1] // interweave_32, interweave_32)
            packing_data = data.transpose((1, 0, 2)).ravel()
        elif self.frame_mode == 1:
            data = self.__splice_frame_head(data, extra_data)

            packing_data = data.ravel()
        else:
            raise PackingError('交织打包字段有误')

        self.frame_prt += 1
        return packing_data

    def check_data(self, data: Union[np.ndarray, list]) -> None:
        if self.mirror_mode == 1:
            assert len(data) == 1, '镜像模式只需要一个通道的数据'
        else:
            assert len(data) == self.channel_num, f'通道数量与{type(self)}.{self.__channel_num}不一致'

    def __splice_frame_head(self, data: np.ndarray, extra_data: Union[np.ndarray, None]) -> np.ndarray:
        """
        将标准的通道数据拼接上包头包尾

        :param data:
        :param extra_data: 包头包尾中的额外数据
        :return:
        """
        frame_head = self.frame_head()
        if extra_data is not None and (self.longlong_frame_head == 1 or self.frame_head_length == 0):
            frame_head[:, 8:extra_data.shape[1]+8] = extra_data
        if self.has_frame_tail == 1:
            frame_tail = self.frame_tail()
            frame_head[:, 1] = frame_tail[:, 1] = self.frame_prt
            frame_head[:, 2] = frame_tail[:, 2] = (frame_head.shape[1] + data.shape[1] + frame_tail.shape[1])*4
            data = np.hstack((frame_head, data, frame_tail))
        else:
            frame_head[:, 1] = self.frame_prt
            frame_head[:, 2] = (frame_head.shape[1] + data.shape[1])*4
            data = np.hstack((frame_head, data))

        return data

    @lru_cache(maxsize=16)
    def frame_head(self) -> np.ndarray:
        """
        根据参数生成包头

        :return:
        """
        if self.longlong_frame_head == 1:
            head_length = 128  # 512//4
        elif self.frame_head_length == 0:
            head_length = 64  # 256//4
        elif self.frame_head_length == 1:
            head_length = 8  # 32//4
        else:
            raise PackingError('包头长度错误')

        frame_head = np.zeros((self.channel_num, head_length), dtype='u4')
        frame_head[:, 0] = np.frombuffer(self.frame_tag_head, dtype='u4')
        frame_head[:, 3] = self.interweave_size << 16
        frame_head[:, 3] += self.__get_frame_mode() & 0xFF
        frame_head[:, 4] = self.channel_num & 0xFFFF
        frame_head[:, 5] = self.loop_mode
        frame_head[:, 6] += self.segment_length & 0xFFFFFF00
        frame_head[:, 7] = self.segment_length & 0xFF
        frame_head[:, 7] += self.mirror_mode << 8

        for _index, _chnl in enumerate(self.channels):
            frame_head[_index, 3] += _chnl.data_bit_width << 8
            frame_head[_index, 4] += _chnl.chnl_id << 16
            frame_head[_index, 6] += _chnl.frame_data_type & 0xFF

        return frame_head

    @lru_cache(maxsize=16)
    def frame_tail(self) -> np.ndarray:
        """
        根据参数生成包尾

        :return:
        """
        frame_tail = np.array([[]] * self.channel_num, dtype='u4')

        if self.has_frame_tail == 1:
            frame_tail = self.frame_head().copy()
            frame_tail[:, 0] = np.frombuffer(self.frame_tag_tail, dtype='u4')

        return frame_tail

    def __get_frame_mode(self) -> int:
        bit_0 = self.frame_mode
        bit_1 = self.has_frame_tail << 1
        bit_2 = self.frame_head_length << 2
        bit_3 = self.longlong_frame_head << 3
        bit_4 = self.single_frame_head << 4

        return bit_0 + bit_1 + bit_2 + bit_3 + bit_4

    def signal_generate(self, center_frq, band_width=0, sign=0, pulse_width=16384e-9, init_phase=0, sampling_rate=4e9,
                        point_num=None, point_type=None, parallel_channels=1) -> np.ndarray:
        """
        生成信号数据

        :param center_frq: 中心频率(Hz)
        :param band_width: 带宽(Hz) 默认0
        :param sign: 调频斜率符号  0表示正, 1表示负 默认0
        :param pulse_width: 脉宽(s) 默认16.384μs
        :param init_phase: 初始相位(°) 默认0°
        :param sampling_rate: 采样率(Hz) 默认4GHz
        :param point_num: 生成数据点数 默认由pulse_width与采样率计算得出
        :param point_type: 点的数据类型：  0：uint32；1：int32；
                                        2：uint8；3：int8；
                                        4：uint16；5：int16；
        :param parallel_channels: 并行通道数
        :return:
        """
        assert center_frq > 0, '中心频率应大于0'
        assert band_width >= 0, '信号带宽应大于等于0'

        n = int(sampling_rate * pulse_width)
        if band_width == 0:
            t = np.array([np.arange(n) / n * pulse_width for i in range(parallel_channels)])
        else:
            t = np.linspace(np.zeros(parallel_channels),
                            np.zeros(parallel_channels)+pulse_width,
                            n).T.copy(order='C')

        f0, f1 = (center_frq+band_width/2, center_frq-band_width/2) if sign \
            else (center_frq-band_width/2, center_frq+band_width/2)
        signal = chirp(t, f0=f0, f1=f1, t1=pulse_width, phi=init_phase)

        if point_type is None:
            try:
                point_type = self.channels[0].frame_data_type
            except IndexError as e:
                point_type = 5

        dtype, length, _ = self._data_type_relate[point_type]
        signal = dtype(signal*32767)
        signal = np.frombuffer(signal, dtype='u4').reshape(int(parallel_channels), int(n//(32/length)))

        if point_num is not None and point_num > n:
            box = np.zeros((int(parallel_channels), int(point_num*length/32)), dtype='u4')
            box[:, :signal.shape[1]] = signal
            signal = box
        return signal


if __name__ == '__main__':
    # a = np.cos([(np.arange(64*1024) * 0.01 - 0.25 * i) * np.pi for i in range(8)]) * 32768
    # b = np.int16(a)
    # c = np.frombuffer(b, dtype='u4').reshape(8, 32*1024)

    packing = Packing()
    # packing.channel_num = 8
    # for index, chnl in enumerate(packing.channels):
    #     chnl.chnl_id = index
    #
    # d = packing.packing_data(c)
    b = packing.signal_generate(1e9, 5e8)

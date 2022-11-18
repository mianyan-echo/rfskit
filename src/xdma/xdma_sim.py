# -*- coding:utf-8 -*-
############################
# PSCN SIMULATION
# Writer: tony
# Date: Jan. 3, 2019
############################
import platform
import time

from rfskit.tools.printLog import *
import numpy as np
import random

PCIESTREAMCNT = 1


class Xdma(object):

    isWindows = platform.system() == "Windows"

    def __init__(self):
        self.sd_dict = {}
        self.board_info = ""
        self.board_set = set()
        self.__buffer_dict = {}
        self.fd_index = 0

        self.reg = {}
        printInfo("xdma模拟初始化")

    def open_board(self, board):
        return True

    def get_fpga_version(self, board=0):
        return 0

    def close_board(self, board):
        return True

    def get_info(self, board=0):
        return ""

    # 申请内存
    def alloc_buffer(self, board, length, buf=None):
        import ctypes
        self.fd_index += 1
        if buf is not None:
            self.__buffer_dict[self.fd_index] = np.frombuffer((ctypes.c_uint * length).from_address(buf), dtype='u4')
        else:
            self.__buffer_dict[self.fd_index] = np.arange(length, dtype='u4')
        return self.fd_index

    # 获取内存
    def get_buffer(self, fd, length):
        # data = np.random.rand(length//2)
        # data.dtype = np.uint32
        data = self.__buffer_dict.get(fd, np.arange(length, dtype='u4'))
        return data

    def free_buffer(self, fd):
        return True

    def alite_write(self, addr, data, board=0):
        self.reg[addr] = data
        printDebug("板卡%x, 接收写寄存器，地址：%x, 值：%x" % (board, addr, data))
        return True

    def alite_read(self, addr, board=0):
        try:
            val = self.reg[addr]
        except:
            val = random.randint(0, 10)
        printDebug("板卡%x, 接收读寄存器，地址：%x, 返回值：%x" % (board, addr, val))
        return True, val

    def reset_board(self, board):
        printDebug("接收到板卡%x复位" % board)
        return True

    def stream_write(self, board, chnl, fd, length, offset=0, stop_event=None, flag=1):
        # printInfo("板卡%x, 接收到数据流下行指令，通道号：%d，数据量：%d" % (board, chnl, length))
        return True

    def stream_read(self, board, chnl, fd, length, offset=0, stop_event=None, flag=1):
        time.sleep(0.02)
        return True

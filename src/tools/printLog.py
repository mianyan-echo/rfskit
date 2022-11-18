import platform
import sys
import os
import queue

__all__ = ["printInfo", "printError", "printException", "printColor", "printDebug", "printWarning"]

import time

if 'Windows' in platform.system():
    import ctypes

    __stdInputHandle = -10
    __stdOutputHandle = -11
    __stdErrorHandle = -12
    __foreGroundBLUE = 0x09
    __foreGroundGREEN = 0x0a
    __foreGroundRED = 0x0c
    __foreGroundYELLOW = 0x0e
    stdOutHandle = ctypes.windll.kernel32.GetStdHandle(__stdOutputHandle)


    def setCmdColor(color, handle=stdOutHandle):
        return ctypes.windll.kernel32.SetConsoleTextAttribute(handle, color)


    def resetCmdColor():
        setCmdColor(__foreGroundRED | __foreGroundGREEN | __foreGroundBLUE)


    def printBlue(msg):
        setCmdColor(__foreGroundBLUE)
        sys.stdout.write('%s\n' % msg)
        resetCmdColor()


    def printGreen(msg):
        setCmdColor(__foreGroundGREEN)
        sys.stdout.write('%s\n' % msg)
        resetCmdColor()


    def printRed(msg):
        setCmdColor(__foreGroundRED)
        sys.stdout.write('%s\n' % msg)
        resetCmdColor()


    def printYellow(msg):
        setCmdColor(__foreGroundYELLOW)
        sys.stdout.write('%s\n' % msg)
        resetCmdColor()
else:
    STYLE = {'fore': {'red': 31, 'green': 32, 'yellow': 33, 'blue': 34, }}


    def _UseStyle(msg, mode='', fore='', back='40'):
        fore = '%s' % STYLE['fore'][fore] if fore in STYLE['fore'] else ''
        style = ';'.join([s for s in [mode, fore, back] if s])
        style = '\033[%sm' % style if style else ''
        end = '\033[%sm' % 0 if style else ''
        return '%s%s%s' % (style, msg, end)


    def printRed(msg):
        print(_UseStyle(msg, fore='red'))


    def printGreen(msg):
        print(_UseStyle(msg, fore='green'))


    def printYellow(msg):
        print(_UseStyle(msg, fore='yellow'))


    def printBlue(msg):
        print(_UseStyle(msg, fore='blue'))

enable_debug = True
enable_info = True
enable_error = True
enable_exception = True
enable_QT = True


class WriteStream(object):
    def __init__(self, queue):
        self.queue = queue

    def write(self, text):
        self.queue.put(text)

    def flush(self):
        pass


def set_print_enable(dict_en):
    global enable_debug
    global enable_info
    global enable_error
    global enable_exception
    global enable_QT
    enable_QT = dict_en['QT']
    enable_debug = dict_en['debug']
    enable_info = dict_en['info']
    enable_error = dict_en['error']
    enable_exception = dict_en['exception']


set_print_enable({'QT': False, 'debug': True, 'info': True, 'error': True, 'exception': True})

if enable_QT:
    def printColor(msg, color='red'):
        print('<font color=%s>%s</font><br>' % (color, msg))

    def printDebug(msg, **kwargs):
        global enable_debug
        if enable_debug:
            printColor('Debug: %s' % msg, color=kwargs.pop('color', ''))

    def printException(e, msg='', **kwargs):
        global enable_exception
        if enable_exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            err_info = '%s %s %s' % (exc_type, fname, exc_tb.tb_lineno)
            print('<font color=red>Exception: %s</font><br>' % err_info)
            print('<font color=red>Exception: %s</font><br>' % e)
            print('<font color=red>%s</font><br>' % msg)
        else:
            pass

    def printError(msg, **kwargs):
        global enable_error
        if enable_error:
            print('<font color=red>Error: %s</font><br>' % msg)
        else:
            pass

    def printInfo(msg, **kwargs):
        global enable_info
        if enable_info:
            printColor('Info: %s' % msg, color=kwargs.pop('color', ''))
        else:
            pass

    def printWarning(msg, **kwargs):
        global enable_info
        if enable_info:
            printColor('Warning: %s' % msg)
        else:
            pass

else:

    def printColor(msg, color='red', with_time=False):
        if with_time:
            msg = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
        if color == 'red':
            printRed(msg)
        elif color == 'green':
            printGreen(msg)
        elif color == 'yellow':
            printYellow(msg)
        elif color == 'blue':
            printBlue(msg)
        else:
            print(msg)

    def printDebug(msg, **kwargs):
        global enable_debug
        if enable_debug:
            printColor('Debug: %s' % msg,
                       color=kwargs.pop('color', ''),
                       with_time=kwargs.pop('with_time', False))
        else:
            pass

    def printException(e, msg='', **kwargs):
        global enable_exception
        if enable_exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            err_info = '%s %s %s' % (exc_type, fname, exc_tb.tb_lineno)
            printRed(err_info)
            printRed(e)
            printRed(msg)
        else:
            pass

    def printError(msg, **kwargs):
        global enable_error
        if enable_error:
            printRed('Error: %s' % msg)
        else:
            pass

    def printInfo(msg, **kwargs):
        global enable_info
        if enable_info:
            printColor('Info: %s' % msg, color=kwargs.pop('color', ''),
                       with_time=kwargs.pop('with_time', False))
        else:
            pass

    def printWarning(msg, **kwargs):
        global enable_info
        if enable_info:
            printColor('Warning: %s' % msg,
                       with_time=kwargs.pop('with_time', False))
        else:
            pass

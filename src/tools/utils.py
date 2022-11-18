from functools import wraps
import warnings
import time
from threading import RLock

from .printLog import *


class APIBaseType(type):
    _METHODS = frozenset({
    })
    _ATTRS = {}
    _TEMPLATE = """def {method_name}(self, *args, **kwargs): warnings.warn('接口{method_name}未实现', RuntimeWarning)
        """

    def __new__(mcs, name, bases, attrs: dict, _root=False):
        if _root:
            for method_name in mcs._METHODS:
                if method_name not in attrs:
                    d = {'warnings': warnings}
                    exec(mcs._TEMPLATE.format(method_name=method_name), d)
                    attrs[method_name] = d[method_name]
            for attr_name, default_value in mcs._ATTRS.items():
                attrs.setdefault(attr_name, default_value)
        return super().__new__(mcs, name, bases, attrs)


class SingletonType(type):
    """
    单例模式，为了确保某个类只能存在一个实例，元类方法实现
    """
    single_lock = RLock()

    def __call__(cls, *args, **kwargs):
        with SingletonType.single_lock:
            if not hasattr(cls, "_instance"):
                cls._instance = super(SingletonType, cls).__call__(*args, **kwargs)

        return cls._instance


def solve_exception(flag=False):
    def decorator(func):
        """
            接收处理异常
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AssertionError as e:
                if flag:
                    printError(e)
                    return False
                return f"{e}"
            except Exception as e:
                printException(e)
                return False

        return wrapper
    return decorator


def simulation(sim, callback_function):
    """
        处理模拟返回
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            pthread = kwargs.get("pthread", None)
            if sim:
                result = callback_function()
            else:
                result = func(*args, **kwargs)
            if pthread:
                pthread.update_state(result)
            return result
        return wrapper
    return decorator


class Page:

    """
        分页
    """
    _page = 1        # 页码
    _total_page = 0  # 总页
    _file_list = []  # 文件列表

    def __init__(self, ui, page_size, update_function):
        self.ui = ui
        self._page_size = page_size
        self.callback_function = update_function
        self.ui.spinBox_page.setMinimum(1)  # 最小页码为1
        self.ui.spinBox_page.setMaximum(1)
        self.ui.btn_page_home.clicked.connect(self.home)
        self.ui.btn_page_prev.clicked.connect(self.prev)
        self.ui.btn_page_jump.clicked.connect(self.jump)
        self.ui.btn_page_next.clicked.connect(self.next)
        self.ui.btn_page_end.clicked.connect(self.end)
        # self.ui.spinBox_page.valueChanged.connect(self.page_changed)
        self.btn_enable(False, False, False, False)

    def home(self):
        # 首页
        self.page = 1
        self.update()

    def prev(self):
        # 前一页
        self.page -= 1
        self.update()

    def jump(self):
        # 跳转
        changed_page = self.ui.spinBox_page.value()
        if self.page != changed_page:
            self.page = self.ui.spinBox_page.value()
            self.update()

    def next(self):
        # 后一页
        self.page += 1
        self.update()

    def end(self):
        # 尾页
        self.page = self.total_page
        self.update()

    def update(self):
        # 更新table界面和button显示
        cur_page = self.page
        if cur_page <= 1 and cur_page != self.total_page:
            self.btn_enable(False, False, True, True)
        elif cur_page > 1 and cur_page == self.total_page:
            self.btn_enable(True, True, False, False)
        elif cur_page > 1 and cur_page != self.total_page:
            self.btn_enable(True, True, True, True)
        else:
            self.btn_enable(False, False, False, False)
        self.callback_function(self.file_list)

    def btn_enable(self, *state):
        self.ui.btn_page_home.setEnabled(state[0])
        self.ui.btn_page_prev.setEnabled(state[1])
        self.ui.btn_page_next.setEnabled(state[2])
        self.ui.btn_page_end.setEnabled(state[3])

    @property
    def file_list(self):
        return self._file_list[(self.page - 1) * self._page_size: self.page * self._page_size]

    @file_list.setter
    def file_list(self, files):
        self.total_page = len(files) // self._page_size + 1 \
            if len(files) % self._page_size else len(files) // self._page_size
        self._file_list = files
        self.home()

    @property
    def total_page(self):
        return self._total_page

    @total_page.setter
    def total_page(self, value):
        self._total_page = value
        self.ui.spinBox_page.setMaximum(value)  # 设置最大页码
        self.set_total_message(value)

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, value):
        self._page = value
        self.ui.spinBox_page.setValue(value)

    def set_total_message(self, num):
        self.ui.label_total_page.setText(f"共 {num} 页")

    def get_current_index(self):
        # 从0开始计算
        return (self.page - 1) * self._page_size


def sleep(interval):
    if interval >= 0:
        time.sleep(interval)

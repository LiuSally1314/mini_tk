# ============================================
# 流程方法基类
#
# 每个 core/flows/<name>.py 里的类都继承它。
# 实例化后由 ActionRunner 调用 bind(runner) 注入上下文，
# 方法内部可 transparent 访问：
#   self.runner      （ActionRunner 实例）
#   self.dm          （DeviceManager）
#   self.finder      （OcrFinder）
#   self.defaults    （defaults dict）
#   self.last_coord  （可读写）
#   self._action_data（可读写）
# ============================================

from typing import Any


class FlowMethods:
    _runner: Any = None

    def bind(self, runner) -> "FlowMethods":
        """ActionRunner 创建时调用，注入上下文"""
        self._runner = runner
        return self

    @property
    def runner(self):
        return self._runner

    @property
    def dm(self):
        return self._runner.dm

    @property
    def finder(self):
        return self._runner.finder

    @property
    def defaults(self):
        return self._runner.defaults

    @property
    def last_coord(self):
        return self._runner.last_coord

    @last_coord.setter
    def last_coord(self, v):
        self._runner.last_coord = v

    @property
    def _action_data(self):
        return self._runner._action_data
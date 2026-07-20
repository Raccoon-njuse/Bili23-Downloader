from PySide6.QtCore import QObject

from ..common.enum import ToastNotificationCategory
from ..common.signal_bus import signal_bus

class Updater(QObject):
    def __init__(self, parent = None):
        super().__init__(parent)

    def request_update(self, manual: bool):
        """禁用上游更新服务，避免新产品请求不属于自己的发布渠道。"""
        if manual:
            signal_bus.toast.show.emit(
                ToastNotificationCategory.INFO,
                "",
                "Please check releases in the Media Agent CLI repository.",
            )

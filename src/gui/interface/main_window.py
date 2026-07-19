from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, QTimer

from qfluentwidgets import (
    MSFluentWindow, SystemThemeListener, NavigationItemPosition, FluentIcon, qrouter
)

from util.common.enum import ToastNotificationCategory
from util.common.signal_bus import signal_bus
from util.common.config import config

import logging

logger = logging.getLogger(__name__)

class MainWindowBase:
    def run_post_terms_checks(self: "MainWindow") -> None:
        signal_bus.update.check.emit(False)

        if not config.get(config.tutorial_dialog_shown):
            # 播放器直接进入可操作界面，不显示原下载器的文档引导。
            config.set(config.tutorial_dialog_shown, True)

        if not config.get(config.select_area_dialog_shown):
            self.show_select_area_dialog()

            config.set(config.select_area_dialog_shown, True)

        if not config.get(config.is_login):
            self.show_login_teaching_tip()

        QTimer.singleShot(0, self.check_cache_path)
        QTimer.singleShot(0, self.check_ffmpeg)

        signal_bus.emit_pending_signals()

    def _get_toast_function(self, category: ToastNotificationCategory):
        from gui.component.widget.info_bar import InfoBar

        match category:
            case ToastNotificationCategory.SUCCESS:
                func = InfoBar.success

            case ToastNotificationCategory.ERROR:
                func = InfoBar.error

            case ToastNotificationCategory.WARNING:
                func = InfoBar.warning

            case ToastNotificationCategory.INFO:
                func = InfoBar.info

        return func

    def show_toast_notification(self, category: ToastNotificationCategory, title: str, content: str):
        from gui.component.widget.info_bar import InfoBarPosition

        func = self._get_toast_function(category)

        func(
            title = title,
            content = content,
            orient = Qt.Orientation.Horizontal,
            isClosable = False,
            duration = 3000,
            position = InfoBarPosition.TOP,
            parent = self
        )

    def show_toast_notification_long_message(self, category: ToastNotificationCategory, title: str, content: str):
        from gui.component.widget.info_bar import InfoBarPosition

        func = self._get_toast_function(category)

        func(
            title = title,
            content = content,
            orient = Qt.Orientation.Vertical,
            isClosable = True,
            duration = 5000,
            position = InfoBarPosition.BOTTOM_RIGHT,
            parent = self,
            contentMaxHeight = 200
        )

    def show_login_teaching_tip(self: "MainWindow"):
        from qfluentwidgets import TeachingTip, TeachingTipTailPosition

        TeachingTip.create(
            target = self.avatar_widget,
            title = self.tr("Log in to your account"),
            content = self.tr("Click the avatar to log in to your Bilibili account. \nCaching and playback require an authorized account."),
            icon = FluentIcon.INFO,
            isClosable = True,
            duration = -1,
            tailPosition = TeachingTipTailPosition.LEFT,
            parent = self
        )

    def show_terms_of_use(self):
        from ..dialog.main_window.terms import TermsOfUseDialog

        dialog = TermsOfUseDialog(self)

        if not dialog.exec():
            # 用户不接受使用协议，关闭程序
            self.close()

            logger.warning("用户未接受使用协议，程序已关闭")

            return False

        self.run_post_terms_checks()

        return True
    
    def show_update_dialog(self, info: dict):
        from ..dialog.update import UpdateDialog

        dialog = UpdateDialog(info, self)
        dialog.exec()

    def show_select_area_dialog(self):
        from ..dialog.setting.select_area import SelectAreaDialog

        dialog = SelectAreaDialog(self)
        dialog.exec()

    def center_on_screen(self: "MainWindow", show = True):
        from PySide6.QtWidgets import QApplication

        desktop = QApplication.screens()[0].availableGeometry()
        w, h = desktop.width(), desktop.height()

        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        if show:
            self.initialized = True
            self.show()

    def check_cache_path(self):
        """检查播放器私有缓存根目录，不读取普通下载目录配置。"""
        from util.common.io.directory import Directory
        from util.player_cache.paths import cache_paths

        cache_paths.ensure_layout()
        accessible = Directory.ensure_directory_accessible(str(cache_paths.root))

        if not accessible:
            signal_bus.toast.show_long_message.emit(
                ToastNotificationCategory.ERROR,
                self.tr("Private cache unavailable"),
                self.tr("The private media cache is inaccessible or lacks write permissions.")
            )

            logger.error("播放器私有缓存不可访问或缺少写入权限")

    def check_ffmpeg(self):
        if config.no_ffmpeg_available:
            signal_bus.toast.show_long_message.emit(
                ToastNotificationCategory.ERROR,
                self.tr("FFmpeg Not Found"),
                self.tr("No FFmpeg executable found. Please ensure FFmpeg is installed and configured correctly.")
            )

    def update_route_key(self, key: str):
        self.current_route_key = key

    def reset_route_key(self: "MainWindow"):
        self.navigationInterface.setCurrentItem(self.current_route_key)

    def _activate_window(self: "MainWindow"):
        if not self.initialized:
            self.resize(950, 600)
            self.center_on_screen(show = True)

        if self.isMinimized():
            self.showNormal()
        else:
            self.show()

        self.raise_()
        self.activateWindow()
    
    def _addSubInterface(self: "MainWindow", interface: QWidget):
        interface.setProperty("isStackedTransparent", False)
        self.stackedWidget.addWidget(interface)

        routeKey = interface.objectName()

        self.navigationInterface.items[routeKey].clicked.connect(lambda: self.switchTo(interface))
        
        if self.stackedWidget.count() == 1:
            self.stackedWidget.currentChanged.connect(self._onCurrentInterfaceChanged)
            self.navigationInterface.setCurrentItem(routeKey)
            qrouter.setDefaultRouteKey(self.stackedWidget, routeKey)

        self._updateStackedBackground()

class MainWindow(MainWindowBase, MSFluentWindow):
    def __init__(self):
        super().__init__()

        self.resize(950, 600)
        self.setMinimumSize(950, 600)
        self.setWindowTitle("Bili23 Player")
        self.setWindowIcon(QIcon(":/bili23/icon/app.svg"))
        self.setObjectName("MainWindow")

        self.current_route_key = "ParseInterface"
        self.initialized = False
        self.player_dialog = None

        self.init_UI()

        self.center_on_screen(not config.get(config.silent_start))

        # 设置鼠标指针为等待状态，直到工具初始化完成
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        self.setMicaEffectEnabled(config.get(config.mica_effect))

        QTimer.singleShot(0, self.init_utils)
        
    def init_UI(self):
        from .parse import ParseInterface
        from gui.component.widget.avatar import NavigationLargeAvatarWidget

        self.parse_interface = ParseInterface(self)
        self.parse_btn = self.addSubInterface(self.parse_interface, FluentIcon.SEARCH, self.tr("Parser"), position = NavigationItemPosition.TOP)

        # 缓存页只展示播放器自己的私有容器历史，不复用原下载队列。
        self.cache_btn = self.navigationInterface.addItem(
            "CacheInterface",
            FluentIcon.VIDEO,
            self.tr("Cache"),
            selectable = True,
            position = NavigationItemPosition.TOP
        )

        self.avatar_widget = NavigationLargeAvatarWidget("", QPixmap(":/bili23/image/noface.jpg"), self)

        self.navigationInterface.addWidget(
            "avatar",
            self.avatar_widget,
            onClick = self.on_avatar_click,
            position = NavigationItemPosition.BOTTOM
        )

        self.setting_btn = self.navigationInterface.addItem(
            "SettingInterface",
            FluentIcon.SETTING,
            self.tr("Settings"),
            selectable = True,
            position = NavigationItemPosition.BOTTOM
        )

        self.connect_signals()

        if config.get(config.stay_on_top):
            self.setStayOnTop(True)

    def init_deferred_ui(self):
        from util.player_cache.manager import cache_download_runtime, cache_playback_manager

        from .cache import CacheInterface
        from .setting import SettingInterface

        # 保留全局运行时对象的引用，确保隐藏下载队列在窗口存活期间持续调度。
        self.cache_download_runtime = cache_download_runtime
        self.cache_playback_manager = cache_playback_manager

        self.cache_interface = CacheInterface(self)
        self.setting_interface = SettingInterface(self)

        self._addSubInterface(self.cache_interface)
        self._addSubInterface(self.setting_interface)

        self.cache_playback_manager.playback_ready.connect(self.on_playback_ready)
        self.cache_playback_manager.playback_stop_requested.connect(self.close_player)

    def connect_signals(self):
        signal_bus.toast.show.connect(self.show_toast_notification)
        signal_bus.toast.show_long_message.connect(self.show_toast_notification_long_message)

        signal_bus.login.update_avatar.connect(self.on_update_avatar)
        signal_bus.update.show_dialog.connect(self.show_update_dialog)
        signal_bus.interface.mica_effect_changed.connect(self.setMicaEffectEnabled)

        signal_bus.parse.parse_url.connect(self.on_reparse_task)

        self.parse_btn.clicked.connect(lambda: self.update_route_key("ParseInterface"))
        self.cache_btn.clicked.connect(lambda: self.update_route_key("CacheInterface"))
        self.setting_btn.clicked.connect(lambda: self.update_route_key("SettingInterface"))

    def init_utils(self):
        QApplication.processEvents()

        self.init_deferred_ui()

        from util.misc.update import Updater

        # 监听系统主题变化
        self.theme_listener = SystemThemeListener(self)
        self.theme_listener.start()

        self.updater = Updater(self)

        signal_bus.update.check.connect(self.updater.request_update)

        # 初始化完成，恢复鼠标指针
        QApplication.restoreOverrideCursor()

        if not config.get(config.accepted_terms):
            QTimer.singleShot(0, self.show_terms_of_use)

            return

        self.run_post_terms_checks()

    def closeEvent(self, e):
        from util.thread.async_ import AsyncTask

        if not self.on_close():
            e.ignore()
            return
        
        # 隐藏窗口，给用户反馈正在关闭的状态，避免长时间无响应的感觉
        self.hide()

        self.close_player()
        
        AsyncTask.safe_quit()

        # 初始化定时器尚未执行时窗口也可能被用户立即关闭，此时没有主题监听器。
        theme_listener = getattr(self, "theme_listener", None)
        if theme_listener is not None and theme_listener.isRunning():
            theme_listener.quit()
            theme_listener.wait(1000)

            if theme_listener.isRunning():
                theme_listener.terminate()
                theme_listener.wait(1000)

            theme_listener.deleteLater()

        super().closeEvent(e)

    def resizeEvent(self, e):
        if hasattr(self, "parse_interface"):
            self.parse_interface.adjust_column_width()

        return super().resizeEvent(e)

    def on_close(self):
        # 此分支没有托盘下载队列；关闭窗口即退出并释放临时播放明文。
        return True

    def on_avatar_click(self):
        if not config.get(config.is_login) or config.is_expired:
            # 未登录，点击头像显示登录界面
            from ..dialog.login import LoginDialog
            from util.auth.user import user_manager

            dialog = LoginDialog(self)

            if dialog.exec():
                user_manager.get_user_info()

    def on_playback_ready(self, entry, path: str):
        """只在私有缓存还原完成后创建播放器，并接管临时文件的释放。"""
        from ..dialog.player import PlayerDialog

        self.close_player()
        self.player_dialog = PlayerDialog(entry.title, path, entry.duration, self)
        self.player_dialog.closed.connect(self.on_player_closed)
        self.player_dialog.show()
        self.player_dialog.raise_()
        self.player_dialog.activateWindow()

    def close_player(self):
        """关闭内置播放器，触发临时明文文件的删除。"""
        if self.player_dialog is not None:
            self.player_dialog.close()

    def on_player_closed(self, path: str):
        if hasattr(self, "cache_playback_manager"):
            self.cache_playback_manager.release_playback(path)
        self.player_dialog = None

    def on_update_avatar(self, pixmap: QPixmap | bytes):
        if isinstance(pixmap, bytes):
            avatar_pixmap = QPixmap()
            avatar_pixmap.loadFromData(pixmap)

            pixmap = avatar_pixmap
            config.user_avatar_pixmap = avatar_pixmap

        self.avatar_widget.setAvatar(pixmap)

    def on_reparse_task(self, url: str):
        if self.navigationInterface.currentItem().objectName() != "ParseInterface":
            self.navigationInterface.buttons()[0].click()  # 切换到解析界面

        self.parse_interface.reparse(url)

import logging, os
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QSizePolicy, QPushButton
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from utils.paths import get_resource_path

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """
    主视图 (View)
    """
    signal_connect_clicked = pyqtSignal(bool)
    signal_tab_changed = pyqtSignal(int)
    signal_close_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NeuroSync v1.0")
        self.resize(1400, 900) 
        icon_path = get_resource_path(os.path.join('assets','icons','logo.ico'))
    
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            logging.warning(f"未找到应用图标文件: {icon_path}，将使用默认系统图标。")
        
        self._is_connected_ui_state = False
        
        self._setup_main_layout()
        self._setup_ui_connections()
        
        logger.info("主窗口初始化完成。")

    def _setup_main_layout(self):
        """
        手写界面布局：
        - QVBoxLayout (最外层)
            - QHBoxLayout (顶部控制栏 = TabBar + 右侧状态指示器)
                - QTabWidget (左侧)
                - QHBoxLayout (右侧状态区域)
            - QFrame#statusFooter (最下方一行小字提示)
        """
        self.tab_widget = QTabWidget()
        self.tab_widget.setMovable(False)
        
        self.tab_home = QWidget(); self.tab_home.setObjectName("homeTab")
        self.tab_config = QWidget(); self.tab_config.setObjectName("configTab")
        self.tab_qualify = QWidget(); self.tab_qualify.setObjectName("testTab")
        self.tab_display = QWidget(); self.tab_display.setObjectName("displayTab")
        self.tab_analyze = QWidget(); self.tab_analyze.setObjectName("analyzeTab")
        
        self.tab_widget.addTab(self.tab_home, "主页")
        self.tab_widget.addTab(self.tab_config, "配置")
        self.tab_widget.addTab(self.tab_qualify, "测试")
        self.tab_widget.addTab(self.tab_display, "显示")
        self.tab_widget.addTab(self.tab_analyze, "分析")
        
        for tab in [self.tab_home, self.tab_config, self.tab_qualify, self.tab_display, self.tab_analyze]:
            tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # 为每一页预设一个 QVBoxLayout，方便后面 embed_widget_to_tab
            l = QVBoxLayout(tab)
            l.setContentsMargins(10, 10, 10, 10) # 加上边距让画布更清爽
        

        # 2. 实例化右侧顶部的原子组件
        # ==========================================
        self.top_status_container = QWidget()
        top_status_layout = QHBoxLayout(self.top_status_container)
        top_status_layout.setContentsMargins(0, 0, 10, 0) # 整体右边距
        top_status_layout.setSpacing(10) # 组件间距
        
        # 2.1 LED指示器与设备 ID (整合到一起)
        self.conn_led = StatusLED(color="red")
        self.label_device_id = QLabel("   ")
        self.label_device_id.setStyleSheet("font-weight: bold; color: #555;")
        
        id_frame = QHBoxLayout()
        id_frame.setSpacing(5)
        id_frame.addWidget(self.conn_led)
        id_frame.addWidget(self.label_device_id)
        
        self.battery_icon = SmallBatteryWidget()
        self.btn_connect = StatusButton(text="连接设备")

        top_status_layout.addLayout(id_frame)
        top_status_layout.addWidget(self.battery_icon)
        top_status_layout.addWidget(self.btn_connect)
        
        self.tab_widget.setCornerWidget(self.top_status_container, Qt.Corner.TopRightCorner)
        

        # 4. 最下方的状态提示 (一行小字提示)
        # ==========================================
        self.label_footer_status = QLabel("状态：待机。")
        self.label_footer_status.setStyleSheet("font-size: 12px; color: #7f8c8d; padding-left: 10px; padding-bottom: 2px;")
        
        # 5. 总装：最外层竖直布局
        # ==========================================
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 0)
        main_layout.setSpacing(0)
        
        main_layout.addWidget(self.tab_widget)
        main_layout.addWidget(self.label_footer_status)

    def _setup_ui_connections(self):
        """绑定 UI 内部的触发事件"""
        self.btn_connect.clicked.connect(self._on_connect_btn_clicked)
        self.tab_widget.currentChanged.connect(self.signal_tab_changed.emit)

    def _on_connect_btn_clicked(self):
        """UI 层面处理按钮状态变化，发射业务信号"""
        if not self._is_connected_ui_state:
            self.signal_connect_clicked.emit(True)
        else:
            self.signal_connect_clicked.emit(False)
    
    def set_connected_state(self, device_type: str):
        """Controller 唤醒：设置为已连接状态"""
        self._is_connected_ui_state = True
        
        self.btn_connect.set_connected_state()
        self.conn_led.set_status("green")
        self.show_status(f"设备 {device_type} 已连接。", "#4CAF50")
        self.label_device_id.setText(device_type)

    def set_disconnected_state(self):
        """Controller 唤醒：设置为断开状态"""
        self._is_connected_ui_state = False
        
        self.btn_connect.set_disconnect_state()
        self.conn_led.set_status("red")
        
        self.label_device_id.setText("设备：--")
        self.battery_icon.set_battery_level(0)

    def update_battery_display(self, battery_level: int):
        """Controller 唤醒：更新小型电池图标"""
        self.battery_icon.set_battery_level(battery_level)

    def show_status(self, message: str, color="#7f8c8d"):
        """Controller 唤醒：更新最下方的一行小字提示"""
        self.label_footer_status.setText(f"状态：{message}")
        self.label_footer_status.setStyleSheet(f"font-size: 12px; color: {color};")

    def lock_tabs_for_acquisition(self):
        """在开始采样时，锁定前面配置的 Tab 防止误触"""
        self.tab_widget.setTabEnabled(0, False) # 锁定用户信息
        self.tab_widget.setTabEnabled(1, False) # 锁定通道配置

    def unlock_tabs(self):
        """恢复 Tab 的可用状态"""
        self.tab_widget.setTabEnabled(0, True)
        self.tab_widget.setTabEnabled(1, True)

    def embed_widget_to_tab(self, tab_name: str, widget):
        """
        通用组件嵌入方法。
        根据 tab_name 映射找到对应的篮子和 QVBoxLayout，并放入组件。
        """
        name_map = {
            "home": self.tab_home,
            "config": self.tab_config,
            "qualify": self.tab_qualify,
            "display": self.tab_display,
            "analyze": self.tab_analyze
        }
        
        if tab_name in name_map:
            name_map[tab_name].layout().addWidget(widget) # type: ignore
            
            logger.info("已成功嵌入 [%s] 标签页。", tab_name)

    def show_error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event): # type: ignore
        self.signal_close_requested.emit()
        event.accept()
        
class StatusButton(QPushButton):
    """
    一个可以根据状态切换文本和 QSS 样式的按钮。
    （原 ConnectButton 的升级版）
    """
    def __init__(self, text="连接设备", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # 应用初始样式 (在全局 QSS 中定义)
        self.setProperty("state", "idle") 
        self.setMinimumWidth(100)
        self.setMinimumHeight(35)

    def set_disconnect_state(self):
        self.setText("连接设备")
        self.setProperty("state", "idle")
        self.setEnabled(True)
        self._refresh_style()

    def set_connected_state(self):
        self.setText("断开设备")
        self.setProperty("state", "connected")
        self.setEnabled(True)
        self._refresh_style()

    def set_action_state(self, action_text="连接中..."):
        self.setText(action_text)
        self.setProperty("state", "acting")
        self.setEnabled(False)
        self._refresh_style()

    def _refresh_style(self):
        """Qt 的一个 Bug，需要手动刷新样式表"""
        self.style().unpolish(self) # type: ignore
        self.style().polish(self) # type: ignore


# ==========================================
# 2. 状态指示 LED (StatusLED)
# ==========================================
class StatusLED(QLabel):
    """
    一个模拟 LED 灯的圆形指示器。
    通过 QSS 改变背景颜色：'green' (connected), 'red' (disconnected), 'yellow' (timeout/error)
    """
    def __init__(self, color="red", size=16, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setProperty("led_state", color)

    def set_status(self, color):
        """color: 'green', 'red', 'yellow'"""
        self.setProperty("led_state", color)
        self.style().unpolish(self) # type: ignore
        self.style().polish(self) # type: ignore


# ==========================================
# 3. 小型电池图标 (SmallBatteryWidget)
# ==========================================
class SmallBatteryWidget(QWidget):
    """
    一个由一个小电池图标和一个百分比 QLabel 组成的紧凑型 QWidget。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        self.icon_label = QLabel("🔋") 
        
        # 2. 百分比
        self.percent_label = QLabel("--%")
        self.percent_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #555;")
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.percent_label)

    def set_battery_level(self, percent: int):
        self.percent_label.setText(f"{percent}%")
        
        if percent < 20:
            self.percent_label.setStyleSheet("font-size: 13px; color: #f44336;") # 红色
        elif percent < 40:
            self.percent_label.setStyleSheet("font-size: 13px; color: #ff9800;") # 橙色
        else:
            self.percent_label.setStyleSheet("font-size: 13px; color: #4caf50;") # 绿色

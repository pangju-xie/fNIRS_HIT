import random, os, sys, logging
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QApplication
from PyQt5.QtCore import QTimer, pyqtSignal



from ui.views.quality_view import QualityViewWidget
from models.stats import SensorTypes
from ui.views.locate_widget import BrainLocatorView

logger = logging.getLogger(__name__)

class ChannelItemWidget(QWidget):
    """滚动列表中单个通道的展示条目"""
    def __init__(self, mode, name):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        self.lbl_mode = QLabel(mode)
        self.lbl_mode.setFixedWidth(60)
        self.lbl_mode.setStyleSheet("font-weight: bold; color: #555;")
        
        self.lbl_name = QLabel(name)
        self.lbl_name.setFixedWidth(80)
        
        self.lbl_value = QLabel("0.0")
        self.lbl_value.setFixedWidth(80)
        
        self.lbl_status = QLabel("Unknown")
        self.lbl_status.setFixedWidth(80)
        self.lbl_status.setStyleSheet("border-radius: 4px; padding: 2px; text-align: center; color: white; background-color: #9e9e9e;")
        
        layout.addWidget(self.lbl_mode)
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_value)
        layout.addWidget(self.lbl_status)
        layout.addStretch()
        
    def update_data(self, value, status_text, hex_color):
        self.lbl_value.setText(f"{value:.2f}")
        self.lbl_status.setText(status_text)
        self.lbl_status.setStyleSheet(f"border-radius: 4px; padding: 2px; text-align: center; color: white; background-color: {hex_color}; font-weight: bold;")


class QualityManager(QWidget):
    """质量评估逻辑控制器"""
    signal_qualify_finished = pyqtSignal() 
    signal_request_start = pyqtSignal()
    signal_request_stop = pyqtSignal()
    
    def __init__(self, sensor_types: SensorTypes, bmap_manager):
        super().__init__()
        self.ui = QualityViewWidget()
        self.ui.setupUi(self)
        
        self.sensor_types = sensor_types
        self.bmap_manager = bmap_manager
        
        # 创建一个全新的拓扑视图，并传入配置好的模型
        self.locate_widget = BrainLocatorView(model=self.bmap_manager)
        self.ui.brain_layout.addWidget(self.locate_widget)
        
        self.is_running = False
        self.channel_widgets = {} # 存放所有列表 UI 条目
        
        self._init_channels()
        self._wire_signals()
        
        logger.info("质量评估组件已初始化。")

    def _init_channels(self):
        """根据配置模型生成列表项"""
        # 清空列表
        while self.ui.scrollAreaLayout.count():
            item = self.ui.scrollAreaLayout.takeAt(0)
            if item.widget(): item.widget().deleteLater() # type: ignore
        self.channel_widgets.clear()
        
        # 1. 加载 fNIRS 通道
        if self.sensor_types.value & SensorTypes.FNIRS.value:
            fnirs_dict = self.bmap_manager.get_fnirs_montage_dict()
            for pair in fnirs_dict.get('fnirs_pairs', []):
                item = ChannelItemWidget("fNIRS", pair)
                self.channel_widgets[pair] = item
                self.ui.scrollAreaLayout.addWidget(item)
                
        # 2. 加载 EEG 通道
        if self.sensor_types.value & SensorTypes.EEG.value:
            eeg_dict = self.bmap_manager.get_eeg_montage_dict()
            for ch in eeg_dict.get('eeg_channels', []):
                item = ChannelItemWidget("EEG", ch)
                self.channel_widgets[ch] = item
                self.ui.scrollAreaLayout.addWidget(item)

    def _wire_signals(self):
        self.ui.btn_start.clicked.connect(self.start_test)
        self.ui.btn_stop.clicked.connect(self.stop_test)
        self.ui.btn_complete.clicked.connect(self.complete_test)

    def _get_color_mapping(self, value, is_eeg=False):
        """将信号值映射为红黄绿"""
        if is_eeg:
            # EEG 阻抗越低越好 (假设 0-50kOhm)
            ratio = 1.0 - min(max(value / 50.0, 0.0), 1.0)
        else:
            # fNIRS 信号越强越好
            ratio = value
            # ratio = min(max(value / 3000.0, 0.0), 1.0)
            
        if ratio < 0.3: return "Poor", "#F44336"
        elif ratio < 0.6: return "Fair", "#FFC107"
        elif ratio < 0.85: return "Good", "#8BC34A"
        else: return "Excellent", "#4CAF50"

    def start_test(self):
        self.is_running = True
        self.ui.btn_start.setEnabled(False)
        self.ui.btn_stop.setEnabled(True)
        
        # 清空拓扑图上的历史颜色
        if hasattr(self.locate_widget, 'clear_colors'):
            self.locate_widget.clear_colors()
            
        self.signal_request_start.emit()

    def stop_test(self):
        self.is_running = False
        self.ui.btn_start.setEnabled(True)
        self.ui.btn_stop.setEnabled(False)
        self.signal_request_stop.emit()

    def complete_test(self):
        self.stop_test()
        self.signal_qualify_finished.emit()

    def update_quality_data(self, sensor_type: SensorTypes, quality_dict: dict):
        if not self.is_running:
            return
        logger.debug(f"收到新的质量数据更新，模态: {sensor_type.name}，数据: {quality_dict}")
        if sensor_type == SensorTypes.FNIRS:
            fnirs_dict = self.bmap_manager.get_fnirs_montage_dict()
            for pair, val in quality_dict.items():
                if pair in self.channel_widgets:
                    status, color = self._get_color_mapping(val, is_eeg=False)
                    self.channel_widgets[pair].update_data(val, status, color)
                    
                    # 更新拓扑图连线颜色
                    s_alias, d_alias = pair.split('-')
                    s_std = fnirs_dict['sources'][s_alias]['standard_name']
                    d_std = fnirs_dict['detectors'][d_alias]['standard_name']
                    self.locate_widget.set_line_color(s_std, d_std, color)

        elif sensor_type == SensorTypes.EEG:
            eeg_dict = self.bmap_manager.get_eeg_montage_dict()
            for ch, val in quality_dict.items():
                if ch in self.channel_widgets:
                    status, color = self._get_color_mapping(val, is_eeg=True)
                    self.channel_widgets[ch].update_data(val, status, color)
                    
                    # 更新拓扑图节点颜色
                    std_name = eeg_dict['eeg_details'][ch]['standard_name']
                    self.locate_widget.set_node_color(std_name, color)
                    
        self.locate_widget.update()
        
        
if __name__ == "__main__":            
    from core.widget_manager.bmap_manager import BrainMapManager

    app = QApplication(sys.argv)
    
    # 1. 模拟一个已经配好节点的 BMapManager 模型
    mock_bmap = BrainMapManager()
    
    # 手动在模型上激活几个节点（模拟第二页用户的操作）
    mock_bmap.set_node_state('FC1', 'Source')
    mock_bmap.set_node_state('FC2', 'Source')
    mock_bmap.set_node_state('C1', 'Detector')
    mock_bmap.set_node_state('C2', 'Detector')
    mock_bmap.set_node_state('Cz', 'EEG')
    mock_bmap.set_node_state('Oz', 'EEG')
    
    # 2. 模拟当前连接的模态为 双模态 (fNIRS + EEG)
    # 若无法引入 SensorTypes，可自行定义枚举
    mock_sensor_type = SensorTypes.EEG_FNIRS 
    
    # 3. 实例化界面
    manager = QualityManager(
        sensor_types=mock_sensor_type,
        bmap_manager=mock_bmap
    )
    
    manager.setWindowTitle("独立测试：信号质量与阻抗评估")
    manager.resize(1100, 750)
    manager.show()
    
    sys.exit(app.exec_())
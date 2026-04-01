# ui/views/channel_view.py
import os
import sys
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QGroupBox, QLabel, QSpinBox, QComboBox, 
                             QPushButton, QSplitter, QFrame)
from PyQt5.QtCore import Qt

# 动态获取项目根目录，确保绝对路径导包不出错
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from core.widget_manager.bmap_manager import BrainMapManager
from ui.views.locate_widget import BrainLocatorView
from models.stats import SensorTypes  # 引入强类型枚举

logger = logging.getLogger(__name__)

class ChannelViewWidget(QWidget):
    """
    通道配置界面纯视图层 (View)
    根据传入的 SensorTypes (IntFlag) 动态渲染 UI
    """
    def __init__(self, sensor_types: SensorTypes = SensorTypes.EEG_FNIRS, parent=None):
        super().__init__(parent)
        # 使用强类型枚举管理传感器模态
        self.sensor_types = sensor_types
        
        self.brain_manager = BrainMapManager()
        self.brain_locator = BrainLocatorView(self.brain_manager)
        
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("ChannelConfigForm")
        self.resize(1200, 800)
        
        # 严格使用 Qt.WidgetAttribute 枚举
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # ==========================================
        # 区域 1：动态单行参数栏 (使用 IntFlag 位运算判断)
        # ==========================================
        param_group = QGroupBox("1. 通道采样率配置")
        param_layout = QHBoxLayout(param_group)
        param_layout.setContentsMargins(15, 12, 15, 8) 
        param_layout.setSpacing(12)

        if self.sensor_types & SensorTypes.EEG:
            param_layout.addWidget(QLabel("EEG 通道数:"))
            self.spin_eeg = QSpinBox(); self.spin_eeg.setRange(1, 32); self.spin_eeg.setValue(32)
            param_layout.addWidget(self.spin_eeg)
            
            param_layout.addWidget(QLabel("采样率(Hz):"))
            self.combo_eeg_hz = QComboBox(); self.combo_eeg_hz.addItems(["500", "1000", "2000", "4000"])
            param_layout.addWidget(self.combo_eeg_hz)
            self._add_vline(param_layout)

        if self.sensor_types & SensorTypes.FNIRS:
            param_layout.addWidget(QLabel("fNIRS 光源数:"))
            self.spin_src = QSpinBox(); self.spin_src.setRange(1, 16); self.spin_src.setValue(8)
            param_layout.addWidget(self.spin_src)
            
            param_layout.addWidget(QLabel("探测器数:"))
            self.spin_det = QSpinBox(); self.spin_det.setRange(1, 16); self.spin_det.setValue(8)
            param_layout.addWidget(self.spin_det)
            
            param_layout.addWidget(QLabel("采样率(Hz):"))
            self.combo_fnirs_hz = QComboBox(); self.combo_fnirs_hz.addItems(["10", "20"])
            param_layout.addWidget(self.combo_fnirs_hz)
            self._add_vline(param_layout)

        if self.sensor_types & SensorTypes.SEMG:
            param_layout.addWidget(QLabel("sEMG 通道数:"))
            self.spin_semg = QSpinBox(); self.spin_semg.setRange(1, 16); self.spin_semg.setValue(8)
            param_layout.addWidget(self.spin_semg)
            
            param_layout.addWidget(QLabel("采样率(Hz):"))
            self.combo_semg_hz = QComboBox(); self.combo_semg_hz.addItems(["500", "1000", "2000", "4000"])
            param_layout.addWidget(self.combo_semg_hz)

        param_layout.addStretch()
        main_layout.addWidget(param_group)

        # ==========================================
        # 区域 2：空间拓扑配置画布
        # ==========================================
        canvas_group = QGroupBox("2. 通道配置")
        canvas_layout = QVBoxLayout(canvas_group)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.brain_locator.setMinimumWidth(500)
        splitter.addWidget(self.brain_locator)
        
        # 只有存在肌电时，才显示右侧预留画布
        if self.sensor_types & SensorTypes.SEMG:
            self.semg_placeholder = QLabel("躯干肌电节点画布\n(待开发)")
            self.semg_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.semg_placeholder.setStyleSheet("""
                QLabel { background-color: #f8f9fa; border: 2px dashed #bdc3c7;
                         border-radius: 8px; color: #95a5a6; font-size: 18px; font-weight: bold; }
            """)
            splitter.addWidget(self.semg_placeholder)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 1)
        
        canvas_layout.addWidget(splitter)
        main_layout.addWidget(canvas_group, stretch=1) 

        # ==========================================
        # 区域 3：操作按钮
        # ==========================================
        self.bottom_frame = QFrame()
        self.bottom_frame.setObjectName("bottomControlBar")
        btn_layout = QHBoxLayout(self.bottom_frame)
        btn_layout.setContentsMargins(15, 5, 15, 5) # 设置底座内部留白
        
        self.btn_clear = QPushButton("新建Montage")
        self.btn_load = QPushButton("加载Montage")
        self.btn_save = QPushButton("保存Montage")
        
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_save)
        
        btn_layout.addStretch() 
        
        self.btn_apply = QPushButton("设置")
        self.btn_apply.setObjectName("btn_apply")
        self.btn_finish = QPushButton("完成 >>")
        self.btn_finish.setObjectName("btn_finish")
        
        self.btn_finish.setEnabled(False) # 初始状态下完成按钮不可用，必须先成功设置采样率等参数
        
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_finish)
        
        main_layout.addWidget(self.bottom_frame)

    def _add_vline(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #bdc3c7;")
        layout.addWidget(line)

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    # 测试环境：传入全模态枚举进行测试
    window = ChannelViewWidget(sensor_types=SensorTypes.EEG_FNIRS)
    window.show()
    sys.exit(app.exec_())
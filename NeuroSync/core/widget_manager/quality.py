import logging
import sys

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from ui.views.locate_widget import BrainLocatorView
from ui.views.quality_view import QualityViewWidget
from utils.stats import SensorTypes

logger = logging.getLogger(__name__)


class ChannelItemWidget(QWidget):
    """滚动列表中的单个通道展示项。"""

    def __init__(self, name, value_title):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(10)

        self.lbl_name = QLabel(name)
        self.lbl_name.setFixedWidth(110)
        self.lbl_name.setAlignment(Qt.AlignCenter)

        self.lbl_value = QLabel("0.00")
        self.lbl_value.setFixedWidth(96)
        self.lbl_value.setAlignment(Qt.AlignCenter)
        self.lbl_value.setToolTip(value_title)

        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_value)

    def update_data(self, value, hex_color):
        self.lbl_value.setText(f"{value:.2f}")
        self.lbl_value.setStyleSheet(f"color: {hex_color}; font-weight: bold;")


class QualityManager(QWidget):
    """质量评估逻辑控制器。"""

    signal_qualify_finished = pyqtSignal()
    signal_request_start = pyqtSignal()
    signal_request_stop = pyqtSignal()

    def __init__(self, sensor_types: SensorTypes, bmap_manager):
        super().__init__()
        self.ui = QualityViewWidget()
        self.ui.setupUi(self)

        self.sensor_types = sensor_types
        self.bmap_manager = bmap_manager
        self.locate_widget = BrainLocatorView(model=self.bmap_manager, quality_view_mode=True)
        self.ui.brain_layout.addWidget(self.locate_widget)

        self.is_running = False
        self.fnirs_widgets = {}
        self.eeg_widgets = {}
        self.eeg_name_map = {}

        self._init_channels()
        self._wire_signals()
        logger.info("质量评估组件已初始化。")

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()  # type: ignore

    def _init_channels(self):
        self._clear_layout(self.ui.fnirs_scroll.content_layout)
        self._clear_layout(self.ui.eeg_scroll.content_layout)
        self.fnirs_widgets.clear()
        self.eeg_widgets.clear()
        self.eeg_name_map.clear()

        fnirs_dict = self.bmap_manager.get_fnirs_montage_dict()
        fnirs_pairs = fnirs_dict.get("fnirs_pairs", [])
        if fnirs_pairs:
            for pair in fnirs_pairs:
                item = ChannelItemWidget(pair, "fNIRS 通道强度")
                self.fnirs_widgets[pair] = item
                self.ui.fnirs_scroll.content_layout.addWidget(item)

        eeg_dict = self.bmap_manager.get_eeg_montage_dict()
        eeg_channels = eeg_dict.get("eeg_channels", [])
        if eeg_channels:
            for ch in eeg_channels:
                standard_name = eeg_dict.get("eeg_details", {}).get(ch, {}).get("standard_name", ch) or ch
                self.eeg_name_map[ch] = standard_name
                item = ChannelItemWidget(standard_name, "EEG 阻抗(kΩ)")
                self.eeg_widgets[ch] = item
                self.ui.eeg_scroll.content_layout.addWidget(item)

        self.ui.fnirs_group.setVisible(bool(fnirs_pairs))
        self.ui.eeg_group.setVisible(bool(eeg_channels))

    def _wire_signals(self):
        self.ui.btn_start.clicked.connect(self.start_test)
        self.ui.btn_stop.clicked.connect(self.stop_test)
        self.ui.btn_complete.clicked.connect(self.complete_test)

    def _get_color_mapping(self, value, is_eeg=False):
        if is_eeg:
            if value < 5.0:
                return "#4CAF50"
            if value < 10.0:
                return "#8BC34A"
            if value < 20.0:
                return "#FFC107"
            return "#F44336"

        ratio = value
        if ratio < 0.3:
            return "#F44336"
        if ratio < 0.6:
            return "#FFC107"
        if ratio < 0.85:
            return "#8BC34A"
        return "#4CAF50"

    def _get_eeg_quality_display(self, payload):
        if isinstance(payload, dict):
            impedance = float(payload.get("impedance_kohm", 0.0))
            lead_off = bool(payload.get("lead_off", False))
            if lead_off:
                return impedance, "#F44336"
            return impedance, self._get_color_mapping(impedance, is_eeg=True)

        impedance = float(payload)
        return impedance, self._get_color_mapping(impedance, is_eeg=True)

    def start_test(self):
        self.is_running = True
        self.ui.btn_start.setEnabled(False)
        self.ui.btn_stop.setEnabled(True)
        if hasattr(self.locate_widget, "clear_colors"):
            self.locate_widget.clear_colors()
        self.signal_request_start.emit()

    def stop_test(self):
        self.is_running = False
        self.ui.btn_start.setEnabled(True)
        self.ui.btn_stop.setEnabled(False)
        if hasattr(self.locate_widget, "clear_colors"):
            self.locate_widget.clear_colors()
        self.signal_request_stop.emit()

    def complete_test(self):
        self.stop_test()
        self.signal_qualify_finished.emit()

    def update_quality_data(self, sensor_type: SensorTypes, quality_dict: dict):
        if not self.is_running:
            return

        logger.debug("收到新的质量数据更新，模态: %s，数据: %s", sensor_type.name, quality_dict)

        if sensor_type == SensorTypes.FNIRS:
            fnirs_dict = self.bmap_manager.get_fnirs_montage_dict()
            for pair, value in quality_dict.items():
                if pair not in self.fnirs_widgets:
                    continue
                color = self._get_color_mapping(value, is_eeg=False)
                self.fnirs_widgets[pair].update_data(value, color)

                s_alias, d_alias = pair.split("-")
                source_entry = fnirs_dict["sources"].get(s_alias, {})
                detector_entry = fnirs_dict["detectors"].get(d_alias, {})
                source_name = source_entry.get("layout_name")
                detector_name = detector_entry.get("layout_name")
                if source_name and detector_name:
                    self.locate_widget.set_line_color(source_name, detector_name, color)

        elif sensor_type == SensorTypes.EEG:
            eeg_dict = self.bmap_manager.get_eeg_montage_dict()
            for ch, payload in quality_dict.items():
                if ch not in self.eeg_widgets:
                    continue
                impedance, color = self._get_eeg_quality_display(payload)
                self.eeg_widgets[ch].update_data(impedance, color)
                layout_name = eeg_dict["eeg_details"][ch].get("layout_name")
                if layout_name:
                    self.locate_widget.set_node_color(layout_name, color)

        self.locate_widget.update()


if __name__ == "__main__":
    from core.widget_manager.bmap_manager import BrainMapManager

    app = QApplication(sys.argv)
    mock_bmap = BrainMapManager()
    mock_bmap.set_node_state("FC1", "Source")
    mock_bmap.set_node_state("FC2", "Source")
    mock_bmap.set_node_state("C1", "Detector")
    mock_bmap.set_node_state("C2", "Detector")
    mock_bmap.set_node_state("Cz", "EEG")
    mock_bmap.set_node_state("Oz", "EEG")

    manager = QualityManager(sensor_types=SensorTypes.EEG_FNIRS, bmap_manager=mock_bmap)
    manager.setWindowTitle("独立测试：信号质量与阻抗评估")
    manager.resize(1100, 750)
    manager.show()
    sys.exit(app.exec_())

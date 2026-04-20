# core/widget_manager/channel.py
import sys, os
import json
import logging
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt5.QtCore import pyqtSignal

# 动态获取项目根目录，确保绝对路径导包不出错
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)
    
from ui.views.channel_view import ChannelViewWidget
from utils.paths import TEMPLATE_DIR
from utils.stats import SensorTypes

logger = logging.getLogger(__name__)

class ChannelManager(ChannelViewWidget):
    """
    配置管理控制器 (Controller)
    1. 负责静默限制拦截 (监听 spinbox 动态传给 Manager)
    2. 存取 template/montage 路径下的 JSON 模板
    3. 翻译下位机 Bitmask 协议
    """
    OnConfigSet = pyqtSignal(list, list)  
    OnConfigFinished = pyqtSignal()
    signal_status_msg = pyqtSignal(str, str)

    def __init__(self, sensor_types: SensorTypes = SensorTypes.EEG_FNIRS, parent=None):
        super().__init__(sensor_types=sensor_types, parent=parent)
        
        self.template_dir = Path(TEMPLATE_DIR)
        self._wire_signals()
        self._update_manager_limits() 
        logger.info(f"Channel Manager Initialized with sensor flags: {sensor_types.name}")

    # def _get_template_directory(self) -> Path:
    #     """保存和读取到项目根目录下的 template/montage 目录下"""
    #     # __file__ 当前在 NeuroSync/core/widget_manager/channel.py
    #     # 向上解析 3 级父目录即可稳稳获取 NeuroSync 根目录
    #     project_root = Path(__file__).resolve().parent.parent.parent
    #     template_dir = project_root / "template" / "montage"
    #     template_dir.mkdir(parents=True, exist_ok=True)
    #     return template_dir

    def _wire_signals(self):
        """绑定业务逻辑与信号拦截"""
        self.btn_clear.clicked.connect(self._handle_clear)
        self.btn_save.clicked.connect(self._handle_save)
        self.btn_load.clicked.connect(self._handle_load)
        self.btn_apply.clicked.connect(self._handle_apply)
        self.btn_finish.clicked.connect(self._handle_finish)

        # 数量限制动态绑定 (SpinBox 改变时立即通知 Manager 更新限制，由底层静默拦截)
        if hasattr(self, 'spin_eeg'): self.spin_eeg.valueChanged.connect(self._update_manager_limits)
        if hasattr(self, 'spin_src'): self.spin_src.valueChanged.connect(self._update_manager_limits)
        if hasattr(self, 'spin_det'): self.spin_det.valueChanged.connect(self._update_manager_limits)

    def _update_manager_limits(self):
        """将 UI 的最大通道数同步给底层的 BrainMapManager"""
        eeg_limit = self.spin_eeg.value() if hasattr(self, 'spin_eeg') else 0
        src_limit = self.spin_src.value() if hasattr(self, 'spin_src') else 0
        det_limit = self.spin_det.value() if hasattr(self, 'spin_det') else 0
        self.brain_manager.set_limits(eeg=eeg_limit, source=src_limit, detector=det_limit)

    # ==========================================
    # 模板存取逻辑
    # ==========================================
    def _handle_clear(self):
        reply = QMessageBox.question(self, "确认", "确定要清空所有已选的电极吗？")
        if reply == QMessageBox.Yes:
            self.brain_manager.clear_all_selections()

    def _handle_save(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存通道模板", str(self.template_dir / "my_template.json"), "JSON files (*.json)"
            )
            if not file_path: return

            # 1. 对节点进行智能排序 (保证按照 S1, S2, D1, D2, E1, E2 的自然数字顺序)
            def alias_sort_key(item):
                alias = item[1] # alias 例如 'S10'
                prefix = alias[0] if alias else ''
                num = int(alias[1:]) if len(alias)>1 and alias[1:].isdigit() else 0
                return (prefix, num)
            
            sorted_nodes = dict(sorted(self.brain_manager.node_aliases.items(), key=alias_sort_key))

            # 2. 收集有效的 fNIRS 通道对 (如 "S1-D1")
            active_fnirs_pairs = []
            for s_name, d_name in self.brain_manager.valid_channels:
                s_alias = self.brain_manager.node_aliases.get(s_name)
                d_alias = self.brain_manager.node_aliases.get(d_name)
                if s_alias and d_alias:
                    active_fnirs_pairs.append(f"{s_alias}-{d_alias}")

            config_data = {
                "channels": {
                    "eeg": self.spin_eeg.value() if hasattr(self, 'spin_eeg') else 0,
                    "semg": self.spin_semg.value() if hasattr(self, 'spin_semg') else 0,
                    "fnirs_src": self.spin_src.value() if hasattr(self, 'spin_src') else 0,
                    "fnirs_det": self.spin_det.value() if hasattr(self, 'spin_det') else 0
                },
                "sampling_rates": {
                    "eeg": int(self.combo_eeg_hz.currentText()) if hasattr(self, 'combo_eeg_hz') else 0,
                    "fnirs": int(self.combo_fnirs_hz.currentText()) if hasattr(self, 'combo_fnirs_hz') else 0,
                    "semg": int(self.combo_semg_hz.currentText()) if hasattr(self, 'combo_semg_hz') else 0
                },
                # 保存 {"FC1": "S1", "C2": "E2"} 
                "selected_nodes": sorted_nodes,
                # 保存当前有效的 fNIRS 通道对
                "fnirs_pairs": active_fnirs_pairs,
                # 依然保留黑名单，以便完美还原用户手动断开的线
                "blacklisted": list(self.brain_manager.blacklisted_channels)
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            self.signal_status_msg.emit("模板保存成功！", "#4caf50")
        except Exception as e:
            self.signal_status_msg.emit(f"模板保存失败: {e}", "#e74c3c")

    def _handle_load(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "加载通道模板", str(self.template_dir), "JSON files (*.json)"
            )
            if not file_path: return

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 1. 恢复硬件限定与采样率
            hw = data.get("channels", {})
            if "eeg" in hw and hasattr(self, 'spin_eeg'): self.spin_eeg.setValue(hw["eeg"])
            if "semg" in hw and hasattr(self, 'spin_semg'): self.spin_semg.setValue(hw["semg"])
            if "fnirs_src" in hw and hasattr(self, 'spin_src'): self.spin_src.setValue(hw["fnirs_src"])
            if "fnirs_det" in hw and hasattr(self, 'spin_det'): self.spin_det.setValue(hw["fnirs_det"])

            sr = data.get("sampling_rates", {})
            if "eeg" in sr and hasattr(self, 'combo_eeg_hz'): self.combo_eeg_hz.setCurrentText(str(sr["eeg"]))
            if "fnirs" in sr and hasattr(self, 'combo_fnirs_hz'): self.combo_fnirs_hz.setCurrentText(str(sr["fnirs"]))
            if "semg" in sr and hasattr(self, 'combo_semg_hz'): self.combo_semg_hz.setCurrentText(str(sr["semg"]))

            # 2. 恢复脑图
            self.brain_manager.clear_all_selections()
            nodes = data.get("selected_nodes", {})
            
            # 因为我们在保存时已经排好了序，所以这里依次添加时，底层会自动按顺序还原 S1, S2, D1...
            for node_name, alias in nodes.items():
                if alias.startswith('S'): state = 'Source'
                elif alias.startswith('D'): state = 'Detector'
                elif alias.startswith('E'): state = 'EEG'
                else: state = 'None'
                self.brain_manager.set_node_state(node_name, state)

            # 3. 恢复黑名单
            for pair in data.get("blacklisted", []):
                if len(pair) == 2:
                    self.brain_manager.toggle_channel_blacklist(pair[0], pair[1], True)

            self.signal_status_msg.emit("模板加载并应用成功！", "#4caf50")
        except Exception as e:
            self.signal_status_msg.emit(f"加载失败: {e}", "#e74c3c")

    # ==========================================
    # 下位机协议转换逻辑 (Bitmask)
    # ==========================================
    def _handle_apply(self):
        try:
            max_eeg = self.spin_eeg.value() if hasattr(self, 'spin_eeg') else 0
            max_src = self.spin_src.value() if hasattr(self, 'spin_src') else 0
            max_det = self.spin_det.value() if hasattr(self, 'spin_det') else 0
            max_emg = self.spin_semg.value() if hasattr(self, 'spin_semg') else 0

            config_order = self._generate_config_bytes(max_src, max_det, max_eeg, max_emg)
            sr_order = self._generate_sample_rate_bytes()

            self.OnConfigSet.emit(sr_order, config_order)

        except Exception as e:
            self.signal_status_msg.emit(f"参数配置错误: {e}", "#e74c3c")

    def _generate_config_bytes(self, actual_src, actual_det, actual_eeg, acutal_emg) -> list:
        buf = []
        if actual_src > 0 and actual_det > 0:
            fnirs_buf = [0] * actual_src
            buf.extend([SensorTypes.FNIRS, actual_src, actual_det])
            
            for s_name, d_name in self.brain_manager.valid_channels:
                s_idx = int(self.brain_manager.node_aliases[s_name][1:]) - 1
                d_idx = int(self.brain_manager.node_aliases[d_name][1:]) - 1
                if 0 <= s_idx < actual_src and 0 <= d_idx < actual_det:
                    fnirs_buf[s_idx] |= (1 << d_idx)
            
            d_bytes = (actual_det + 7) // 8
            for value in fnirs_buf:
                buf.extend([(value >> ((d_bytes - i - 1) * 8)) & 0xff for i in range(d_bytes)])

        if actual_eeg > 0:
            buf.extend([SensorTypes.EEG, actual_eeg])
            eeg_value = 0
            for alias in [a for a in self.brain_manager.node_aliases.values() if a.startswith('E')]:
                e_idx = int(alias[1:]) - 1
                if 0 <= e_idx < actual_eeg:
                    eeg_value |= (1 << e_idx)
            
            e_bytes = (actual_eeg + 7) // 8
            buf.extend([(eeg_value >> ((e_bytes - i - 1) * 8)) & 0xff for i in range(e_bytes)])
            
        if acutal_emg > 0:
            pass
            # buf.extend([SensorTypes.SEMG, acutal_emg])
            # emg_value = 0
            # for alias in [a for a in self.brain_manager.node_aliases.values() if a.startswith('E')]:
            #     e_idx = int(alias[1:]) - 1
            #     if 0 <= e_idx < actual_eeg:
            #         emg_value |= (1 << e_idx)
            
            # e_bytes = (actual_eeg + 7) // 8
            # buf.extend([(emg_value >> ((e_bytes - i - 1) * 8)) & 0xff for i in range(e_bytes)])

        return buf

    def _generate_sample_rate_bytes(self) -> list:
        buf = []
        sr_map = {"500": 1, "1000": 2, "2000": 3, "4000":4, "10": 1, "20": 2}
        
        if hasattr(self, 'combo_eeg_hz'):
            val = self.combo_eeg_hz.currentText()
            if val in sr_map: buf.extend([SensorTypes.EEG, sr_map[val]])
            
        if hasattr(self, 'combo_fnirs_hz'):
            val = self.combo_fnirs_hz.currentText()
            if val in sr_map: buf.extend([SensorTypes.FNIRS, sr_map[val]])
        
        if hasattr(self, 'combo_semg_hz'):
            val = self.combo_semg_hz.currentText()
            if val in sr_map: buf.extend([SensorTypes.SEMG, sr_map[val]])
            
        return buf

    def _handle_finish(self):
        self.OnConfigFinished.emit()
        # self.close() 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("智能通道与采样配置系统")
    # 测试环境：传入全模态枚举进行测试
    window = ChannelManager(sensor_types=SensorTypes.EEG_FNIRS)
    window.show()
    sys.exit(app.exec_())
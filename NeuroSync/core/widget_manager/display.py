import sys
import os
import logging
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt5.QtCore import QTimer, pyqtSignal, Qt, QEvent
from PyQt5.QtGui import QFont

# 动态将项目根目录加入环境变量，方便独立运行测试
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from ui.views.display_view import DisplayViewWidget
from utils.filter import SignalProcessor 

pg.setConfigOptions(antialias=False)
pg.setConfigOption('background', '#FAFAFA')  # 全局背景设为浅灰白
pg.setConfigOption('foreground', 'k')        # 全局前景（坐标轴、文字、网格）设为黑色

logger = logging.getLogger(__name__)

# 为打标事件准备 9 种高对比度颜色
MARKER_COLORS = [
    '#000000', '#9C27B0', '#E91E63', '#00838F', '#795548', 
    '#F57F17', '#4A148C', '#827717', '#C2185B', '#37474F'
]
class BaseSweepCanvas(pg.GraphicsLayoutWidget):
    def __init__(self, parent, frequency, time_window, y_offset):
        super().__init__(parent=parent)
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.frequency = frequency
        self.time_window = time_window
        self.max_points = int(self.time_window * self.frequency)
        self.y_offset = y_offset
        
        self.sweep_pos = 0
        # self.data_buffer = []
        self.stage_buffer = None 
        self.stage_ptr = 0
        
        self.baise_data = []
        self.markers = []
        
        
        self.plot_item = self.addPlot(row=0, col=0)
        self.plot_item.showGrid(x=False, y=True, alpha=0.3)
        self.plot_item.setMouseEnabled(x=False, y=False)
        self.plot_item.hideButtons()
        self.plot_item.setMenuEnabled(False)
        self.plot_item.getViewBox().disableAutoRange(axis=pg.ViewBox.XAxis)
        self.plot_item.setLimits(xMin=0, xMax=self.time_window)
        self.plot_item.setXRange(0, self.time_window, padding=0)
        
        font = QFont()
        font.setPixelSize(10) 
        self.plot_item.getAxis('left').setTickFont(font)
        
        
        self.time_data = np.arange(self.max_points) / self.frequency
        
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._render_frame)
        self.render_timer.start(33) 

    def push_data(self, data_point):
        if self.stage_buffer is None:
            self.stage_buffer = np.zeros((2000, len(data_point)), dtype=np.float32)
            
        # 直接覆盖写入，极其轻量
        if self.stage_ptr < 2000:
            self.stage_buffer[self.stage_ptr] = data_point
            self.stage_ptr += 1
        
    def draw_marker(self, key_val):
        """在游标当前位置画一条对应颜色的竖线"""
        t_val = self.time_data[self.sweep_pos]
        color = MARKER_COLORS[key_val % len(MARKER_COLORS)]
        
        line = pg.InfiniteLine(
            pos=t_val, angle=90, 
            pen=pg.mkPen(color=color, width=2.5),
            label=str(key_val), 
            labelOpts={'position': 0.95, 'color': color, 'movable': False, 'fill': (255,255,255,150)}
        )
        self.plot_item.addItem(line)
        self.markers.append({'line': line, 'pos_idx': self.sweep_pos})
        
    def reset(self):
        """彻底清空画布内容与扫描指针"""
        self.sweep_pos = 0
        self.stage_ptr = 0
            
        if isinstance(self.baise_data, list):
            self.baise_data.clear()
            
        for m in self.markers:
            self.plot_item.removeItem(m['line'])
        self.markers.clear()

class StandardPlotCanvas(BaseSweepCanvas):
    """标准单线扫描画板 (适用于 EEG / sEMG)"""
    def __init__(self, parent, channels_labels, frequency=500, time_window=5, y_offset=100.0):
        super().__init__(parent, frequency, time_window, y_offset)
        self.labels = channels_labels
        self.num_channels = len(self.labels)
        
        self.lines = []
        self.channel_data = []
        self.setMinimumHeight(max(300, self.num_channels * 60))
        self._init_plot()
        
    def _init_plot(self):
        self.plot_item.clear()
        self.channel_data.clear()
        self.lines.clear()
        self.sweep_pos = 0
        
        # 配置 Y 轴标签
        yticks_pos = [(self.num_channels - 0.5 - i) * self.y_offset for i in range(self.num_channels)]
        y_axis = self.plot_item.getAxis('left')
        y_axis.setTicks([[(y, name) for y, name in zip(yticks_pos, self.labels)]])
        self.plot_item.setYRange(0, self.num_channels * self.y_offset, padding=0)
        
        for i in range(self.num_channels):
            data = np.full(self.max_points, np.nan)
            self.channel_data.append(data)
            # 交替使用颜色增强辨识度
            color = '#3498db' if i % 2 == 0 else '#e67e22'
            line = self.plot_item.plot(
                self.time_data, data, 
                pen=pg.mkPen(color=color, width=1.5),
                connect='finite',   
                autoDownsample=True
                )
            self.lines.append(line)
            
        # 绿色扫描指针游标
        self.sweep_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('#2ecc71', width=1.5, style=Qt.PenStyle.DashLine))
        self.plot_item.addItem(self.sweep_line)

    def _render_frame(self):
        if getattr(self, 'stage_buffer', None) is None or self.stage_ptr == 0: 
            return
        n = self.stage_ptr
        new_samples = self.stage_buffer[:n]   # type: ignore
        self.stage_ptr = 0  # 游标归零，立刻开始接收下一波 UDP 推流
        
        if n > self.max_points:
            new_samples = new_samples[-self.max_points:]
            n = self.max_points
            
        end_pos = self.sweep_pos + n
        
        # 1. 填入新数据并附加 Y 轴偏移
        if end_pos <= self.max_points:
            for i in range(self.num_channels):
                y_pos = (self.num_channels - 0.5 - i) * self.y_offset
                self.channel_data[i][self.sweep_pos:end_pos] = new_samples[:, i] + y_pos
        else:
            part1 = self.max_points - self.sweep_pos
            part2 = n - part1
            for i in range(self.num_channels):
                y_pos = (self.num_channels - 0.5 - i) * self.y_offset
                self.channel_data[i][self.sweep_pos:] = new_samples[:part1, i] + y_pos
                self.channel_data[i][:part2] = new_samples[part1:, i] + y_pos
                
        # 2. 清除前方的空白擦除区
        gap = max(1, int(self.frequency * 0.1)) 
        gap_end = end_pos + gap
        if gap_end <= self.max_points:
            for i in range(self.num_channels):
                self.channel_data[i][end_pos:gap_end] = np.nan
        else:
            gap1 = self.max_points - end_pos
            gap2 = gap_end - self.max_points
            for i in range(self.num_channels):
                self.channel_data[i][end_pos:] = np.nan
                self.channel_data[i][:gap2] = np.nan
        
        # 3. 擦除游标前方的 Marker 竖线
        to_remove = []
        for m in self.markers:
            # 判断 marker 的 index 是否落在了目前的擦除空白带里
            dist = (m['pos_idx'] - end_pos) % self.max_points
            if dist <= gap:
                self.plot_item.removeItem(m['line'])
                to_remove.append(m)
        for m in to_remove:
            self.markers.remove(m)
                
        self.sweep_pos = end_pos % self.max_points
        
        # 4. 更新 PyQtGraph 曲线
        for i in range(self.num_channels):
            self.lines[i].setData(self.time_data, self.channel_data[i])
        self.sweep_line.setValue(self.time_data[self.sweep_pos])

    def update_ylim(self, new_offset):
        old_offset = self.y_offset
        self.y_offset = new_offset
        
        y_max = self.num_channels * self.y_offset 
        self.plot_item.setYRange(0, y_max, padding=0)
        
        yticks_pos = [(self.num_channels - 0.5 - i) * self.y_offset for i in range(self.num_channels)]
        self.plot_item.getAxis('left').setTicks([[(y, name) for y, name in zip(yticks_pos, self.labels)]])
        
        for i in range(self.num_channels):
            mask = ~np.isnan(self.channel_data[i])
            shift = (self.num_channels - 0.5 - i) * (new_offset - old_offset)
            self.channel_data[i][mask] += shift
            self.lines[i].setData(self.time_data, self.channel_data[i])
        
    def reset(self):
        super().reset()
        self.sweep_pos = 0
        # 填充 NaN，并立刻刷新曲线
        for i in range(self.num_channels):
            self.channel_data[i].fill(np.nan)
            self.lines[i].setData(self.time_data, self.channel_data[i])
        # 拔除画布上遗留的标线
        for m in self.markers:
            self.plot_item.removeItem(m['line'])
        self.markers.clear()


class FNIRSPlotCanvas(BaseSweepCanvas):
    """fNIRS 专用扫描画板：红/红外(或HbO/HbR) 同轴渲染"""
    def __init__(self, parent, channels_labels, frequency=10, time_window=10, y_offset=10.0):
        super().__init__(parent, frequency, time_window, y_offset)
        self.labels = channels_labels
        self.num_channels = len(self.labels)
        
        self.lines_red, self.lines_ir = [], []
        self.data_red, self.data_ir = [], []
        self._init_plot()
        
        self.setMinimumHeight(max(300, self.num_channels * 40))
        
    def _init_plot(self):
        self.plot_item.clear()
        self.data_red.clear(); self.data_ir.clear()
        self.lines_red.clear(); self.lines_ir.clear()
        self.sweep_pos = 0
        
        yticks_pos = [(self.num_channels - i - 0.5) * self.y_offset for i in range(self.num_channels)]
        self.plot_item.getAxis('left').setTicks([[(y, name) for y, name in zip(yticks_pos, self.labels)]])
        self.plot_item.setYRange(0, self.num_channels * self.y_offset, padding=0)
        
        for i in range(self.num_channels):
            d_red = np.full(self.max_points, np.nan)
            d_ir = np.full(self.max_points, np.nan)
            self.data_red.append(d_red); self.data_ir.append(d_ir)
            
            # 使用高对比度颜色，防干扰
            lr = self.plot_item.plot(
                self.time_data, d_red, 
                pen=pg.mkPen('#E74C3C', width=1.5),
                connect='finite', autoDownsample=True
            )
            li = self.plot_item.plot(
                self.time_data, d_ir, 
                pen=pg.mkPen('#2980B9', width=1.5),
                connect='finite', autoDownsample=True
            )
            self.lines_red.append(lr); self.lines_ir.append(li)
            
        self.sweep_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('#2ecc71', width=1.5, style=Qt.PenStyle.DashLine))
        self.plot_item.addItem(self.sweep_line)

    def _render_frame(self):
        if getattr(self, 'stage_buffer', None) is None or self.stage_ptr == 0: 
            return
            
        n = self.stage_ptr
        new_samples = self.stage_buffer[:n] # type: ignore
        self.stage_ptr = 0
        
        if n > self.max_points:
            new_samples = new_samples[-self.max_points:]
            n = self.max_points
            
        end_pos = self.sweep_pos + n
        
        if end_pos <= self.max_points:
            for i in range(self.num_channels):
                y_pos = (self.num_channels - 0.5 - i) * self.y_offset
                self.data_red[i][self.sweep_pos:end_pos] = new_samples[:, 2*i] + y_pos
                self.data_ir[i][self.sweep_pos:end_pos] = new_samples[:, 2*i+1] + y_pos
        else:
            part1 = self.max_points - self.sweep_pos
            part2 = n - part1
            for i in range(self.num_channels):
                y_pos = (self.num_channels - 0.5 - i) * self.y_offset
                self.data_red[i][self.sweep_pos:] = new_samples[:part1, 2*i] + y_pos
                self.data_red[i][:part2] = new_samples[part1:, 2*i] + y_pos
                self.data_ir[i][self.sweep_pos:] = new_samples[:part1, 2*i+1] + y_pos
                self.data_ir[i][:part2] = new_samples[part1:, 2*i+1] + y_pos
                
        gap = max(1, int(self.frequency * 0.1))
        gap_end = end_pos + gap
        if gap_end <= self.max_points:
            for i in range(self.num_channels):
                self.data_red[i][end_pos:gap_end] = np.nan
                self.data_ir[i][end_pos:gap_end] = np.nan
        else:
            gap1 = self.max_points - end_pos
            gap2 = gap_end - self.max_points
            for i in range(self.num_channels):
                self.data_red[i][end_pos:] = np.nan
                self.data_red[i][:gap2] = np.nan
                self.data_ir[i][end_pos:] = np.nan
                self.data_ir[i][:gap2] = np.nan
                
        to_remove = []
        for m in self.markers:
            dist = (m['pos_idx'] - end_pos) % self.max_points
            if dist <= gap:
                self.plot_item.removeItem(m['line'])
                to_remove.append(m)
        for m in to_remove:
            self.markers.remove(m)
                
        self.sweep_pos = end_pos % self.max_points
        
        for i in range(self.num_channels):
            self.lines_red[i].setData(self.time_data, self.data_red[i])
            self.lines_ir[i].setData(self.time_data, self.data_ir[i])
        self.sweep_line.setValue(self.time_data[self.sweep_pos])
        
    def update_ylim(self, new_offset):
        old_offset = self.y_offset
        self.y_offset = new_offset
        
        y_max = (self.num_channels) * self.y_offset
        self.plot_item.setYRange(0, y_max, padding=0)
        
        yticks_pos = [(self.num_channels - 0.5 - i) * self.y_offset for i in range(self.num_channels)]
        self.plot_item.getAxis('left').setTicks([[(y, name) for y, name in zip(yticks_pos, self.labels)]])
        
        for i in range(self.num_channels):
            shift = (self.num_channels - 0.5 - i) * (new_offset - old_offset) 
            mask_red = ~np.isnan(self.data_red[i])
            self.data_red[i][mask_red] += shift
            self.lines_red[i].setData(self.time_data, self.data_red[i])

            mask_ir = ~np.isnan(self.data_ir[i])
            self.data_ir[i][mask_ir] += shift
            self.lines_ir[i].setData(self.time_data, self.data_ir[i])

    def reset(self):
        super().reset()
        self.sweep_pos = 0
        for i in range(self.num_channels):
            self.data_red[i].fill(np.nan)
            self.data_ir[i].fill(np.nan)
            self.lines_red[i].setData(self.time_data, self.data_red[i])
            self.lines_ir[i].setData(self.time_data, self.data_ir[i])
        for m in self.markers:
            self.plot_item.removeItem(m['line'])
        self.markers.clear()


class DisplayManager(QWidget):
    """实时采集与滤波显示中心"""
    signal_request_start = pyqtSignal()
    signal_request_stop = pyqtSignal()
    signal_request_record = pyqtSignal(bool)
    signal_display_finished = pyqtSignal()
    signal_op_mode_changed = pyqtSignal(str) 
    signal_mark_event = pyqtSignal(int)
    
    def __init__(self, fnirs_channels=[], eeg_channels=[], semg_channels=[], fs_fnirs=10, fs_eeg=500, fs_semg=1000):
        super().__init__()
        self.ui = DisplayViewWidget()
        self.ui.setupUi(self)
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) # 开启全局强焦点，使得此 Widget 能捕获按键
        
        self.is_running = False
        self.is_recording = False
    
        
        self.ui.fnirsPanel.setVisible(bool(fnirs_channels))
        self.ui.eegPanel.setVisible(bool(eeg_channels))
        self.ui.semgPanel.setVisible(bool(semg_channels))
        
        if fnirs_channels:
            self.fnirs_canvas = FNIRSPlotCanvas(self, fnirs_channels, fs_fnirs, time_window=30)
            self.ui.plotLayout_fnirs.addWidget(self.fnirs_canvas) # type: ignore
            self.processor_fnirs = SignalProcessor(sample_rate=fs_fnirs, num_channels=len(fnirs_channels)*2)
            self._bind_filter_ui('fnirs')
            
            if hasattr(self.ui, 'comboSigType_fnirs'):
                self.ui.comboSigType_fnirs.installEventFilter(self) # type: ignore
                
        if eeg_channels:
            self.eeg_canvas = StandardPlotCanvas(self, eeg_channels, fs_eeg)
            self.ui.plotLayout_eeg.addWidget(self.eeg_canvas) # type: ignore
            self.processor_eeg = SignalProcessor(sample_rate=fs_eeg, num_channels=len(eeg_channels))
            self._bind_filter_ui('eeg')
            
        if semg_channels:
            self.semg_canvas = StandardPlotCanvas(self, semg_channels, fs_semg)
            self.ui.plotLayout_semg.addWidget(self.semg_canvas) # type: ignore
            self.processor_semg = SignalProcessor(sample_rate=fs_semg, num_channels=len(semg_channels))
            self._bind_filter_ui('semg')
            
        self._wire_signals()

    def _bind_filter_ui(self, prefix):
        chk = getattr(self.ui, f"chkEnable_{prefix}", None)
        bar = getattr(self.ui, f"filterBar_{prefix}", None)
        if not chk or not bar: return
        
        def toggle_vis(is_checked):
            bar.setVisible(is_checked)
            if is_checked:
                combo = getattr(self.ui, f"comboType_{prefix}")
                combo.currentTextChanged.emit(combo.currentText())
            else:
                processor = getattr(self, f"processor_{prefix}", None)
                if processor and hasattr(processor, 'filter_states'):
                    processor.filter_states.clear()

        def combo_change(f_type):
            if not chk.isChecked(): return
            is_band = f_type == "带通滤波"; is_low = f_type == "低通滤波"; is_high = f_type == "高通滤波"
            
            getattr(self.ui, f"lblFreq1_{prefix}").setVisible(is_band or is_low)
            getattr(self.ui, f"spinFreq1_{prefix}").setVisible(is_band or is_low)
            getattr(self.ui, f"lblFreq2_{prefix}").setVisible(is_band or is_high)
            getattr(self.ui, f"spinFreq2_{prefix}").setVisible(is_band or is_high)
            getattr(self.ui, f"lblOrder_{prefix}").setText("窗口:" if f_type == "平滑滤波(S-G)" else "阶数:")

        chk.toggled.connect(toggle_vis)
        getattr(self.ui, f"comboType_{prefix}").currentTextChanged.connect(combo_change)
        
        spin_y = getattr(self.ui, f"spinYLim_{prefix}")
        canvas = getattr(self, f"{prefix}_canvas")
        spin_y.valueChanged.connect(canvas.update_ylim)
        
        getattr(self.ui, f"btnApply_{prefix}").clicked.connect(lambda: self._apply_filter(prefix))

    def _apply_filter(self, prefix):
        is_enable = getattr(self.ui, f"chkEnable_{prefix}").isChecked()
        processor = getattr(self, f"processor_{prefix}")
        
        if not is_enable:
            processor.online_filter_states.clear()
            return
            
        f_type_str = getattr(self.ui, f"comboType_{prefix}").currentText()
        t_map = {"低通滤波": "lowpass", "高通滤波": "highpass", "带通滤波": "bandpass", "平滑滤波(S-G)": "sg"}
        
        params = {
            'low_cutoff': getattr(self.ui, f"spinFreq1_{prefix}").value(),
            'high_cutoff': getattr(self.ui, f"spinFreq2_{prefix}").value(),
            'order': getattr(self.ui, f"spinOrder_{prefix}").value(),
            'window_length': getattr(self.ui, f"spinOrder_{prefix}").value(),
            'polyorder': 3
        }
        for ch in range(processor.num_channels):
            processor.setup_online_filter(ch, t_map.get(f_type_str, "bandpass"), **params)

    def keyPressEvent(self, event): # type: ignore
        """全局键盘事件拦截：捕获 0-9 按键并在所有画布打标"""
        if not self.is_running or not self.is_recording:
            return super().keyPressEvent(event)
            
        key = event.key()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            val = key - Qt.Key.Key_0
            logger.info(f"触发打标刺激: {val}")
            
            # 画图 (如果在的话)
            if hasattr(self, 'fnirs_canvas'): self.fnirs_canvas.draw_marker(val)
            if hasattr(self, 'eeg_canvas'): self.eeg_canvas.draw_marker(val)
            if hasattr(self, 'semg_canvas'): self.semg_canvas.draw_marker(val)
            
            # 发射信号供外界落盘记录
            self.signal_mark_event.emit(val)
        else:
            super().keyPressEvent(event)
         
    def eventFilter(self, obj, event): # type: ignore
        if hasattr(self.ui, 'comboSigType_fnirs') and obj == self.ui.comboSigType_fnirs: # type: ignore
            if event.type() == QEvent.Type.MouseButtonPress:
                if self.is_recording:
                    QMessageBox.warning(self, "操作被拒绝", "数据落盘记录期间，禁止切换信号源视图类型！")
                    return True # 拦截事件，下拉框不会弹开
        return super().eventFilter(obj, event)
       
    def _wire_signals(self):
        self.ui.btnStart.clicked.connect(self.start_acquisition)
        self.ui.btnStop.clicked.connect(self.stop_acquisition)
        self.ui.btnRecord.clicked.connect(self.toggle_record)
        self.ui.btnReset.clicked.connect(self.reset_system)
        self.ui.btnComplete.clicked.connect(self.signal_display_finished.emit)
        
        if hasattr(self.ui, 'comboSigType_fnirs'):
            self.ui.comboSigType_fnirs.currentTextChanged.connect(self._apply_sigtype_change) # type: ignore
            # self.ui.comboSigType_fnirs.currentTextChanged.connect(self.signal_op_mode_changed.emit) # type: ignore
            
        self.ui.btnStart.setEnabled(True)
        self.ui.btnStop.setEnabled(False)
        self.ui.btnRecord.setEnabled(False)

    def push_new_data(self, fnirs_raw: list, eeg_raw: list, semg_raw: list=[]):
        if not self.is_running: return
        
        if fnirs_raw and hasattr(self, 'processor_fnirs'):
            f_data = [self.processor_fnirs.process_sample_online(i, v) for i, v in enumerate(fnirs_raw)]
            if hasattr(self.ui, 'comboSigType_fnirs'):
                if self.ui.comboSigType_fnirs.currentText() == "Heamo": # type: ignore
                    if not self.fnirs_canvas.baise_data or len(self.fnirs_canvas.baise_data) != len(f_data):
                        self.fnirs_canvas.baise_data = f_data.copy()
                    if len(f_data) == len(self.fnirs_canvas.baise_data):
                        f_data = [f - b for f, b in zip(f_data, self.fnirs_canvas.baise_data)]
            self.fnirs_canvas.push_data(f_data)
            
        if eeg_raw and hasattr(self, 'processor_eeg'):
            e_data = [self.processor_eeg.process_sample_online(i, v) for i, v in enumerate(eeg_raw)]
            self.eeg_canvas.push_data(e_data)

    def start_acquisition(self):
        self.is_running = True
        self.ui.btnStart.setEnabled(False)
        self.ui.btnStop.setEnabled(True)
        self.ui.btnRecord.setEnabled(True) 
        self.ui.btnReset.setEnabled(True)
        self.ui.btnComplete.setEnabled(False)
        
        self.is_recording = False
        self.ui.btnRecord.setText("记录")
        self.ui.btnRecord.setStyleSheet("")
        
        if hasattr(self, 'fnirs_canvas'): self.fnirs_canvas.reset()
        if hasattr(self, 'eeg_canvas'): self.eeg_canvas.reset()
        
        logger.info("开始实时采集数据。")
        self.setFocus()# 防止点击后焦点丢失，导致捕获不到 0-9 键盘按键
        self.signal_request_start.emit()
        
    def stop_acquisition(self):
        self.is_running = False
        self.ui.btnStart.setEnabled(True)
        self.ui.btnStop.setEnabled(False)
        self.ui.btnRecord.setEnabled(False)
        self.ui.btnReset.setEnabled(True)
        self.ui.btnComplete.setEnabled(False)
        
        self.is_recording = False
        self.ui.btnRecord.setText("记录")
        self.ui.btnRecord.setStyleSheet("")
            
        logger.info("实时采集已停止。")
        self.signal_request_stop.emit()
        
    def toggle_record(self):
        self.is_recording = True
        self.ui.btnRecord.setText("记录中...")
        self.ui.btnRecord.setEnabled(False)  # 禁用自身，防止乱点
        self.ui.btnRecord.setStyleSheet("background-color: #e74c3c; color: white; border: none; font-weight: bold;")
        self.ui.btnReset.setEnabled(False)
        
        self.signal_request_record.emit(True)
    
    def _apply_sigtype_change(self, new_type):
        self.signal_op_mode_changed.emit(new_type)
        self.reset_system() # 切换信号类型时重置画布与滤波器，避免数据错乱

    def reset_system(self):
        logger.info("重置画布与滤波器。")
        if hasattr(self, 'processor_fnirs'): self.processor_fnirs.reset_online_filters(); self.fnirs_canvas.reset()
        if hasattr(self, 'processor_eeg'): self.processor_eeg.reset_online_filters(); self.eeg_canvas.reset()


# ==========================================
# 🚀 独立测试台
# ==========================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    app = QApplication(sys.argv)
    
    mock_fnirs_chs = ["S1-D1", "S1-D2", "S2-D3", "S3-D4"] 
    mock_eeg_chs = ["Cz", "Oz", "Pz", "Fz"]
    
    manager = DisplayManager(fnirs_channels=mock_fnirs_chs, eeg_channels=mock_eeg_chs, fs_fnirs=10, fs_eeg=500)
    manager.setWindowTitle("NeuroSync 实时多模态波形与滤波测试系统 (PyQt5 扫描版)")
    manager.resize(1300, 800)
    
    t = 0.0
    def mock_data_pump():
        global t
        if not manager.is_running: return
        t += 1.0 / 500.0 
        
        clean_eeg = np.sin(2 * np.pi * 2 * t) * 50  
        noise_eeg = np.sin(2 * np.pi * 50 * t) * 30 + np.random.normal(0, 10)
        eeg_val = clean_eeg + noise_eeg
        mock_eeg = [eeg_val, eeg_val*0.5, eeg_val*0.8, eeg_val*0.3]
        
        if int(t * 500) % 50 == 0: 
            val = np.sin(2 * np.pi * 0.1 * t) * 5 + np.random.normal(0, 2)
            mock_fnirs = [val + 2, val - 1, val + 1, val - 2, val + 3, val - 1.5, val + 2.5, val - 0.5]
            manager.push_new_data(mock_fnirs, mock_eeg)
        else:
            manager.push_new_data([], mock_eeg)

    pump_timer = QTimer()
    pump_timer.timeout.connect(mock_data_pump)
    pump_timer.start(2) # 2ms = 500Hz
    
    manager.show()
    sys.exit(app.exec_())
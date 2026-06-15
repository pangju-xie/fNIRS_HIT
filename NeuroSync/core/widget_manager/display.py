import logging
import os
import sys
from collections import deque
from threading import Lock

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QEvent, QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from ui.views.display_view import DisplayViewWidget
from utils.filter import SignalProcessor


pg.setConfigOptions(antialias=False)
pg.setConfigOption("background", "#FAFAFA")
pg.setConfigOption("foreground", "k")

logger = logging.getLogger(__name__)

FILTER_LABEL_MAP = {
    "低通": "lowpass",
    "高通": "highpass",
    "带通": "bandpass",
    "平滑 (S-G)": "sg",
    "Lowpass": "lowpass",
    "Highpass": "highpass",
    "Bandpass": "bandpass",
    "Smooth (S-G)": "sg",
}

MARKER_COLORS = [
    "#000000",
    "#9C27B0",
    "#E91E63",
    "#00838F",
    "#795548",
    "#F57F17",
    "#4A148C",
    "#827717",
    "#C2185B",
    "#37474F",
]

EEG_TRACE_COLORS = [
    "#E74C3C",
    "#3498DB",
    "#16A085",
    "#F39C12",
    "#8E44AD",
    "#2ECC71",
    "#D35400",
    "#2980B9",
]


class DisplayProcessingWorker(QObject):
    signal_fnirs_processed = pyqtSignal(object)
    signal_eeg_processed = pyqtSignal(object)
    signal_semg_processed = pyqtSignal(object)

    PROCESS_INTERVAL_MS = 25

    def __init__(self, fs_fnirs, fnirs_channels, fs_eeg, eeg_channels, fs_semg, semg_channels, eeg_alpha):
        super().__init__()
        self.processor_fnirs = SignalProcessor(sample_rate=fs_fnirs, num_channels=fnirs_channels * 2) if fnirs_channels else None
        self.processor_eeg = SignalProcessor(sample_rate=fs_eeg, num_channels=eeg_channels) if eeg_channels else None
        self.processor_semg = SignalProcessor(sample_rate=fs_semg, num_channels=semg_channels) if semg_channels else None
        self._running = False
        self._fnirs_signal_type = "血氧"
        self._eeg_display_alpha = eeg_alpha
        self._eeg_display_baseline = None
        self._fnirs_baseline = None
        self._queue_lock = Lock()
        self._process_timer = None
        self._input_queues = {
            "fnirs": deque(),
            "eeg": deque(),
            "semg": deque(),
        }
        self._queued_rows = {"fnirs": 0, "eeg": 0, "semg": 0}
        self._max_pending_rows = {
            "fnirs": max(int(fs_fnirs) * 10, 100),
            "eeg": max(int(fs_eeg) * 2, 2000),
            "semg": max(int(fs_semg) * 2, 2000),
        }

    @pyqtSlot()
    def start_loop(self):
        if self._process_timer is None:
            self._process_timer = QTimer()
            self._process_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._process_timer.timeout.connect(self._process_pending)
        self._process_timer.start(self.PROCESS_INTERVAL_MS)

    @pyqtSlot()
    def stop_loop(self):
        if self._process_timer is not None:
            self._process_timer.stop()

    @pyqtSlot(bool)
    def set_running(self, running):
        self._running = bool(running)
        if not self._running:
            self.clear_pending_inputs()

    @pyqtSlot()
    def reset_processing_state(self):
        self.clear_pending_inputs()
        self._eeg_display_baseline = None
        self._fnirs_baseline = None
        for processor in (self.processor_fnirs, self.processor_eeg, self.processor_semg):
            if processor:
                processor.reset_online_filters()

    @pyqtSlot(str)
    def set_fnirs_signal_type(self, signal_type):
        self._fnirs_signal_type = signal_type
        self._fnirs_baseline = None

    @pyqtSlot(str, object)
    def configure_filter(self, prefix, filter_payload):
        processor = getattr(self, f"processor_{prefix}", None)
        if not processor:
            return
        if not filter_payload:
            processor.clear_online_filters()
            return
        processor.setup_online_filter_for_all_channels(filter_payload["filter_type"], **filter_payload["params"])

    def enqueue_stream(self, modality, payload):
        if modality not in self._input_queues or payload is None:
            return

        array = np.asarray(payload, dtype=np.float32)
        if array.size == 0:
            return
        if array.ndim == 1:
            array = array.reshape(1, -1)

        with self._queue_lock:
            queue = self._input_queues[modality]
            queue.append(array)
            self._queued_rows[modality] += len(array)
            self._trim_pending_locked(modality)

    def clear_pending_inputs(self):
        with self._queue_lock:
            for modality, queue in self._input_queues.items():
                queue.clear()
                self._queued_rows[modality] = 0

    def _trim_pending_locked(self, modality):
        max_rows = self._max_pending_rows[modality]
        queue = self._input_queues[modality]
        while self._queued_rows[modality] > max_rows and queue:
            overflow = self._queued_rows[modality] - max_rows
            head = queue[0]
            if len(head) <= overflow:
                queue.popleft()
                self._queued_rows[modality] -= len(head)
            else:
                queue[0] = head[overflow:]
                self._queued_rows[modality] -= overflow

    def _drain_pending(self, modality):
        with self._queue_lock:
            queue = self._input_queues[modality]
            if not queue:
                return None
            chunks = list(queue)
            queue.clear()
            self._queued_rows[modality] = 0
        if len(chunks) == 1:
            return chunks[0]
        return np.concatenate(chunks, axis=0)

    @pyqtSlot()
    def _process_pending(self):
        if not self._running:
            return

        fnirs_batch = self._drain_pending("fnirs")
        if self.processor_fnirs is not None and fnirs_batch is not None and fnirs_batch.size:
            self.signal_fnirs_processed.emit(self._process_fnirs_batch(fnirs_batch))

        eeg_batch = self._drain_pending("eeg")
        if self.processor_eeg is not None and eeg_batch is not None and eeg_batch.size:
            self.signal_eeg_processed.emit(self._process_eeg_batch(eeg_batch))

        semg_batch = self._drain_pending("semg")
        if self.processor_semg is not None and semg_batch is not None and semg_batch.size:
            self.signal_semg_processed.emit(self._process_semg_batch(semg_batch))

    def _process_fnirs_batch(self, batch):
        filtered = np.zeros_like(batch, dtype=np.float32)
        for sample_idx, sample in enumerate(batch):
            current = np.asarray(
                [self.processor_fnirs.process_sample_online(i, value) for i, value in enumerate(sample)],
                dtype=np.float32,
            )
            if self._fnirs_signal_type == "血氧":
                if self._fnirs_baseline is None or len(self._fnirs_baseline) != len(current):
                    self._fnirs_baseline = current.copy()
                current = current - self._fnirs_baseline
            filtered[sample_idx] = current
        return filtered

    def _process_eeg_batch(self, batch):
        filtered = np.zeros_like(batch, dtype=np.float32)
        for sample_idx, sample in enumerate(batch):
            filtered[sample_idx] = [self.processor_eeg.process_sample_online(i, value) for i, value in enumerate(sample)]
        return self._prepare_eeg_batch(filtered)

    def _process_semg_batch(self, batch):
        filtered = np.zeros_like(batch, dtype=np.float32)
        for sample_idx, sample in enumerate(batch):
            filtered[sample_idx] = [self.processor_semg.process_sample_online(i, value) for i, value in enumerate(sample)]
        return filtered

    def _prepare_eeg_sample(self, sample):
        if sample.size == 0:
            return sample
        if self._eeg_display_baseline is None or len(self._eeg_display_baseline) != len(sample):
            self._eeg_display_baseline = sample.copy()
            return np.zeros_like(sample, dtype=np.float32)
        alpha = self._eeg_display_alpha if self._eeg_display_alpha > 0 else 0.004
        self._eeg_display_baseline += alpha * (sample - self._eeg_display_baseline)
        return sample - self._eeg_display_baseline

    def _prepare_eeg_batch(self, batch):
        prepared = np.zeros_like(batch, dtype=np.float32)
        for idx, sample in enumerate(batch):
            prepared[idx] = self._prepare_eeg_sample(sample)
        return prepared


class BaseSweepCanvas(pg.GraphicsLayoutWidget):
    def __init__(self, parent, frequency, time_window, y_offset, render_interval_ms=25, pending_seconds=2.0):
        super().__init__(parent=parent)
        self.manager = parent
        self.frequency = frequency
        self.time_window = time_window
        self.max_points = max(int(self.time_window * self.frequency), 1)
        self.y_offset = y_offset
        self.sweep_pos = 0
        self.sample_index = 0
        self.stage_buffer = None
        self.stage_capacity = max(int(self.frequency * pending_seconds), self.max_points * 2, 256)
        self.stage_channels = 0
        self.stage_head = 0
        self.stage_size = 0
        self.pending_version = 0
        self.last_rendered_version = 0
        self.render_interval_ms = render_interval_ms
        self._last_tick_window_start = None
        self.markers = []
        self.time_data = np.arange(self.max_points, dtype=np.float32) / self.frequency

        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.plot_item = self.addPlot(row=0, col=0)
        self.plot_item.showGrid(x=False, y=True, alpha=0.1)
        self.plot_item.setMouseEnabled(x=False, y=False)
        self.plot_item.hideButtons()
        self.plot_item.setMenuEnabled(False)
        self.plot_item.getViewBox().disableAutoRange(axis=pg.ViewBox.XAxis)
        self.plot_item.setLimits(xMin=0, xMax=self.time_window)
        self.plot_item.setXRange(0, self.time_window, padding=0)
        self._update_x_axis_labels(force=True)

        font = QFont()
        font.setPixelSize(10)
        self.plot_item.getAxis("left").setTickFont(font)
        self.plot_item.getAxis("bottom").setTickFont(font)

        self.render_timer = QTimer(self)
        self.render_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.render_timer.timeout.connect(self._render_frame)
        self.render_timer.start(self.render_interval_ms)

    def _ensure_stage_buffer(self, channels):
        if self.stage_buffer is None or self.stage_channels != channels:
            self.stage_channels = channels
            self.stage_buffer = np.zeros((self.stage_capacity, channels), dtype=np.float32)
            self.stage_head = 0
            self.stage_size = 0

    def push_data(self, data_point):
        self.push_batch_data(np.asarray(data_point, dtype=np.float32))

    def push_batch_data(self, batch_points):
        batch = np.asarray(batch_points, dtype=np.float32)
        if batch.size == 0:
            return
        if batch.ndim == 1:
            batch = batch.reshape(1, -1)
        self._ensure_stage_buffer(batch.shape[1])
        if len(batch) >= self.stage_capacity:
            batch = batch[-self.stage_capacity :]
            self.stage_head = 0
            self.stage_size = 0
        for row in batch:
            write_idx = (self.stage_head + self.stage_size) % self.stage_capacity
            self.stage_buffer[write_idx] = row
            if self.stage_size < self.stage_capacity:
                self.stage_size += 1
            else:
                self.stage_head = (self.stage_head + 1) % self.stage_capacity
        self.pending_version += 1

    def _consume_pending_batch(self):
        if self.stage_buffer is None or self.stage_size == 0:
            return None
        end = self.stage_head + self.stage_size
        if end <= self.stage_capacity:
            batch = self.stage_buffer[self.stage_head:end].copy()
        else:
            first = self.stage_buffer[self.stage_head:]
            second = self.stage_buffer[: end % self.stage_capacity]
            batch = np.concatenate((first, second), axis=0)
        self.stage_head = 0
        self.stage_size = 0
        self.last_rendered_version = self.pending_version
        return batch

    def clear_pending_samples(self):
        self.stage_head = 0
        self.stage_size = 0

    def stop_rendering(self):
        self.render_timer.stop()

    def start_rendering(self):
        if not self.render_timer.isActive():
            self.render_timer.start(self.render_interval_ms)

    def draw_marker(self, key_val):
        t_val = float(self.time_data[self.sweep_pos])
        color = MARKER_COLORS[key_val % len(MARKER_COLORS)]
        line = pg.InfiniteLine(
            pos=t_val,
            angle=90,
            pen=pg.mkPen(color=color, width=2),
            label=str(key_val),
            labelOpts={"position": 0.95, "color": color, "movable": False, "fill": (255, 255, 255, 160)},
        )
        self.plot_item.addItem(line)
        self.markers.append({"line": line, "pos_idx": self.sweep_pos})

    def _clear_markers(self):
        for marker in self.markers:
            self.plot_item.removeItem(marker["line"])
        self.markers.clear()

    def reset(self):
        self.sweep_pos = 0
        self.sample_index = 0
        self.stage_head = 0
        self.stage_size = 0
        self.pending_version = 0
        self.last_rendered_version = 0
        self._last_tick_window_start = None
        self.plot_item.setXRange(0, self.time_window, padding=0)
        self._update_x_axis_labels(force=True)
        self._clear_markers()

    def _current_window_start(self):
        if self.sample_index <= 0:
            return 0.0
        completed_windows = max((self.sample_index - 1) // self.max_points, 0)
        return completed_windows * self.time_window

    def _format_time_tick(self, value):
        if abs(value - round(value)) < 1e-6:
            return str(int(round(value)))
        return f"{value:.1f}"

    def _update_x_axis_labels(self, force=False):
        tick_positions = np.linspace(0.0, self.time_window, 6)
        window_start = self._current_window_start()
        if not force and self._last_tick_window_start is not None and abs(window_start - self._last_tick_window_start) < 1e-6:
            return
        ticks = [(float(pos), self._format_time_tick(window_start + float(pos))) for pos in tick_positions]
        self.plot_item.getAxis("bottom").setTicks([ticks])
        self._last_tick_window_start = window_start

    def _render_frame(self):
        raise NotImplementedError


class StandardPlotCanvas(BaseSweepCanvas):
    def __init__(self, parent, channels_labels, frequency=500, time_window=5, y_offset=100.0, trace_colors=None, render_interval_ms=25):
        self.labels = channels_labels
        self.num_channels = len(self.labels)
        self.trace_colors = trace_colors or []
        super().__init__(parent, frequency, time_window, y_offset, render_interval_ms=render_interval_ms, pending_seconds=2.0)
        self.channel_data = [np.full(self.max_points, np.nan, dtype=np.float32) for _ in range(self.num_channels)]
        self.lines = []
        self.setMinimumHeight(max(300, self.num_channels * 60))
        self._init_plot()

    def _channel_center(self, idx):
        return (self.num_channels - 0.5 - idx) * self.y_offset

    def _init_plot(self):
        self.plot_item.clear()
        self.lines.clear()
        ticks = []
        for i, name in enumerate(self.labels):
            center = self._channel_center(i)
            ticks.append((center, name))
            color = self.trace_colors[i % len(self.trace_colors)] if self.trace_colors else ("#3498db" if i % 2 == 0 else "#e67e22")
            line = self.plot_item.plot(
                self.time_data,
                self.channel_data[i],
                pen=pg.mkPen(color=color, width=1.5),
                connect="finite",
                autoDownsample=True,
            )
            self.lines.append(line)
        self.plot_item.getAxis("left").setTicks([ticks])
        self.plot_item.setYRange(0, max(self.num_channels, 1) * self.y_offset, padding=0)
        self.sweep_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("#2ecc71", width=1.5, style=Qt.PenStyle.DashLine))
        self.plot_item.addItem(self.sweep_line)

    def _render_frame(self):
        if self.pending_version == self.last_rendered_version or self.stage_size == 0:
            return
        new_samples = self._consume_pending_batch()
        if new_samples is None or len(new_samples) == 0:
            return
        if len(new_samples) >= self.max_points:
            new_samples = new_samples[-self.max_points :]

        sample_count = len(new_samples)
        write_indices = (np.arange(sample_count) + self.sweep_pos) % self.max_points
        for ch_idx in range(self.num_channels):
            self.channel_data[ch_idx][write_indices] = new_samples[:, ch_idx] + self._channel_center(ch_idx)

        next_pos = (self.sweep_pos + sample_count) % self.max_points
        for ch_idx in range(self.num_channels):
            self.channel_data[ch_idx][next_pos] = np.nan

        self.sweep_pos = next_pos
        self.sample_index += sample_count
        self._update_x_axis_labels()

        for ch_idx in range(self.num_channels):
            self.lines[ch_idx].setData(self.time_data, self.channel_data[ch_idx])
        self.sweep_line.setValue(float(self.time_data[self.sweep_pos]))

    def update_ylim(self, new_offset):
        new_offset = max(float(new_offset), 0.001)
        old_offset = self.y_offset
        self.y_offset = new_offset

        ticks = [(self._channel_center(i), name) for i, name in enumerate(self.labels)]
        self.plot_item.getAxis("left").setTicks([ticks])
        self.plot_item.setYRange(0, max(self.num_channels, 1) * self.y_offset, padding=0)

        if old_offset == new_offset:
            return

        for ch_idx in range(self.num_channels):
            old_center = (self.num_channels - 0.5 - ch_idx) * old_offset
            new_center = self._channel_center(ch_idx)
            valid_mask = ~np.isnan(self.channel_data[ch_idx])
            self.channel_data[ch_idx][valid_mask] += new_center - old_center
            self.lines[ch_idx].setData(self.time_data, self.channel_data[ch_idx])

    def reset(self):
        super().reset()
        for ch_idx in range(self.num_channels):
            self.channel_data[ch_idx].fill(np.nan)
            self.lines[ch_idx].setData(self.time_data, self.channel_data[ch_idx])
        self.sweep_line.setValue(0)


class FNIRSPlotCanvas(BaseSweepCanvas):
    def __init__(self, parent, channels_labels, frequency=10, time_window=30, y_offset=10.0, render_interval_ms=40):
        self.labels = channels_labels
        self.num_channels = len(self.labels)
        super().__init__(parent, frequency, time_window, y_offset, render_interval_ms=render_interval_ms, pending_seconds=6.0)
        self.data_red = [np.full(self.max_points, np.nan, dtype=np.float32) for _ in range(self.num_channels)]
        self.data_ir = [np.full(self.max_points, np.nan, dtype=np.float32) for _ in range(self.num_channels)]
        self.raw_red_history = [np.full(self.max_points, np.nan, dtype=np.float32) for _ in range(self.num_channels)]
        self.raw_ir_history = [np.full(self.max_points, np.nan, dtype=np.float32) for _ in range(self.num_channels)]
        self.raw_mode_channel_stats = [(0.0, 0.0, 0.0, 0.0) for _ in range(self.num_channels)]
        self.lines_red = []
        self.lines_ir = []
        self.setMinimumHeight(max(300, self.num_channels * 40))
        self._init_plot()

    def _channel_center(self, idx):
        return (self.num_channels - 0.5 - idx) * self.y_offset

    def _init_plot(self):
        self.plot_item.clear()
        self.lines_red.clear()
        self.lines_ir.clear()
        ticks = self._build_axis_ticks()
        for i, name in enumerate(self.labels):
            center = self._channel_center(i)
            red_line = self.plot_item.plot(
                self.time_data,
                self.data_red[i],
                pen=pg.mkPen("#E74C3C", width=2.0),
                connect="finite",
                autoDownsample=True,
            )
            ir_line = self.plot_item.plot(
                self.time_data,
                self.data_ir[i],
                pen=pg.mkPen("#2980B9", width=2.0),
                connect="finite",
                autoDownsample=True,
            )
            self.lines_red.append(red_line)
            self.lines_ir.append(ir_line)
        self.plot_item.getAxis("left").setTicks([ticks])
        self.plot_item.setYRange(0, max(self.num_channels, 1) * self.y_offset, padding=0)
        self.sweep_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("#2ecc71", width=1.5, style=Qt.PenStyle.DashLine))
        self.plot_item.addItem(self.sweep_line)

    def _is_raw_mode(self):
        combo = getattr(self.manager.ui, "comboSigType_fnirs", None)
        return bool(combo and combo.currentText() == "原始")

    def _format_mean_text(self, value):
        if abs(value) >= 1000:
            return f"{value:.0f}"
        if abs(value) >= 100:
            return f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _build_axis_ticks(self):
        ticks = []
        raw_mode = self._is_raw_mode()
        for i, name in enumerate(self.labels):
            center = self._channel_center(i)
            if raw_mode:
                red_center, red_half_span, ir_center, ir_half_span = self.raw_mode_channel_stats[i]
                label = (
                    f"{name}\n"
                    f"🔴 Red {self._format_mean_text(red_center)} ± {self._format_mean_text(red_half_span)}\n"
                    f"🔵 IR {self._format_mean_text(ir_center)} ± {self._format_mean_text(ir_half_span)}"
                )
            else:
                label = name
            ticks.append((center, label))
        return ticks

    def _refresh_axis_ticks(self):
        self.plot_item.getAxis("left").setTicks([self._build_axis_ticks()])

    def refresh_signal_mode_labels(self):
        self._refresh_axis_ticks()

    def _render_frame(self):
        if self.pending_version == self.last_rendered_version or self.stage_size == 0:
            return
        new_samples = self._consume_pending_batch()
        if new_samples is None or len(new_samples) == 0:
            return
        if len(new_samples) >= self.max_points:
            new_samples = new_samples[-self.max_points :]

        sample_count = len(new_samples)
        write_indices = (np.arange(sample_count) + self.sweep_pos) % self.max_points
        is_raw_mode = self._is_raw_mode()
        display_half_span = max(self.y_offset * 0.42, 1e-6)

        for ch_idx in range(self.num_channels):
            center = self._channel_center(ch_idx)
            red_vals = new_samples[:, 2 * ch_idx].astype(np.float32)
            ir_vals = new_samples[:, 2 * ch_idx + 1].astype(np.float32)
            self.raw_red_history[ch_idx][write_indices] = red_vals
            self.raw_ir_history[ch_idx][write_indices] = ir_vals
            if is_raw_mode:
                valid_red = self.raw_red_history[ch_idx][~np.isnan(self.raw_red_history[ch_idx])]
                valid_ir = self.raw_ir_history[ch_idx][~np.isnan(self.raw_ir_history[ch_idx])]
                red_min = float(np.min(valid_red)) if valid_red.size else 0.0
                red_max = float(np.max(valid_red)) if valid_red.size else 0.0
                ir_min = float(np.min(valid_ir)) if valid_ir.size else 0.0
                ir_max = float(np.max(valid_ir)) if valid_ir.size else 0.0
                red_center = (red_max + red_min) / 2.0
                ir_center = (ir_max + ir_min) / 2.0
                red_half_span = max((red_max - red_min) / 2.0, 1e-6)
                ir_half_span = max((ir_max - ir_min) / 2.0, 1e-6)
                self.raw_mode_channel_stats[ch_idx] = (red_center, red_half_span, ir_center, ir_half_span)
                red_vals = (red_vals - red_center) * (display_half_span / red_half_span)
                ir_vals = (ir_vals - ir_center) * (display_half_span / ir_half_span)
            self.data_red[ch_idx][write_indices] = red_vals + center
            self.data_ir[ch_idx][write_indices] = ir_vals + center

        next_pos = (self.sweep_pos + sample_count) % self.max_points
        for ch_idx in range(self.num_channels):
            self.data_red[ch_idx][next_pos] = np.nan
            self.data_ir[ch_idx][next_pos] = np.nan
            self.raw_red_history[ch_idx][next_pos] = np.nan
            self.raw_ir_history[ch_idx][next_pos] = np.nan

        self.sweep_pos = next_pos
        self.sample_index += sample_count
        self._update_x_axis_labels()
        self._refresh_axis_ticks()

        for ch_idx in range(self.num_channels):
            self.lines_red[ch_idx].setData(self.time_data, self.data_red[ch_idx])
            self.lines_ir[ch_idx].setData(self.time_data, self.data_ir[ch_idx])
        self.sweep_line.setValue(float(self.time_data[self.sweep_pos]))

    def update_ylim(self, new_offset, channel_info=None):
        del channel_info
        new_offset = max(float(new_offset), 0.001)
        old_offset = self.y_offset
        self.y_offset = new_offset

        self._refresh_axis_ticks()
        self.plot_item.setYRange(0, max(self.num_channels, 1) * self.y_offset, padding=0)

        if old_offset == new_offset:
            return

        for ch_idx in range(self.num_channels):
            old_center = (self.num_channels - 0.5 - ch_idx) * old_offset
            new_center = self._channel_center(ch_idx)
            shift = new_center - old_center
            for data, line in ((self.data_red[ch_idx], self.lines_red[ch_idx]), (self.data_ir[ch_idx], self.lines_ir[ch_idx])):
                valid_mask = ~np.isnan(data)
                data[valid_mask] += shift
                line.setData(self.time_data, data)

    def reset(self):
        super().reset()
        self.raw_mode_channel_stats = [(0.0, 0.0, 0.0, 0.0) for _ in range(self.num_channels)]
        self._refresh_axis_ticks()
        for ch_idx in range(self.num_channels):
            self.data_red[ch_idx].fill(np.nan)
            self.data_ir[ch_idx].fill(np.nan)
            self.raw_red_history[ch_idx].fill(np.nan)
            self.raw_ir_history[ch_idx].fill(np.nan)
            self.lines_red[ch_idx].setData(self.time_data, self.data_red[ch_idx])
            self.lines_ir[ch_idx].setData(self.time_data, self.data_ir[ch_idx])
        self.sweep_line.setValue(0)


class DisplayManager(QWidget):
    signal_request_start = pyqtSignal()
    signal_request_stop = pyqtSignal()
    signal_request_record = pyqtSignal(bool)
    signal_display_finished = pyqtSignal()
    signal_op_mode_changed = pyqtSignal(str)
    signal_mark_event = pyqtSignal(int)
    signal_worker_running = pyqtSignal(bool)
    signal_worker_reset = pyqtSignal()
    signal_worker_filter = pyqtSignal(str, object)
    signal_worker_fnirs_mode = pyqtSignal(str)

    def __init__(self, fnirs_channels=[], eeg_channels=[], semg_channels=[], fs_fnirs=10, fs_eeg=500, fs_semg=1000):
        super().__init__()
        self.ui = DisplayViewWidget()
        self.ui.setupUi(self)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.is_running = False
        self.is_recording = False
        self._eeg_display_alpha = 0.0
        self._filter_state_cache = {}

        self.ui.fnirsPanel.setVisible(bool(fnirs_channels))
        self.ui.eegPanel.setVisible(bool(eeg_channels))
        self.ui.semgPanel.setVisible(bool(semg_channels))

        if fnirs_channels:
            self.fnirs_canvas = FNIRSPlotCanvas(self, fnirs_channels, fs_fnirs, time_window=30, y_offset=10.0, render_interval_ms=40)
            self.ui.plotLayout_fnirs.addWidget(self.fnirs_canvas)  # type: ignore
            self._bind_filter_ui("fnirs")
            if hasattr(self.ui, "comboSigType_fnirs"):
                self.ui.comboSigType_fnirs.installEventFilter(self)  # type: ignore

        if eeg_channels:
            self.eeg_canvas = StandardPlotCanvas(
                self,
                eeg_channels,
                fs_eeg,
                y_offset=100.0,
                trace_colors=EEG_TRACE_COLORS,
                render_interval_ms=25,
            )
            self.ui.plotLayout_eeg.addWidget(self.eeg_canvas)  # type: ignore
            self._eeg_display_alpha = min(1.0, 2.0 / max(float(fs_eeg), 1.0))
            self._bind_filter_ui("eeg")
            self._init_default_eeg_filter()
            logger.info("EEG 显示画布已初始化：采样率=%s Hz，通道=%s", fs_eeg, eeg_channels)

        if semg_channels:
            self.semg_canvas = StandardPlotCanvas(self, semg_channels, fs_semg, y_offset=100.0, render_interval_ms=25)
            self.ui.plotLayout_semg.addWidget(self.semg_canvas)  # type: ignore
            self._bind_filter_ui("semg")

        self._init_processing_worker(fs_fnirs, len(fnirs_channels), fs_eeg, len(eeg_channels), fs_semg, len(semg_channels))
        self._wire_signals()

    def _init_processing_worker(self, fs_fnirs, fnirs_channels, fs_eeg, eeg_channels, fs_semg, semg_channels):
        self.processing_thread = QThread(self)
        self.processing_worker = DisplayProcessingWorker(
            fs_fnirs,
            fnirs_channels,
            fs_eeg,
            eeg_channels,
            fs_semg,
            semg_channels,
            self._eeg_display_alpha,
        )
        self.processing_worker.moveToThread(self.processing_thread)
        self.processing_thread.started.connect(self.processing_worker.start_loop)
        self.processing_thread.finished.connect(self.processing_worker.stop_loop)
        self.processing_thread.finished.connect(self.processing_worker.deleteLater)
        self.processing_thread.finished.connect(self.processing_thread.deleteLater)
        self.signal_worker_running.connect(self.processing_worker.set_running)
        self.signal_worker_reset.connect(self.processing_worker.reset_processing_state)
        self.signal_worker_filter.connect(self.processing_worker.configure_filter)
        self.signal_worker_fnirs_mode.connect(self.processing_worker.set_fnirs_signal_type)
        if hasattr(self, "fnirs_canvas"):
            self.processing_worker.signal_fnirs_processed.connect(self.fnirs_canvas.push_batch_data)
        if hasattr(self, "eeg_canvas"):
            self.processing_worker.signal_eeg_processed.connect(self.eeg_canvas.push_batch_data)
        if hasattr(self, "semg_canvas"):
            self.processing_worker.signal_semg_processed.connect(self.semg_canvas.push_batch_data)
        self.processing_thread.start()
        init_mode = getattr(self.ui, "comboSigType_fnirs", None)
        self.signal_worker_fnirs_mode.emit(init_mode.currentText() if init_mode else "血氧")

    def _bind_filter_ui(self, prefix):
        chk = getattr(self.ui, f"chkEnable_{prefix}", None)
        bar = getattr(self.ui, f"filterBar_{prefix}", None)
        if not chk or not bar:
            return

        def toggle_vis(is_checked):
            bar.setVisible(is_checked)
            if is_checked:
                combo = getattr(self.ui, f"comboType_{prefix}")
                combo.currentTextChanged.emit(combo.currentText())
            else:
                self._filter_state_cache.pop(prefix, None)
                self.signal_worker_filter.emit(prefix, {})

        def combo_change(f_type):
            if not chk.isChecked():
                return
            is_band = f_type in {"带通", "Bandpass"}
            is_low = f_type in {"低通", "Lowpass"}
            is_high = f_type in {"高通", "Highpass"}
            getattr(self.ui, f"lblFreq1_{prefix}").setVisible(is_band or is_low)
            getattr(self.ui, f"spinFreq1_{prefix}").setVisible(is_band or is_low)
            getattr(self.ui, f"lblFreq2_{prefix}").setVisible(is_band or is_high)
            getattr(self.ui, f"spinFreq2_{prefix}").setVisible(is_band or is_high)
            getattr(self.ui, f"lblOrder_{prefix}").setText("窗口：" if f_type in {"平滑 (S-G)", "Smooth (S-G)"} else "阶数：")

        def update_dynamic_step(val):
            import math

            if val <= 0:
                return
            power = math.floor(math.log10(val))
            if math.isclose(val, 10**power, rel_tol=1e-5):
                step = 10 ** (power - 1)
            else:
                step = 10**power
            spin_y.setSingleStep(max(step, 0.001))

        chk.toggled.connect(toggle_vis)
        getattr(self.ui, f"comboType_{prefix}").currentTextChanged.connect(combo_change)

        spin_y = getattr(self.ui, f"spinYLim_{prefix}")
        canvas = getattr(self, f"{prefix}_canvas")
        if prefix == "fnirs":
            spin_y.setValue(0.1)
            spin_y.setSingleStep(0.1)
        else:
            spin_y.setValue(100.0)
            spin_y.setSingleStep(10.0)
        spin_y.valueChanged.connect(update_dynamic_step)
        spin_y.valueChanged.connect(canvas.update_ylim)
        getattr(self.ui, f"btnApply_{prefix}").clicked.connect(lambda: self._apply_filter(prefix))

    def _apply_filter(self, prefix):
        is_enable = getattr(self.ui, f"chkEnable_{prefix}").isChecked()
        if not is_enable:
            self._filter_state_cache.pop(prefix, None)
            self.signal_worker_filter.emit(prefix, {})
            return

        f_type_str = getattr(self.ui, f"comboType_{prefix}").currentText()
        params = {
            "low_cutoff": getattr(self.ui, f"spinFreq1_{prefix}").value(),
            "high_cutoff": getattr(self.ui, f"spinFreq2_{prefix}").value(),
            "order": getattr(self.ui, f"spinOrder_{prefix}").value(),
            "window_length": getattr(self.ui, f"spinOrder_{prefix}").value(),
            "polyorder": 3,
        }
        filter_type = FILTER_LABEL_MAP.get(f_type_str, "bandpass")
        payload = {"filter_type": filter_type, "params": params}
        self._filter_state_cache[prefix] = payload
        self.signal_worker_filter.emit(prefix, payload)
        logger.info("%s 滤波已应用到全部通道：type=%s", prefix.upper(), filter_type)

    def _wire_signals(self):
        self.ui.btnStart.clicked.connect(self.start_acquisition)
        self.ui.btnStop.clicked.connect(self.stop_acquisition)
        self.ui.btnRecord.clicked.connect(self.toggle_record)
        self.ui.btnReset.clicked.connect(self.reset_system)
        self.ui.btnComplete.clicked.connect(self.signal_display_finished.emit)
        if hasattr(self.ui, "comboSigType_fnirs"):
            self.ui.comboSigType_fnirs.currentTextChanged.connect(self._apply_sigtype_change)  # type: ignore
        self.ui.btnStart.setEnabled(True)
        self.ui.btnStop.setEnabled(False)
        self.ui.btnRecord.setEnabled(False)

    def _enqueue_stream_batch(self, modality, payload):
        if not self.is_running or not hasattr(self, "processing_worker"):
            return
        self.processing_worker.enqueue_stream(modality, payload)

    def push_new_data(self, fnirs_raw: list, eeg_raw: list, semg_raw: list = []):
        if fnirs_raw and hasattr(self, "fnirs_canvas"):
            self._enqueue_stream_batch("fnirs", fnirs_raw)
        if eeg_raw and hasattr(self, "eeg_canvas"):
            self._enqueue_stream_batch("eeg", eeg_raw)
        if semg_raw and hasattr(self, "semg_canvas"):
            self._enqueue_stream_batch("semg", semg_raw)

    def flush_display_buffers(self):
        if hasattr(self, "processing_worker"):
            self.processing_worker.clear_pending_inputs()
        for canvas_name in ("fnirs_canvas", "eeg_canvas", "semg_canvas"):
            canvas = getattr(self, canvas_name, None)
            if canvas is not None:
                canvas.clear_pending_samples()

    def start_acquisition(self):
        self.flush_display_buffers()
        self.is_running = True
        self.ui.btnStart.setEnabled(False)
        self.ui.btnStop.setEnabled(True)
        self.ui.btnRecord.setEnabled(True)
        self.ui.btnReset.setEnabled(True)
        self.ui.btnComplete.setEnabled(False)
        self.is_recording = False
        self.ui.btnRecord.setText("记录")
        self.ui.btnRecord.setStyleSheet("")
        self.signal_worker_reset.emit()
        self.signal_worker_running.emit(True)
        if hasattr(self, "fnirs_canvas"):
            self.fnirs_canvas.reset()
        if hasattr(self, "eeg_canvas"):
            self.eeg_canvas.reset()
        if hasattr(self, "semg_canvas"):
            self.semg_canvas.reset()
        self._reapply_enabled_filters()
        logger.info("开始实时采集。")
        self.setFocus()
        self.signal_request_start.emit()

    def stop_acquisition(self):
        self.is_running = False
        self.signal_worker_running.emit(False)
        self.flush_display_buffers()
        self.ui.btnStart.setEnabled(True)
        self.ui.btnStop.setEnabled(False)
        self.ui.btnRecord.setEnabled(False)
        self.ui.btnReset.setEnabled(True)
        self.ui.btnComplete.setEnabled(False)
        self.is_recording = False
        self.ui.btnRecord.setText("记录")
        self.ui.btnRecord.setStyleSheet("")
        logger.info("停止实时采集。")
        self.signal_request_stop.emit()

    def toggle_record(self):
        self.is_recording = True
        self.ui.btnRecord.setText("记录中...")
        self.ui.btnRecord.setEnabled(False)
        self.ui.btnRecord.setStyleSheet("background-color: #e74c3c; color: white; border: none; font-weight: bold;")
        self.ui.btnReset.setEnabled(False)
        self.signal_request_record.emit(True)

    def _apply_sigtype_change(self, new_type):
        lbl = getattr(self.ui, "lblYLim_fnirs", None)
        spin = getattr(self.ui, "spinYLim_fnirs", None)
        if "原始" in new_type:
            if lbl:
                lbl.setVisible(False)
            if spin:
                spin.setVisible(False)
        else:
            if lbl:
                lbl.setVisible(True)
            if spin:
                spin.setVisible(True)
                spin.setValue(0.1)
        self.signal_worker_fnirs_mode.emit(new_type)
        self.signal_op_mode_changed.emit(new_type)
        self.reset_system()

    def _init_default_eeg_filter(self):
        chk = getattr(self.ui, "chkEnable_eeg", None)
        combo = getattr(self.ui, "comboType_eeg", None)
        low = getattr(self.ui, "spinFreq1_eeg", None)
        high = getattr(self.ui, "spinFreq2_eeg", None)
        order = getattr(self.ui, "spinOrder_eeg", None)
        if not all((chk, combo, low, high, order)):
            return
        combo.setCurrentText("带通")
        low.setValue(2.0)
        high.setValue(45.0)
        order.setValue(5)
        chk.setChecked(True)
        self._apply_filter("eeg")

    def _reapply_enabled_filters(self):
        for prefix, payload in self._filter_state_cache.items():
            self.signal_worker_filter.emit(prefix, payload)

    def reset_system(self):
        logger.info("已重置显示画布和在线滤波器。")
        self.flush_display_buffers()
        self.signal_worker_reset.emit()
        if hasattr(self, "fnirs_canvas"):
            self.fnirs_canvas.reset()
        if hasattr(self, "eeg_canvas"):
            self.eeg_canvas.reset()
        if hasattr(self, "semg_canvas"):
            self.semg_canvas.reset()
        self._reapply_enabled_filters()

    def keyPressEvent(self, event):  # type: ignore
        if not self.is_running or not self.is_recording:
            return super().keyPressEvent(event)
        key = event.key()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            val = key - Qt.Key.Key_0
            logger.info("收到打标事件：%s", val)
            if hasattr(self, "fnirs_canvas"):
                self.fnirs_canvas.draw_marker(val)
            if hasattr(self, "eeg_canvas"):
                self.eeg_canvas.draw_marker(val)
            if hasattr(self, "semg_canvas"):
                self.semg_canvas.draw_marker(val)
            self.signal_mark_event.emit(val)
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):  # type: ignore
        if hasattr(self.ui, "comboSigType_fnirs") and obj == self.ui.comboSigType_fnirs:  # type: ignore
            if event.type() == QEvent.Type.MouseButtonPress and self.is_recording:
                QMessageBox.warning(self, "已锁定", "记录过程中不允许切换信号类型。")
                return True
        return super().eventFilter(obj, event)

    def shutdown(self):
        self.is_running = False
        self.signal_worker_running.emit(False)
        self.flush_display_buffers()
        for canvas_name in ("fnirs_canvas", "eeg_canvas", "semg_canvas"):
            canvas = getattr(self, canvas_name, None)
            if canvas is not None:
                canvas.stop_rendering()
        if hasattr(self, "processing_thread") and self.processing_thread.isRunning():
            self.processing_thread.quit()
            self.processing_thread.wait(2000)
        self.processing_worker = None
        self.processing_thread = None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    app = QApplication(sys.argv)

    mock_fnirs_chs = ["S1-D1", "S1-D2", "S2-D3", "S3-D4"]
    mock_eeg_chs = ["Cz", "Oz", "Pz", "Fz"]
    manager = DisplayManager(fnirs_channels=mock_fnirs_chs, eeg_channels=mock_eeg_chs, fs_fnirs=10, fs_eeg=500)
    manager.setWindowTitle("NeuroSync Realtime Display")
    manager.resize(1300, 800)
    manager.show()

    def mock_data_pump():
        if not manager.is_running:
            return
        current_t = globals().get("_display_demo_t", 0.0) + 1.0 / 500.0
        globals()["_display_demo_t"] = current_t

        clean_eeg = np.sin(2 * np.pi * 2 * current_t) * 50
        noise_eeg = np.sin(2 * np.pi * 50 * current_t) * 30 + np.random.normal(0, 10)
        eeg_val = clean_eeg + noise_eeg
        eeg_packet = np.tile(np.array([eeg_val, eeg_val * 0.5, eeg_val * 0.8, eeg_val * 0.3], dtype=np.float32), (10, 1))

        fnirs_packet = []
        if int(current_t * 10) != int((current_t - 1.0 / 500.0) * 10):
            fnirs_val = np.sin(2 * np.pi * 0.1 * current_t) * 5 + np.random.normal(0, 2)
            fnirs_packet = [fnirs_val + 2, fnirs_val - 1, fnirs_val + 1, fnirs_val - 2, fnirs_val + 3, fnirs_val - 1.5, fnirs_val + 2.5, fnirs_val - 0.5]
        manager.push_new_data(fnirs_packet, eeg_packet)

    timer = QTimer()
    timer.timeout.connect(mock_data_pump)
    timer.start(10)

    sys.exit(app.exec_())

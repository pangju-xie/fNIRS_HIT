# -*- coding: utf-8 -*-

"""
Signal Processing and Data Visualization Application

This application provides real-time signal processing capabilities with various
filtering options and multi-channel data visualization.

Main application logic and interaction handling - adapted for new UI structure.
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QMessageBox, QFileDialog, QWidget, QStatusBar)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QMutex, QMutexLocker
from PyQt5.QtGui import QKeySequence
import pandas as pd
import json
from datetime import datetime

from ui_display import Ui_DisplayWidget, SensorTypes
from signal_processor import SignalProcessor, create_signal_processor
    
class BasePlotCanvas(FigureCanvas):
    """Base class for plotting canvases with sweep mode"""
    
    def __init__(self, parent, num_channels, channel_labels, frequency = 10, time = 30, width=15, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='white')
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.num_channels = num_channels
        self.channel_labels = channel_labels
        self.frequency = frequency  # Samples per second
        self.time = time  # Total time in seconds
        self.max_points = int(self.time * self.frequency)  # 120s * 10 samples/s
        self.data_index = 0
        self.sweep_position = 0  # Current position in sweep mode
        self.mutex = QMutex()  # Thread-safe mutex
        
        # Performance optimization
        self.update_counter = 0
        self.skip_frames = 1  # Update display every N frames to reduce lag
        
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor('white')
        self.axes.set_xlabel('Time (s)')
        
        self.time_data = np.arange(self.max_points) / self.frequency  # Fixed time axis (0-120s)
        self.channel_data = {}
        self.channel_lines = {}
        self.sweep_line = None  # Vertical line showing current position
        
    def clear_plot(self):
        """Clear all plotted data"""
        locker = QMutexLocker(self.mutex)
        for i in range(self.num_channels):
            self.channel_data[i] = np.full(self.max_points, np.nan)  # Use NaN instead of zeros
            self.channel_lines[i].set_data(self.time_data, self.channel_data[i])
        self.data_index = 0
        self.sweep_position = 0
        if self.sweep_line:
            self.sweep_line.set_xdata([0, 0])
        self.draw_idle()


class FNIRSPlotCanvas(BasePlotCanvas):
    """Canvas for fNIRS signals with HbO/Hb pairs - sweep mode"""
    
    def __init__(self, parent, channels, frequency = 10, time = 30, offset = 10.0, width=15, height=8, dpi=100):
        self.channel_offset = offset  # Double the offset for better spacing
        self.physical_channels = channels
        num_channels = len(channels) * 2  # HbO + Hb for each channel
        
        # Create labels for HbO and Hb
        labels = []
        for ch in channels:
            labels.append(f"{ch}_Hb")
            labels.append(f"{ch}_HbO")
        
        super().__init__(parent, num_channels, labels, frequency, time, width, height, dpi)
        
        self.colors = ['blue', 'red']  # HbO: red, Hb: blue
        self.initialize_channels()
        
    def initialize_channels(self):
        """Initialize channel data and plot lines"""
        self.axes.set_xlim((0, self.time))  # 0-120 seconds
        # Add extra space at the top for better visibility (double offset)
        y_min = -self.channel_offset
        y_max = (len(self.physical_channels) - 1) * self.channel_offset * 2 + self.channel_offset
        self.axes.set_ylim((y_min, y_max)) # type: ignore
        self.axes.set_yticks(
            np.arange(0, len(self.physical_channels) * self.channel_offset * 2, self.channel_offset * 2),
            self.physical_channels
        )
        
        for i, label in enumerate(self.channel_labels):
            self.channel_data[i] = np.full(self.max_points, np.nan)  # Initialize with NaN
            color = self.colors[i % 2]  # Alternate between HbO and Hb colors
            line, = self.axes.plot(self.time_data, self.channel_data[i], 
                                 color=color, linewidth=1.5, label=label)
            self.channel_lines[i] = line
        
        # Add sweep line
        self.sweep_line = self.axes.axvline(x=0, color='green', linestyle='--', linewidth=1, alpha=0.7)
        
        self.fig.tight_layout()
        
    def modify_ylim(self, value):
        self.axes.set_xlim((0, self.time))  # 0-120 seconds
        # Add extra space at the top for better visibility (double offset)
        self.channel_offset = value
        y_min = -self.channel_offset
        y_max = (len(self.physical_channels) - 1) * self.channel_offset * 2 + self.channel_offset
        self.axes.set_ylim((y_min, y_max)) # type: ignore
        self.axes.set_yticks(
            np.arange(0, len(self.physical_channels) * self.channel_offset * 2, self.channel_offset * 2),
            self.physical_channels
        )
        
    def update_data(self, new_data):
        """Update plot with new data point - optimized sweep mode"""
        if not self.mutex.tryLock():
            return  # Skip this update if locked
        
        try:
            # Frame skipping for performance
            self.update_counter += 1
            should_draw = (self.update_counter % self.skip_frames == 0)
            
            # Update sweep position
            current_time = self.time_data[self.sweep_position]
            
            # Update data at current position
            for i in range(self.num_channels):
                hb_hbo = i%2
                channel_group = i // 2
                offset_value = new_data[hb_hbo, channel_group] + channel_group * self.channel_offset * 2
                self.channel_data[i][self.sweep_position] = offset_value
            
            # Only update line data if we're going to draw
            if should_draw:
                for i in range(self.num_channels):
                    self.channel_lines[i].set_data(self.time_data, self.channel_data[i])
                
                # Update sweep line position
                self.sweep_line.set_xdata([current_time, current_time])
            
            # Clear a small region ahead of the sweep line (creates the "erasing" effect)
            clear_width = self.frequency  # Adjusted for longer time scale
            for i in range(clear_width):
                clear_pos = (self.sweep_position + i + 1) % self.max_points
                for j in range(self.num_channels):
                    self.channel_data[j][clear_pos] = np.nan
            
            # Move to next position
            self.sweep_position = (self.sweep_position + 1) % self.max_points
            self.data_index += 1
            
            # Only redraw when needed
            if should_draw:
                self.draw_idle()
        finally:
            self.mutex.unlock()
    
    def clear_plot(self):
        """Clear all plotted data"""
        locker = QMutexLocker(self.mutex)
        for i in range(self.num_channels):
            self.channel_data[i] = np.full(self.max_points, np.nan)  # Use NaN instead of zeros
            self.channel_lines[i].set_data(self.time_data, self.channel_data[i])
        self.data_index = 0
        self.sweep_position = 0
        if self.sweep_line:
            self.sweep_line.set_xdata([0, 0])
        self.draw_idle()


class EEGPlotCanvas(BasePlotCanvas):
    """Canvas for EEG signals - sweep mode"""
    
    def __init__(self, parent, channels, frequency = 1000, time = 10, width=15, height=8, dpi=100):
        self.channel_offset = 100.0  # Double the offset for better spacing
        labels = [f"EEG-{ch}" for ch in channels]
        
        super().__init__(parent, len(channels), labels, frequency, time, width, height, dpi)
        self.initialize_channels()
        
    def initialize_channels(self):
        """Initialize channel data and plot lines"""
        self.axes.set_xlim((0, self.time))  # 0-120 seconds
        # Add extra space at the top for better visibility (double offset)
        y_min = -self.channel_offset
        y_max = (self.num_channels - 1) * self.channel_offset + self.channel_offset
        self.axes.set_ylim((y_min, y_max)) # type: ignore
        self.axes.set_yticks(
            np.arange(0, self.num_channels * self.channel_offset, self.channel_offset),
            self.channel_labels
        )
        
        for i in range(self.num_channels):
            self.channel_data[i] = np.full(self.max_points, np.nan)  # Initialize with NaN
            line, = self.axes.plot(self.time_data, self.channel_data[i], 
                                 color='black', linewidth=1.0, label=self.channel_labels[i])
            self.channel_lines[i] = line
        
        # Add sweep line
        self.sweep_line = self.axes.axvline(x=0, color='green', linestyle='--', linewidth=1, alpha=0.7)
        
        self.fig.tight_layout()
        
    def update_data(self, new_data):
        """Update plot with new data point - optimized sweep mode"""
        if not self.mutex.tryLock():
            return  # Skip this update if locked
        
        try:
            # Frame skipping for performance
            self.update_counter += 1
            should_draw = (self.update_counter % self.skip_frames == 0)
            
            # Update sweep position
            current_time = self.time_data[self.sweep_position]
            
            # Update data at current position
            for i, value in enumerate(new_data):
                if i < self.num_channels:
                    offset_value = value + i * self.channel_offset
                    self.channel_data[i][self.sweep_position] = offset_value
            
            # Only update line data if we're going to draw
            if should_draw:
                for i in range(self.num_channels):
                    self.channel_lines[i].set_data(self.time_data, self.channel_data[i])
                
                # Update sweep line position
                self.sweep_line.set_xdata([current_time, current_time])
            
            # Clear a small region ahead of the sweep line
            clear_width = 200  # Adjusted for longer time scale
            for i in range(clear_width):
                clear_pos = (self.sweep_position + i + 1) % self.max_points
                for j in range(self.num_channels):
                    self.channel_data[j][clear_pos] = np.nan
            
            # Move to next position
            self.sweep_position = (self.sweep_position + 1) % self.max_points
            self.data_index += 1
            
            # Only redraw when needed
            if should_draw:
                self.draw_idle()
        finally:
            self.mutex.unlock()


class DisplayWidget(QWidget):
    """Main display widget - handles interaction logic"""
    
    statusMessage = pyqtSignal(str)
    OnSampleStart = pyqtSignal(bool)
    OnSamplePatch = pyqtSignal(int, list)  
    
    def __init__(self, sensor_type=SensorTypes.FNIRS, sensor_info = {}):
        super().__init__()
        self.sensor_type = sensor_type
        self.sensor_info = sensor_info
        self.channels = {}
        self.signal_processor = {}
        self.sample_rate = {}
        self.plot_canvas = {}
        
        self.startflag = 0
        self.ui = Ui_DisplayWidget(sensor_type)
        self.ui.setupUi(self)

        self.ui.signalTypeCombo.currentTextChanged.connect(self.on_signal_type_changed)
        self.ui.fnirs_spinbox.valueChanged.connect(self.on_ylim_changed)
        # CRITICAL: Set the main layout to the widget
        self.setLayout(self.ui.mainLayout)
        
        # Initialize signal processor
        self.active_signals = SensorTypes.get_active_signals(sensor_type)
        
        layout = QVBoxLayout(self.ui.plotWidget)
        for types in self.active_signals:
            self.channels[types] = sensor_info[types].get_channels()
            self.sample_rate[types] = sensor_info[types].getSampleRate()
            self.signal_processor[types] = create_signal_processor(sample_rate = self.sample_rate[types],
                                                          num_channels = len(self.channels[types]))
            if types == 'fnirs':
                offset = self.ui.fnirs_spinbox.value()
                self.plot_canvas[types] = FNIRSPlotCanvas(self.ui.plotWidget, self.channels[types], frequency=self.sample_rate[types], time=30, offset=offset, width=12, height=6)
            elif types == 'eeg':
                self.plot_canvas[types] = EEGPlotCanvas(self.ui.plotWidget, self.channels[types], frequency=self.sample_rate[types], time=10, width=12, height=6)
            layout.addWidget(self.plot_canvas[types])
        
        # Initialize components
        self.is_recording = False
        
        # Connect signals
        self.connect_signals()
        
        # Initialize UI state
        self.initialize_ui_state()
        
        
    def connect_signals(self):
        """Connect UI signals to their respective slots"""
        self.ui.startButton.clicked.connect(self.start_acquisition)
        self.ui.stopButton.clicked.connect(self.stop_acquisition)
        self.ui.resetButton.clicked.connect(self.reset_system)
        self.ui.recordButton.clicked.connect(self.record_data)
        # self.ui.saveButton.clicked.connect(self.save_data)
        self.ui.applyButton.clicked.connect(self.apply_filter_settings)
        
        # Connect checkbox changes
        for signal_key, checkbox in self.ui.filter_checkboxes.items():
            checkbox.toggled.connect(lambda checked, sk=signal_key: self.on_filter_enabled_changed(sk, checked))
        
    def initialize_ui_state(self):
        """Set initial UI state"""
        self.ui.set_control_states(
            start_enabled=True,
            stop_enabled=False,
            reset_enabled=False,
            record_enabled=False
        )
        
    def emit_status_message(self, message):
        """Emit status message"""
        self.statusMessage.emit(message)
        
    def on_signal_type_changed(self):
        for types in self.active_signals:
            if types in self.plot_canvas:
                self.plot_canvas[types].clear_plot()
                
    def on_ylim_changed(self):
        """Handle Y-axis limit change for fNIRS plot"""
        if 'fnirs' in self.plot_canvas:
            value = self.ui.fnirs_spinbox.value()
            self.plot_canvas['fnirs'].modify_ylim(value)
        
        
    def on_filter_enabled_changed(self, signal_key, enabled):
        """Handle filter enable/disable - with QMutex protection"""
        # Lock the plot canvas during filter changes
        if hasattr(self, 'plot_canvas') and hasattr(self.plot_canvas, 'mutex'):
            locker = QMutexLocker(self.plot_canvas.mutex)
            
            if enabled:
                self.setup_online_filter(signal_key)
                self.emit_status_message(f"{signal_key.upper()} filter enabled")
            else:
                self.clear_online_filter(signal_key)
                self.emit_status_message(f"{signal_key.upper()} filter disabled")
        else:
            if enabled:
                self.setup_online_filter(signal_key)
                self.emit_status_message(f"{signal_key.upper()} filter enabled")
            else:
                self.clear_online_filter(signal_key)
                self.emit_status_message(f"{signal_key.upper()} filter disabled")
    
    def apply_filter_settings(self):
        """Apply current filter settings to all enabled filters - with QMutex protection"""
        active_filters = self.ui.get_active_filter_params()
        
        if not active_filters:
            QMessageBox.information(self, "No Filters", "No filters are currently enabled.")
            return
        
        # Lock the plot canvas during filter configuration
        if hasattr(self, 'plot_canvas') and hasattr(self.plot_canvas, 'mutex'):
            locker = QMutexLocker(self.plot_canvas.mutex)
            
            for signal_key, filter_config in active_filters.items():
                self.setup_online_filter(signal_key)
            
            filter_list = ", ".join([f"{v['signal_label']}" for v in active_filters.values()])
            self.emit_status_message(f"Filter settings applied: {filter_list}")
            QMessageBox.information(self, "Filters Applied", 
                                  f"Real-time filters configured for:\n{filter_list}")
        else:
            for signal_key, filter_config in active_filters.items():
                self.setup_online_filter(signal_key)
            
            filter_list = ", ".join([f"{v['signal_label']}" for v in active_filters.values()])
            self.emit_status_message(f"Filter settings applied: {filter_list}")
            QMessageBox.information(self, "Filters Applied", 
                                  f"Real-time filters configured for:\n{filter_list}")
    
    def setup_online_filter(self, signal_key):
        """Setup online filter for a specific signal type"""
        filter_params = self.ui.get_active_filter_params_by_signal(signal_key)
        
        if filter_params is None:
            return
        
        filter_type = filter_params['filter_type']
        params = filter_params['params']
        
        # Map Chinese filter names to processor types
        filter_type_map = {
            '低通滤波': 'lowpass',
            '高通滤波': 'highpass',
            '带通滤波': 'bandpass',
            'S-G滤波': 'sg',
            '平滑滤波': 'smooth'
        }
        
        processor_filter_type = filter_type_map.get(filter_type)
        
        if processor_filter_type:
            # Setup filter for appropriate channel range
            for ch in self.channels[signal_key]:
                try:
                    self.signal_processor[signal_key].setup_online_filter(ch, processor_filter_type, **params)
                except Exception as e:
                    self.emit_status_message(f"Filter setup error: {str(e)}")
    
    def clear_online_filter(self, signal_key):
        """Clear online filter for a specific signal type"""
        for ch in self.channels[signal_key]:
            self.signal_processor[signal_key].reset_online_filters(ch) # type: ignore

    def set_start_control_states(self):
        """Set UI states when starting acquisition"""
        self.ui.set_control_states(
            start_enabled=False,
            stop_enabled=True,
            reset_enabled=True,
            record_enabled=True
        )    
        
    def set_stop_control_states(self):
        """Set UI states when stopping acquisition"""
        self.ui.set_control_states(
            start_enabled=True,
            stop_enabled=False,
            reset_enabled=False,
            record_enabled=False
        )
        
    def start_acquisition(self):
        """Start data acquisition"""
        self.startflag = 1
        self.OnSampleStart.emit(True)
        for types in self.active_signals:
            self.plot_canvas[types].clear_plot()
        self.emit_status_message("Acquiring data...")
        
    def stop_acquisition(self):
        """Stop data acquisition"""
        self.startflag = 0
        self.OnSampleStart.emit(False)
        if self.is_recording:
            self.is_recording = False
            for types in self.active_signals:
                if types == 'fnirs' and self.sensor_info[types].get_packet.shape[0] > 0:
                    self.OnSamplePatch.emit(SensorTypes.FNIRS, self.sensor_info[types].get_packet)
        
        self.emit_status_message("Data acquisition stopped")
        
    def reset_system(self):
        """Reset the entire system"""
        # Reset state
        self.is_recording = False
        
        for types in self.active_signals:
            if 'fnirs' == types:
                self.sensor_info[types].CleanData()
        
        # Clear plot with mutex protection
        if hasattr(self, 'plot_canvas'):
            for canvas in self.plot_canvas.values():
                canvas.clear_plot()
        
        # Reset filters
        for types in self.active_signals:
            self.signal_processor[types].reset_online_filters()
        
        # Update UI
        self.ui.recordButton.setText("记录")
        self.ui.set_control_states(
            start_enabled=False,
            stop_enabled= True,
            reset_enabled=True,
            record_enabled=True
        )
        self.emit_status_message("System reset")
        
    def record_data(self):
        """Toggle data recording"""
        self.is_recording  = True
        if self.is_recording:
            self.ui.recordButton.setText("开始记录")
            self.emit_status_message("Recording data...")
            if 'fnirs' in self.active_signals:
                self.sensor_info['fnirs'].StartRecord()
            self.ui.set_control_states(
            start_enabled=False,
            stop_enabled= True,
            reset_enabled=False,
            record_enabled=False
        )
        else:
            self.ui.recordButton.setText("记录")
    
    def on_new_data(self, data):
        """Handle new data from generator - with error handling"""
        # try:
            # Apply real-time filtering
        processed_data = data.copy()
        for types in self.active_signals:
            for ch in range(len(processed_data)):
                processed_data[ch] = self.signal_processor[types].process_sample_online(ch, processed_data[ch])
        
        # Update plot (will skip if mutex is locked)
            if hasattr(self, 'plot_canvas'):
                self.plot_canvas[types].update_data(processed_data)
        # except Exception as e:
        #     print(f"Error in on_new_data: {e}")
        #     # Don't crash the application on data processing errors
    
    def save_data(self):
        """Save recorded data to file"""
        self.is_recording = False
        
        for types in self.active_signals:
            if types == 'fnirs':
                self.sensor_info[types].save_data(data_type = 'csv')

    
    def closeEvent(self, event): # type: ignore
        """Handle widget close event - ensure clean shutdown"""
        event.accept()  # Accept anyway to prevent hanging


class MainApplication(QMainWindow):
    """Main application window"""
    
    def __init__(self, sensor_type=SensorTypes.FNIRS):
        super().__init__()
        self.setWindowTitle("Signal Processing and Data Visualization")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 850)
        
        # Create central widget
        self.display_widget = DisplayWidget(sensor_type)
        self.setCentralWidget(self.display_widget)
        
        # Connect status message
        self.display_widget.statusMessage.connect(self.update_status)
        
        # Setup status bar
        self.setup_status_bar()
        self.setup_shortcuts()
        
    def setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.display_widget.ui.startButton.setShortcut(QKeySequence("Ctrl+R"))
        self.display_widget.ui.stopButton.setShortcut(QKeySequence("Ctrl+T"))
        self.display_widget.ui.resetButton.setShortcut(QKeySequence("Ctrl+Shift+R"))
        
    def update_status(self, message):
        """Update status bar message"""
        self.status_bar.showMessage(message)
    
    def closeEvent(self, event): # type: ignore
        """Handle application close event - ensure clean shutdown"""
        try:
            event.accept()
        except Exception as e:
            print(f"Error during application close: {e}")
            event.accept()  # Accept anyway to prevent hanging


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Signal Processing and Data Visualization")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Signal Processing Lab")
    
    try:
        # You can change sensor type here: FNIRS, EEG, SEMG, EEG_SEMG_FNIRS, etc.
        main_window = MainApplication(sensor_type=SensorTypes.FNIRS)
        main_window.show()
        
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
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


class DataGenerator(QThread):
    """Simulates real-time data acquisition"""
    
    dataReady = pyqtSignal(np.ndarray)
    
    def __init__(self, sensor_type, sample_rate=100):
        super().__init__()
        
        self.sensor_type = sensor_type
        self.sample_rate = sample_rate
        self.running = False
        self.time_counter = 0
        
        # Determine number of channels based on sensor type
        active_signals = SensorTypes.get_active_signals(sensor_type)
        self.num_channels = self._get_channel_count(active_signals)
        
    def _get_channel_count(self, active_signals):
        """Calculate total channel count based on active signals"""
        count = 0
        if 'eeg' in active_signals:
            count += 8  # 8 EEG channels
        if 'semg' in active_signals:
            count += 4  # 4 sEMG channels
        if 'fnirs' in active_signals:
            count += 14  # 7 fNIRS channels × 2 (HbO + Hb)
        return count
        
    def run(self):
        """Main thread execution"""
        while self.running:
            if self.running:
                self.generate_data()
            self.msleep(1000 // self.sample_rate)
            
    def generate_data(self):
        """Generate synthetic multi-channel data"""
        if not self.running:
            return
            
        t = self.time_counter / self.sample_rate
        data = np.zeros(self.num_channels)
        
        for i in range(self.num_channels):
            freq1 = 0.1 + i * 0.05
            freq2 = 1.0 + i * 0.1
            
            signal_component = (np.sin(2 * np.pi * freq1 * t) + 
                              0.3 * np.sin(2 * np.pi * freq2 * t))
            noise = np.random.normal(0, 0.1)
            data[i] = signal_component + noise
            
        self.dataReady.emit(data)
        self.time_counter += 1
    
    def start_acquisition(self):
        """Start data acquisition"""
        self.running = True
        if not self.isRunning():
            self.start()
    
    def stop_acquisition(self):
        """Stop data acquisition"""
        self.running = False
        if self.isRunning():
            self.quit()
            self.wait()


class BasePlotCanvas(FigureCanvas):
    """Base class for plotting canvases with sweep mode"""
    
    def __init__(self, parent, num_channels, channel_labels, width=15, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='white')
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.num_channels = num_channels
        self.channel_labels = channel_labels
        self.max_points = 12000  # 120s * 100 samples/s
        self.data_index = 0
        self.sweep_position = 0  # Current position in sweep mode
        self.mutex = QMutex()  # Thread-safe mutex
        
        # Performance optimization
        self.update_counter = 0
        self.skip_frames = 2  # Update display every N frames to reduce lag
        
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor('white')
        self.axes.set_xlabel('Time (s)')
        
        self.time_data = np.arange(self.max_points) / 100.0  # Fixed time axis (0-120s)
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
    
    def __init__(self, parent, channels, width=15, height=8, dpi=100):
        self.channel_offset = 20.0  # Double the offset for better spacing
        self.physical_channels = channels
        num_channels = len(channels) * 2  # HbO + Hb for each channel
        
        # Create labels for HbO and Hb
        labels = []
        for ch in channels:
            labels.append(f"{ch}_HbO")
            labels.append(f"{ch}_Hb")
        
        super().__init__(parent, num_channels, labels, width, height, dpi)
        
        self.colors = ['red', 'blue']  # HbO: red, Hb: blue
        self.initialize_channels()
        
    def initialize_channels(self):
        """Initialize channel data and plot lines"""
        self.axes.set_xlim((0, 120))  # 0-120 seconds
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
                    channel_group = i // 2
                    offset_value = value + channel_group * self.channel_offset * 2
                    self.channel_data[i][self.sweep_position] = offset_value
            
            # Only update line data if we're going to draw
            if should_draw:
                for i in range(self.num_channels):
                    self.channel_lines[i].set_data(self.time_data, self.channel_data[i])
                
                # Update sweep line position
                self.sweep_line.set_xdata([current_time, current_time])
            
            # Clear a small region ahead of the sweep line (creates the "erasing" effect)
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


class EEGPlotCanvas(BasePlotCanvas):
    """Canvas for EEG signals - sweep mode"""
    
    def __init__(self, parent, channels, width=15, height=8, dpi=100):
        self.channel_offset = 100.0  # Double the offset for better spacing
        labels = [f"EEG-{ch}" for ch in channels]
        
        super().__init__(parent, len(channels), labels, width, height, dpi)
        self.initialize_channels()
        
    def initialize_channels(self):
        """Initialize channel data and plot lines"""
        self.axes.set_xlim((0, 120))  # 0-120 seconds
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
    
    def __init__(self, sensor_type=SensorTypes.FNIRS):
        super().__init__()
        self.sensor_type = sensor_type
        self.ui = Ui_DisplayWidget(sensor_type)
        self.ui.setupUi(self)
        
        # CRITICAL: Set the main layout to the widget
        self.setLayout(self.ui.mainLayout)
        
        # Initialize signal processor
        active_signals = SensorTypes.get_active_signals(sensor_type)
        num_channels = self._get_total_channels(active_signals)
        self.signal_processor = create_signal_processor(sample_rate=100, num_channels=num_channels)
        
        # Initialize components
        self.data_generator = DataGenerator(sensor_type)
        self.recorded_data = []
        self.is_recording = False
        
        # Setup plot canvas
        self.setup_plot_canvas()
        
        # Connect signals
        self.connect_signals()
        
        # Initialize UI state
        self.initialize_ui_state()
        
    def _get_total_channels(self, active_signals):
        """Calculate total number of channels"""
        count = 0
        if 'eeg' in active_signals:
            count += 8
        if 'semg' in active_signals:
            count += 4
        if 'fnirs' in active_signals:
            count += 14
        return count
        
    def setup_plot_canvas(self):
        """Initialize the plotting canvas based on sensor type"""
        active_signals = SensorTypes.get_active_signals(self.sensor_type)
        
        if 'fnirs' in active_signals:
            channels = ['S1-D1', 'S1-D2', 'S2-D1', 'S2-D2', 'S3-D1', 'S3-D3', 'S3-D4']
            self.plot_canvas = FNIRSPlotCanvas(self.ui.plotWidget, channels, width=12, height=6)
        elif 'eeg' in active_signals:
            channels = [f"Ch{i+1}" for i in range(8)]
            self.plot_canvas = EEGPlotCanvas(self.ui.plotWidget, channels, width=12, height=6)
        else:
            # Default fallback
            channels = [f"Ch{i+1}" for i in range(4)]
            self.plot_canvas = EEGPlotCanvas(self.ui.plotWidget, channels, width=12, height=6)
        
        layout = QVBoxLayout(self.ui.plotWidget)
        layout.addWidget(self.plot_canvas)
        
        # Connect data generator
        self.data_generator.dataReady.connect(self.on_new_data)
        
    def connect_signals(self):
        """Connect UI signals to their respective slots"""
        self.ui.startButton.clicked.connect(self.start_acquisition)
        self.ui.stopButton.clicked.connect(self.stop_acquisition)
        self.ui.resetButton.clicked.connect(self.reset_system)
        self.ui.recordButton.clicked.connect(self.toggle_recording)
        self.ui.saveButton.clicked.connect(self.save_data)
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
            record_enabled=False,
            save_enabled=False
        )
        
    def emit_status_message(self, message):
        """Emit status message"""
        self.statusMessage.emit(message)
        
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
            channel_range = self._get_channel_range(signal_key)
            for ch in channel_range:
                try:
                    self.signal_processor.setup_online_filter(ch, processor_filter_type, **params)
                except Exception as e:
                    self.emit_status_message(f"Filter setup error: {str(e)}")
    
    def clear_online_filter(self, signal_key):
        """Clear online filter for a specific signal type"""
        channel_range = self._get_channel_range(signal_key)
        for ch in channel_range:
            self.signal_processor.clear_online_filter(ch) # type: ignore
    
    def _get_channel_range(self, signal_key):
        """Get channel index range for a signal type"""
        active_signals = SensorTypes.get_active_signals(self.sensor_type)
        
        start_idx = 0
        if signal_key == 'eeg' and 'eeg' in active_signals:
            return range(start_idx, start_idx + 8)
        
        if 'eeg' in active_signals:
            start_idx += 8
            
        if signal_key == 'semg' and 'semg' in active_signals:
            return range(start_idx, start_idx + 4)
        
        if 'semg' in active_signals:
            start_idx += 4
            
        if signal_key == 'fnirs' and 'fnirs' in active_signals:
            return range(start_idx, start_idx + 14)
        
        return range(0)
        
    def start_acquisition(self):
        """Start data acquisition"""
        self.data_generator.start_acquisition()
        self.ui.set_control_states(
            start_enabled=False,
            stop_enabled=True,
            reset_enabled=True,
            record_enabled=True,
            save_enabled=False
        )
        self.emit_status_message("Acquiring data...")
        
    def stop_acquisition(self):
        """Stop data acquisition"""
        self.data_generator.stop_acquisition()
        
        # Wait for the thread to properly finish
        if self.data_generator.isRunning():
            self.data_generator.wait(1000)  # Wait up to 1 second
        
        self.ui.set_control_states(
            start_enabled=True,
            stop_enabled=False,
            reset_enabled=False,
            record_enabled=False,
            save_enabled=True if self.recorded_data else False
        )
        self.emit_status_message("Data acquisition stopped")
        
    def reset_system(self):
        """Reset the entire system"""
        # Stop data generator first
        if self.data_generator.running:
            self.data_generator.stop_acquisition()
            if self.data_generator.isRunning():
                self.data_generator.wait(1000)
        
        # Reset state
        self.is_recording = False
        self.recorded_data.clear()
        
        # Clear plot with mutex protection
        if hasattr(self, 'plot_canvas'):
            self.plot_canvas.clear_plot()
        
        # Reset filters
        self.signal_processor.reset_online_filters()
        
        # Update UI
        self.ui.recordButton.setText("记录")
        self.ui.set_control_states(
            start_enabled=True,
            stop_enabled=False,
            reset_enabled=False,
            record_enabled=False,
            save_enabled=False
        )
        self.emit_status_message("System reset")
        
    def toggle_recording(self):
        """Toggle data recording"""
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.ui.recordButton.setText("停止记录")
            self.emit_status_message("Recording data...")
        else:
            self.ui.recordButton.setText("记录")
            self.emit_status_message(f"Recording stopped. {len(self.recorded_data)} samples recorded")
    
    def on_new_data(self, data):
        """Handle new data from generator - with error handling"""
        try:
            # Apply real-time filtering
            processed_data = data.copy()
            for ch in range(len(processed_data)):
                processed_data[ch] = self.signal_processor.process_sample_online(ch, processed_data[ch])
            
            # Record data if recording is enabled
            if self.is_recording:
                self.recorded_data.append(processed_data.copy())
            
            # Update plot (will skip if mutex is locked)
            if hasattr(self, 'plot_canvas'):
                self.plot_canvas.update_data(processed_data)
        except Exception as e:
            print(f"Error in on_new_data: {e}")
            # Don't crash the application on data processing errors
    
    def save_data(self):
        """Save recorded data to file"""
        if not self.recorded_data:
            QMessageBox.warning(self, "Warning", "No data to save.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Data", 
            f"signal_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;JSON Files (*.json)"
        )
        
        if filename:
            try:
                data_to_save = np.array(self.recorded_data)
                
                if filename.endswith('.json'):
                    save_dict = {
                        'data': data_to_save.tolist(),
                        'metadata': {
                            'timestamp': datetime.now().isoformat(),
                            'sample_rate': self.signal_processor.sample_rate,
                            'sensor_type': self.sensor_type,
                            'num_channels': data_to_save.shape[1] if data_to_save.ndim > 1 else 1,
                            'signal_type': self.ui.get_signal_type(),
                            'num_samples': len(data_to_save),
                            'active_filters': self.ui.get_active_filter_params()
                        }
                    }
                    with open(filename, 'w') as f:
                        json.dump(save_dict, f, indent=2)
                else:
                    if data_to_save.ndim == 1:
                        data_to_save = data_to_save.reshape(-1, 1)
                    df = pd.DataFrame(data_to_save, 
                                    columns=[f'Channel_{i+1}' for i in range(data_to_save.shape[1])])
                    df['Time'] = np.arange(len(df)) / self.signal_processor.sample_rate
                    df.to_csv(filename, index=False)
                
                QMessageBox.information(self, "Success", f"Data saved to {filename}")
                self.emit_status_message(f"Data saved: {len(data_to_save)} samples")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save data: {str(e)}")
    
    def closeEvent(self, event): # type: ignore
        """Handle widget close event - ensure clean shutdown"""
        try:
            if hasattr(self, 'data_generator') and self.data_generator.running:
                self.data_generator.stop_acquisition()
                if self.data_generator.isRunning():
                    self.data_generator.wait(2000)  # Wait up to 2 seconds for thread to finish
            event.accept()
        except Exception as e:
            print(f"Error during close: {e}")
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
            if hasattr(self.display_widget, 'data_generator'):
                if self.display_widget.data_generator.running:
                    self.display_widget.data_generator.stop_acquisition()
                    if self.display_widget.data_generator.isRunning():
                        self.display_widget.data_generator.wait(2000)
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
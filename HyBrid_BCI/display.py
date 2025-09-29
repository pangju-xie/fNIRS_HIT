# -*- coding: utf-8 -*-

"""
Signal Processing and Data Visualization Application

This application provides real-time signal processing capabilities with various
filtering options and multi-channel data visualization with uniform offsets.

Main application logic and interaction handling.
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QMessageBox, QFileDialog, QWidget, QStatusBar,
                             QMenu, QAction, QMenuBar, QCheckBox, QHBoxLayout,
                             QLabel, QComboBox)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QKeySequence
import pandas as pd
import json
from datetime import datetime

from ui_display import Ui_DisplayWidget
from signal_processor import SignalProcessor, create_signal_processor


class DataGenerator(QThread):
    """Simulates real-time data acquisition - separated from UI logic"""
    
    dataReady = pyqtSignal(np.ndarray)
    
    def __init__(self, num_channels=7, sample_rate=100):
        super().__init__()
        
        self.num_channels = num_channels
        self.sample_rate = sample_rate
        self.running = False
        self.time_counter = 0
        
    def run(self):
        timer = QTimer()
        timer.timeout.connect(self.generate_data)
        timer.start(1000 // self.sample_rate)  # 100 Hz
        super().run()

    def generate_data(self):
        """Generate synthetic multi-channel data"""
        if not self.running:
            return
            
        # Generate synthetic multi-channel data
        t = self.time_counter / self.sample_rate
        data = np.zeros(self.num_channels*2)
        
        for i in range(self.num_channels*2):
            # Each channel has different frequency components and noise
            freq1 = 0.1 + i * 0.05  # Different base frequencies
            freq2 = 1.0 + i * 0.1   # Higher frequency components
            
            # Simulate physiological-like signals
            signal_component = (np.sin(2 * np.pi * freq1 * t) + 
                              0.3 * np.sin(2 * np.pi * freq2 * t))
            
            # Add some noise
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


class PlotCanvas(FigureCanvas):
    """Custom matplotlib canvas for real-time plotting - separated from UI logic"""
    
    def __init__(self, parent, channels, width=15, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='white')
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.channel_offset = 10.0
        self.channels = channels
        self.num_channels = len(channels)
        
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor('white')
        self.axes.set_xlabel('Time')
        self.axes.set_ylabel('Amplitude')
        self.axes.set_xlim((0,100))
        self.axes.set_ylim((-self.channel_offset, (self.num_channels*2-1)*self.channel_offset)) # type: ignore
        self.axes.set_yticks(np.arange(0, self.num_channels*2*self.channel_offset, 2*self.channel_offset), self.channels) # type: ignore
        
        # Data storage
        self.max_points = 1000
        self.time_data = np.zeros(self.max_points)
        self.channel_data = {}
        self.channel_lines = {}
        self.colors = ['blue','red']
        
        # Initialize channels
        self.initialize_channels()
        
        self.data_index = 0
        
    def initialize_channels(self):
        """Initialize channel data and plot lines"""
        for i in range(self.num_channels):
            self.channel_data[2*i] = np.zeros(self.max_points)
            line1, = self.axes.plot(self.time_data, self.channel_data[i], 
                                 color=self.colors[0], linewidth=1.5, 
                                 label=f'Channel {self.channels[i]}_Hb')
            self.channel_lines[2*i] = line1
            
            self.channel_data[2*i+1] = np.zeros(self.max_points)
            line2, = self.axes.plot(self.time_data, self.channel_data[i], 
                                 color=self.colors[1], linewidth=1.5, 
                                 label=f'Channel {self.channels[i]}_HbO')
            self.channel_lines[2*i+1] = line2
            
        # self.axes.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        self.fig.tight_layout()
        
    def update_data(self, new_data):
        """Update plot with new data point"""
        current_time = self.data_index / 100.0  # Assuming 100 Hz
        
        # Shift data arrays
        self.time_data[:-1] = self.time_data[1:]
        self.time_data[-1] = current_time
        
        for i, value in enumerate(new_data):
            if i < self.num_channels*2:
                baise = i//2
                # Apply channel offset
                offset_value = value + baise * self.channel_offset*2
                self.channel_data[i][:-1] = self.channel_data[i][1:]
                self.channel_data[i][-1] = offset_value
                self.channel_lines[i].set_data(self.time_data, self.channel_data[i])
        
        # Update axis limits
        if self.data_index > self.max_points:
            self.axes.set_xlim(current_time - self.max_points/100.0, current_time)
        else:
            self.axes.set_xlim(0, max(10, current_time))
            
        # Auto-scale y-axis
        all_data = np.concatenate([self.channel_data[i] for i in range(self.num_channels*2)])
        valid_data = all_data[all_data != 0]
        if len(valid_data) > 0:
            margin = 0.1 * (np.max(valid_data) - np.min(valid_data))
            self.axes.set_ylim(np.min(valid_data) - margin, np.max(valid_data) + margin)
        
        self.data_index += 1
        self.draw_idle()
    
    def clear_plot(self):
        """Clear all plotted data"""
        self.time_data = np.zeros(self.max_points)
        for i in range(self.num_channels):
            self.channel_data[i] = np.zeros(self.max_points)
            self.channel_lines[i].set_data(self.time_data, self.channel_data[i])
        self.data_index = 0
        self.axes.set_xlim(0, 10)
        self.axes.set_ylim(-1, 1)
        self.draw_idle()
    
    def set_channel_offset(self, offset):
        """Update channel offset and redraw"""
        old_offset = self.channel_offset
        self.channel_offset = offset
        
        # Update existing data with new offset
        for i in range(self.num_channels):
            # Remove old offset, add new offset
            offset_adjustment = (i * offset) - (i * old_offset)
            adjusted_data = self.channel_data[i] + offset_adjustment
            self.channel_data[i] = adjusted_data
            self.channel_lines[i].set_data(self.time_data, adjusted_data)
            
        self.draw_idle()


class DisplayWidget(QWidget):
    """Main display widget - handles interaction logic"""
    
    # Signal for status updates
    statusMessage = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.ui = Ui_DisplayWidget()
        self.ui.setupUi(self)
        self.channels = ['S1-D1','S1-D2','S2-D1','S2-D2', 'S3-D1','S3-D3','S3-D4']
        # Initialize signal processor
        self.signal_processor = create_signal_processor(sample_rate=100, num_channels=8)
        
        # Initialize components
        self.data_generator = DataGenerator()
        self.recorded_data = []
        self.is_recording = False
        self.current_filter = "No Filter"
        self.online_filtering_enabled = False
        
        # Data buffer for storing generated data
        self.data_buffer = []
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_plot_from_buffer)
        
        # Setup plot canvas
        self.setup_plot_canvas()
        
        # Setup additional UI components
        self.setup_additional_ui()
        
        # Connect signals
        self.connect_signals()
        
        # Initialize UI state
        self.initialize_ui_state()
        
    def setup_plot_canvas(self):
        """Initialize the plotting canvas"""
        self.plot_canvas = PlotCanvas(self.ui.plotWidget,self.channels,  width=12, height=6)
        layout = QVBoxLayout(self.ui.plotWidget)
        layout.addWidget(self.plot_canvas)
        
        # Connect data generator
        self.data_generator.dataReady.connect(self.on_new_data)
        
    def setup_additional_ui(self):
        """Setup additional UI components for online/offline filtering"""
        # Create a horizontal layout for filtering mode selection
        filter_mode_layout = QHBoxLayout()
        
        # Online filtering checkbox
        self.online_filter_checkbox = QCheckBox("Enable Online Filtering (实时滤波)")
        self.online_filter_checkbox.setToolTip("Apply filtering in real-time to incoming data")
        self.online_filter_checkbox.stateChanged.connect(self.toggle_online_filtering)
        
        # Processing mode combo
        self.processing_mode_label = QLabel("Processing Mode (处理模式):")
        self.processing_mode_combo = QComboBox()
        self.processing_mode_combo.addItems([
            "Real-time Only (仅实时)",
            "Offline Only (仅离线)", 
            "Both (实时+离线)"
        ])
        self.processing_mode_combo.currentTextChanged.connect(self.on_processing_mode_changed)
        
        filter_mode_layout.addWidget(self.online_filter_checkbox)
        filter_mode_layout.addWidget(self.processing_mode_label)
        filter_mode_layout.addWidget(self.processing_mode_combo)
        filter_mode_layout.addStretch()
        
        # Add to main layout (assuming there's a main layout in ui_display)
        if hasattr(self.ui, 'mainLayout'):
            self.ui.mainLayout.insertLayout(0, filter_mode_layout)
        
    def connect_signals(self):
        """Connect UI signals to their respective slots"""
        # Control buttons
        self.ui.startButton.clicked.connect(self.start_acquisition)
        self.ui.stopButton.clicked.connect(self.stop_acquisition)
        self.ui.resetButton.clicked.connect(self.reset_system)
        self.ui.recordButton.clicked.connect(self.toggle_recording)
        self.ui.saveButton.clicked.connect(self.save_data)
        
        # Filter controls
        self.ui.filterTypeCombo.currentTextChanged.connect(self.on_filter_changed)
        self.ui.sgApplyButton.clicked.connect(self.apply_sg_filter)
        self.ui.butterworthApplyButton.clicked.connect(self.apply_butterworth_filter)
        
    def initialize_ui_state(self):
        """Set initial UI state"""
        self.ui.set_control_states(
            start_enabled=True,
            stop_enabled=False,
            reset_enabled=True,
            record_enabled=True,
            save_enabled=True
        )
        
        # Set default filter visibility
        self.on_filter_changed(self.ui.filterTypeCombo.currentText())
        
    def emit_status_message(self, message):
        """Emit status message"""
        self.statusMessage.emit(message)
        
    def toggle_online_filtering(self, state):
        """Toggle online filtering on/off"""
        self.online_filtering_enabled = state == Qt.Checked
        
        if self.online_filtering_enabled:
            self.setup_online_filters()
            self.emit_status_message("Online filtering enabled")
        else:
            self.signal_processor.reset_online_filters()
            self.emit_status_message("Online filtering disabled")
    
    def on_processing_mode_changed(self, mode):
        """Handle processing mode change"""
        mode_messages = {
            "Real-time Only (仅实时)": "Real-time processing mode - filters applied during acquisition",
            "Offline Only (仅离线)": "Offline processing mode - filters applied to recorded data",
            "Both (实时+离线)": "Hybrid mode - real-time preview with offline analysis capability"
        }
        self.emit_status_message(mode_messages.get(mode, "Processing mode changed"))
    
    def setup_online_filters(self):
        """Setup online filters for all channels based on current settings"""
        if not self.online_filtering_enabled:
            return
            
        filter_type = self.current_filter
        
        if "S-G" in filter_type:
            params = {
                'window_length': self.ui.windowSpinBox.value(),
                'polyorder': self.ui.polyOrderSpinBox.value()
            }
            for ch in range(8):
                self.signal_processor.setup_online_filter(ch, 'sg', **params)
                
        elif "Butterworth" in filter_type:
            try:
                params = {
                    'low_cutoff': float(self.ui.lowCutoffEdit.text()),
                    'high_cutoff': float(self.ui.highCutoffEdit.text()),
                    'order': self.ui.orderSpinBox.value(),
                    'filter_type': 'bandpass'
                }
                for ch in range(8):
                    self.signal_processor.setup_online_filter(ch, 'butterworth', **params)
            except ValueError:
                self.emit_status_message("Invalid Butterworth filter parameters")
                return
                
        elif "Smooth" in filter_type:
            params = {'window_size': 5}  # Default window size
            for ch in range(8):
                self.signal_processor.setup_online_filter(ch, 'smooth', **params)
        
        self.emit_status_message(f"Online filters setup for {filter_type}")
        
    def on_filter_changed(self, filter_type):
        """Handle filter type change and show/hide appropriate filter groups"""
        self.current_filter = filter_type
        
        # Determine which filter groups to show
        sg_visible = "S-G" in filter_type
        butterworth_visible = "Butterworth" in filter_type
        
        # Update visibility
        self.ui.set_filter_group_visibility(
            sg_visible=sg_visible,
            butterworth_visible=butterworth_visible
        )
        
        # Re-setup online filters if enabled
        if self.online_filtering_enabled:
            self.setup_online_filters()
        
        # Update status message
        status_messages = {
            "S-G Filter (S-G滤波)": "S-G Filter selected - configure window size and polynomial order",
            "Butterworth Filter (Butterworth滤波)": "Butterworth Filter selected - configure cutoff frequencies and order",
            "No Filter (不滤波)": "No filtering applied",
            "Smooth Filter (平滑滤波)": "Smooth Filter selected - using moving average"
        }
        
        message = status_messages.get(filter_type, "Filter type changed")
        self.emit_status_message(message)
        
    def start_acquisition(self):
        """Start data acquisition"""
        self.data_generator.start_acquisition()
        self.plot_timer.start(100)  # Update plot every 100ms
        self.ui.startButton.setEnabled(False)
        self.ui.stopButton.setEnabled(True)
        self.ui.statusbar.showMessage("Acquiring data...")

    def stop_acquisition(self):
        """Stop data acquisition"""
        self.data_generator.stop_acquisition()
        self.plot_timer.stop()
        self.ui.startButton.setEnabled(True)
        self.ui.stopButton.setEnabled(False)
        self.ui.statusbar.showMessage("Data acquisition stopped")

    def reset_system(self):
        """Reset the entire system"""
        self.stop_acquisition()
        self.is_recording = False
        self.recorded_data.clear()
        self.data_buffer.clear()
        self.plot_canvas.clear_plot()
        self.signal_processor.reset_online_filters()
        self.ui.recordButton.setText("Record (记录)")
        self.emit_status_message("System reset")
        
    def toggle_recording(self):
        """Toggle data recording"""
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.ui.recordButton.setText("Stop Recording")
            self.emit_status_message("Recording data...")
        else:
            self.ui.recordButton.setText("Record (记录)")
            self.emit_status_message(f"Recording stopped. {len(self.recorded_data)} samples recorded")
    
    def on_new_data(self, data):
        """Handle new data from generator"""
        # Apply signal type conversion
        processed_data = self.apply_signal_conversion(data.copy())
        
        # Apply online filtering if enabled
        if self.online_filtering_enabled:
            for ch in range(len(processed_data)):
                processed_data[ch] = self.signal_processor.process_sample_online(ch, processed_data[ch])
        
        # Record raw data (before filtering) for offline processing
        if self.is_recording:
            self.recorded_data.append(data.copy())
        
        # Store data in buffer instead of updating plot directly
        self.data_buffer.append(data.copy())
    
    def update_plot_from_buffer(self):
        """Update plot with data from buffer (called every 100ms)"""
        if not self.data_buffer:
            return
        
        # Process all data points in buffer
        for data in self.data_buffer:
            self.plot_canvas.update_data(data)
        
        # Clear buffer after processing
        self.data_buffer.clear()
    def apply_sg_filter(self):
        """Apply S-G filter configuration and update online filters if needed"""
        window_length = self.ui.windowSpinBox.value()
        poly_order = self.ui.polyOrderSpinBox.value()
        
        if window_length % 2 == 0:
            window_length += 1
            self.ui.windowSpinBox.setValue(window_length)
        
        if window_length <= poly_order:
            QMessageBox.warning(self, "Warning", 
                              f"Window length ({window_length}) must be larger than polynomial order ({poly_order})")
            return
        
        # Update online filters if enabled
        if self.online_filtering_enabled and "S-G" in self.current_filter:
            self.setup_online_filters()
        
        self.emit_status_message("S-G filter parameters updated")
        QMessageBox.information(self, "Filter Updated", 
                              f"S-G filter configured: window={window_length}, poly_order={poly_order}")
    
    def apply_butterworth_filter(self):
        """Apply Butterworth filter configuration and update online filters if needed"""
        try:
            low_cutoff = float(self.ui.lowCutoffEdit.text())
            high_cutoff = float(self.ui.highCutoffEdit.text())
            order = self.ui.orderSpinBox.value()
            
            if low_cutoff <= 0 or high_cutoff <= 0:
                QMessageBox.warning(self, "Warning", "Cutoff frequencies must be positive values.")
                return
                
            if low_cutoff >= high_cutoff:
                QMessageBox.warning(self, "Warning", "Low cutoff must be less than high cutoff frequency.")
                return
            
            nyquist = self.signal_processor.sample_rate / 2
            if high_cutoff >= nyquist:
                QMessageBox.warning(self, "Warning", 
                                  f"High cutoff ({high_cutoff} Hz) must be less than Nyquist frequency ({nyquist} Hz)")
                return
            
            # Update online filters if enabled
            if self.online_filtering_enabled and "Butterworth" in self.current_filter:
                self.setup_online_filters()
                
            self.emit_status_message("Butterworth filter parameters updated")
            QMessageBox.information(self, "Filter Updated", 
                                  f"Butterworth filter configured: {low_cutoff}-{high_cutoff} Hz, Order {order}")
            
        except ValueError:
            QMessageBox.warning(self, "Warning", "Please enter valid numeric values for cutoff frequencies.")
    
    def on_offset_changed(self, value):
        """Handle channel offset change"""
        self.plot_canvas.set_channel_offset(value)
    
    def clear_plot(self):
        """Clear the plot"""
        self.plot_canvas.clear_plot()
        self.emit_status_message("Plot cleared")
    
    def save_data(self):
        """Save recorded data to file with option to apply offline filtering"""
        if not self.recorded_data:
            QMessageBox.warning(self, "Warning", "No data to save.")
            return
        
        # Ask user if they want to apply offline filtering
        processing_mode = self.processing_mode_combo.currentText()
        apply_filtering = False
        
        if "Offline" in processing_mode and self.current_filter != "No Filter (不滤波)":
            reply = QMessageBox.question(self, "Offline Filtering", 
                                       "Apply current filter settings to data before saving?",
                                       QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return
            apply_filtering = reply == QMessageBox.Yes
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Data", 
            f"signal_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;JSON Files (*.json)"
        )
        
        if filename:
            try:
                # Get data to save
                if apply_filtering:
                    data_to_save = self.apply_offline_filtering()
                    if data_to_save is None:
                        return
                else:
                    data_to_save = np.array(self.recorded_data)
                
                if filename.endswith('.json'):
                    save_dict = {
                        'data': data_to_save.tolist(),
                        'metadata': {
                            'timestamp': datetime.now().isoformat(),
                            'sample_rate': self.signal_processor.sample_rate,
                            'num_channels': data_to_save.shape[1] if data_to_save.ndim > 1 else 1,
                            'signal_type': self.ui.signalTypeCombo.currentText(),
                            'filter_type': self.current_filter,
                            'num_samples': len(data_to_save),
                            'filtered': apply_filtering,
                            'processing_mode': processing_mode
                        }
                    }
                    with open(filename, 'w') as f:
                        json.dump(save_dict, f, indent=2)
                else:
                    if data_to_save.ndim == 1:
                        data_to_save = data_to_save.reshape(-1, 1)
                    df = pd.DataFrame(data_to_save, columns=[f'Channel_{i+1}' for i in range(data_to_save.shape[1])])
                    df['Time'] = np.arange(len(df)) / self.signal_processor.sample_rate
                    df.to_csv(filename, index=False)
                
                filter_status = " (filtered)" if apply_filtering else " (raw)"
                QMessageBox.information(self, "Success", f"Data saved to {filename}{filter_status}")
                self.emit_status_message(f"Data saved: {len(data_to_save)} samples{filter_status}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save data: {str(e)}")
    
    def load_data(self, filename):
        """Load data from file"""
        try:
            if filename.endswith('.json'):
                with open(filename, 'r') as f:
                    data_dict = json.load(f)
                self.recorded_data = data_dict['data']
                if 'metadata' in data_dict:
                    metadata = data_dict['metadata']
                    filter_info = f"\nFiltered: {metadata.get('filtered', 'unknown')}" if 'filtered' in metadata else ""
                    QMessageBox.information(self, "File Info", 
                                          f"Loaded {metadata.get('num_samples', 'unknown')} samples\n"
                                          f"Signal type: {metadata.get('signal_type', 'unknown')}\n"
                                          f"Filter: {metadata.get('filter_type', 'unknown')}{filter_info}")
            else:
                df = pd.read_csv(filename)
                data_cols = [col for col in df.columns if 'Channel' in col or col.startswith('Ch')]
                if data_cols:
                    self.recorded_data = df[data_cols].values.tolist()
                else:
                    data_cols = [col for col in df.columns if col != 'Time']
                    self.recorded_data = df[data_cols].values.tolist()
            
            self.emit_status_message(f"Loaded {len(self.recorded_data)} samples from {os.path.basename(filename)}")
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")
            return False
    
    def export_plot(self, filename):
        """Export plot to file"""
        try:
            self.plot_canvas.fig.savefig(filename, dpi=300, bbox_inches='tight')
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export plot: {str(e)}")
            return False
    
    def get_filter_frequency_response(self):
        """Get and display filter frequency response"""
        if self.current_filter == "No Filter (不滤波)":
            QMessageBox.information(self, "Filter Response", "No filter is currently selected.")
            return
            
        try:
            if "S-G" in self.current_filter:
                params = {
                    'window_length': self.ui.windowSpinBox.value(),
                    'polyorder': self.ui.polyOrderSpinBox.value()
                }
                # S-G filters don't have traditional frequency response
                QMessageBox.information(self, "Filter Response", 
                                      "Savitzky-Golay filters don't have traditional frequency response.\n"
                                      "They preserve signal features while smoothing.")
                return
                
            elif "Butterworth" in self.current_filter:
                params = {
                    'low_cutoff': float(self.ui.lowCutoffEdit.text()),
                    'high_cutoff': float(self.ui.highCutoffEdit.text()),
                    'order': self.ui.orderSpinBox.value(),
                    'filter_type': 'bandpass'
                }
                freqs, response = self.signal_processor.get_filter_frequency_response('butterworth', **params)
                
                # Simple text display of key frequencies
                passband_start = params['low_cutoff']
                passband_end = params['high_cutoff']
                QMessageBox.information(self, "Filter Response", 
                                      f"Butterworth Bandpass Filter\n"
                                      f"Passband: {passband_start:.2f} - {passband_end:.2f} Hz\n"
                                      f"Order: {params['order']}\n"
                                      f"Sample Rate: {self.signal_processor.sample_rate} Hz")
                                      
        except ValueError:
            QMessageBox.warning(self, "Warning", "Invalid filter parameters.")
    
    def closeEvent(self, event): # type: ignore
        """Handle widget close event"""
        if self.data_generator.running:
            self.data_generator.stop_acquisition()
        if self.plot_timer.isActive():
            self.plot_timer.stop()
        event.accept()


class MainApplication(QMainWindow):
    """Main application window that contains the DisplayWidget"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Signal Processing and Data Visualization")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 850)
        
        # Create central widget
        self.display_widget = DisplayWidget()
        self.setCentralWidget(self.display_widget)
        
        # Connect status message
        self.display_widget.statusMessage.connect(self.update_status)
        
        # Setup menu bar and status bar
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
        
    def open_file(self):
        """Open data file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Data File", "",
            "CSV Files (*.csv);;JSON Files (*.json)"
        )
        if filename:
            self.display_widget.load_data(filename)
            
    def export_plot(self):
        """Export plot to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Plot", 
            f"plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG Image (*.png);;PDF Document (*.pdf);;SVG Vector (*.svg)"
        )
        if filename:
            if self.display_widget.export_plot(filename):
                QMessageBox.information(self, "Success", f"Plot exported to {filename}")
            
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About", 
                         "Signal Processing and Data Visualization\n\n"
                         "Version 2.0\n\n"
                         "A real-time signal processing application with "
                         "online and offline filtering capabilities, "
                         "multiple filter types, and advanced visualization.\n\n"
                         "Features:\n"
                         "• Real-time (online) filtering\n"
                         "• Batch (offline) filtering\n"
                         "• Multiple filter types\n"
                         "• Signal type conversions\n"
                         "• Multi-channel visualization")
    
    def closeEvent(self, event): # type: ignore
        """Handle application close event"""
        if hasattr(self.display_widget, 'data_generator'):
            self.display_widget.closeEvent(event)
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Signal Processing and Data Visualization")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Signal Processing Lab")
    
    # Create and show main window
    try:
        main_window = MainApplication()
        main_window.show()
        
        # Start the application event loop
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
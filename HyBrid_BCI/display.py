# -*- coding: utf-8 -*-

"""
Signal Processing and Data Visualization Application

This application provides real-time signal processing capabilities with various
filtering options and multi-channel data visualization with uniform offsets.
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.animation as animation
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QMessageBox, QFileDialog, QWidget)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from scipy import signal
from scipy.signal import savgol_filter
import pandas as pd
import json
from datetime import datetime
import os

from ui_display import Ui_MainWindow


class DataProcessor:
    """Handles signal processing operations"""
    
    def __init__(self):
        self.sample_rate = 100  # Hz
        
    def apply_sg_filter(self, data, window_length=11, polyorder=3):
        """Apply Savitzky-Golay filter"""
        if len(data) < window_length:
            return data
        return savgol_filter(data, window_length, polyorder)
    
    def apply_butterworth_filter(self, data, low_cutoff=0.01, high_cutoff=0.1, order=4):
        """Apply Butterworth bandpass filter"""
        if len(data) < order * 3:
            return data
        
        nyquist = self.sample_rate / 2
        low = low_cutoff / nyquist
        high = high_cutoff / nyquist
        
        if high >= 1.0:
            high = 0.99
        if low >= high:
            low = high * 0.1
            
        b, a = signal.butter(order, [low, high], btype='band')
        return signal.filtfilt(b, a, data)
    
    def apply_smooth_filter(self, data, window_size=5):
        """Apply moving average filter"""
        if len(data) < window_size:
            return data
        return np.convolve(data, np.ones(window_size)/window_size, mode='same')
    
    def convert_to_optical_density(self, raw_data, reference=None):
        """Convert raw light intensity to optical density"""
        if reference is None:
            reference = np.mean(raw_data[:100]) if len(raw_data) > 100 else np.mean(raw_data)
        
        # Avoid log(0) by adding small epsilon
        epsilon = 1e-10
        od = -np.log10((raw_data + epsilon) / (reference + epsilon))
        return od
    
    def convert_to_hemoglobin(self, od_data, pathlength=3.0, extinction_coeff=2.3):
        """Convert optical density to hemoglobin concentration"""
        # Simplified Beer-Lambert law: C = OD / (ε * L)
        concentration = od_data / (extinction_coeff * pathlength)
        return concentration * 1000  # Convert to µM


class DataGenerator(QThread):
    """Simulates real-time data acquisition"""
    
    dataReady = pyqtSignal(np.ndarray)
    
    def __init__(self, num_channels=8):
        super().__init__()
        self.num_channels = num_channels
        self.running = False
        self.sample_rate = 100
        self.time_counter = 0
        
    def run(self):
        timer = QTimer()
        timer.timeout.connect(self.generate_data)
        timer.start(1000 // self.sample_rate)  # 100 Hz
        
        while self.running:
            self.msleep(10)
            
    def generate_data(self):
        if not self.running:
            return
            
        # Generate synthetic multi-channel data
        t = self.time_counter / self.sample_rate
        data = np.zeros(self.num_channels)
        
        for i in range(self.num_channels):
            # Each channel has different frequency components and noise
            freq1 = 0.1 + i * 0.05  # Different base frequencies
            freq2 = 1.0 + i * 0.1   # Higher frequency components
            amplitude = 1.0 + i * 0.2
            
            # Simulate physiological-like signals
            signal_component = (amplitude * np.sin(2 * np.pi * freq1 * t) + 
                              0.3 * np.sin(2 * np.pi * freq2 * t))
            
            # Add some noise
            noise = np.random.normal(0, 0.1)
            
            data[i] = signal_component + noise + 5.0  # DC offset
            
        self.dataReady.emit(data)
        self.time_counter += 1
    
    def start_acquisition(self):
        self.running = True
        if not self.isRunning():
            self.start()
    
    def stop_acquisition(self):
        self.running = False


class PlotCanvas(FigureCanvas):
    """Custom matplotlib canvas for real-time plotting"""
    
    def __init__(self, parent=None, width=12, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='white')
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor('white')
        self.axes.grid(True, alpha=0.3)
        self.axes.set_xlabel('Time (seconds)')
        self.axes.set_ylabel('Amplitude')
        self.axes.set_title('Multi-Channel Signal Visualization')
        
        # Data storage
        self.max_points = 1000
        self.time_data = np.zeros(self.max_points)
        self.channel_data = {}
        self.channel_lines = {}
        self.num_channels = 8
        self.channel_offset = 0.5
        self.colors = plt.cm.tab10(np.linspace(0, 1, self.num_channels))
        
        # Initialize channels
        for i in range(self.num_channels):
            self.channel_data[i] = np.zeros(self.max_points)
            line, = self.axes.plot(self.time_data, self.channel_data[i], 
                                 color=self.colors[i], linewidth=1.5, 
                                 label=f'Channel {i+1}')
            self.channel_lines[i] = line
            
        self.axes.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        self.fig.tight_layout()
        
        self.data_index = 0
        self.start_time = 0
        
    def update_data(self, new_data):
        """Update plot with new data point"""
        current_time = self.data_index / 100.0  # Assuming 100 Hz
        
        # Shift data arrays
        self.time_data[:-1] = self.time_data[1:]
        self.time_data[-1] = current_time
        
        for i, value in enumerate(new_data):
            if i < self.num_channels:
                # Apply channel offset
                offset_value = value + i * self.channel_offset
                self.channel_data[i][:-1] = self.channel_data[i][1:]
                self.channel_data[i][-1] = offset_value
                self.channel_lines[i].set_data(self.time_data, self.channel_data[i])
        
        # Update axis limits
        if self.data_index > self.max_points:
            self.axes.set_xlim(current_time - self.max_points/100.0, current_time)
        else:
            self.axes.set_xlim(0, max(10, current_time))
            
        # Auto-scale y-axis
        all_data = np.concatenate([self.channel_data[i] for i in range(self.num_channels)])
        if len(all_data) > 0 and not np.all(all_data == 0):
            margin = 0.1 * (np.max(all_data) - np.min(all_data))
            self.axes.set_ylim(np.min(all_data) - margin, np.max(all_data) + margin)
        
        self.data_index += 1
        self.draw_idle()
    
    def clear_plot(self):
        """Clear all plotted data"""
        self.time_data = np.zeros(self.max_points)
        for i in range(self.num_channels):
            self.channel_data[i] = np.zeros(self.max_points)
            self.channel_lines[i].set_data(self.time_data, self.channel_data[i])
        self.data_index = 0
        self.draw_idle()
    
    def set_channel_offset(self, offset):
        """Update channel offset and redraw"""
        self.channel_offset = offset
        # Update existing data with new offset
        for i in range(self.num_channels):
            offset_data = self.channel_data[i] + (i * offset - i * 0.5)  # Remove old offset, add new
            self.channel_lines[i].set_data(self.time_data, offset_data)
        self.draw_idle()


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Initialize components
        self.processor = DataProcessor()
        self.data_generator = DataGenerator()
        self.recorded_data = []
        self.is_recording = False
        self.current_filter = "No Filter"
        
        # Setup plot canvas
        self.setup_plot_canvas()
        
        # Connect signals
        self.connect_signals()
        
        # Initialize UI state
        self.initialize_ui_state()
        
        # Status bar
        self.ui.statusbar.showMessage("Ready")
        
    def setup_plot_canvas(self):
        """Initialize the plotting canvas"""
        self.plot_canvas = PlotCanvas(self.ui.plotWidget, width=12, height=6)
        layout = QVBoxLayout(self.ui.plotWidget)
        layout.addWidget(self.plot_canvas)
        
        # Connect data generator
        self.data_generator.dataReady.connect(self.on_new_data)
        
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
        
        # Plot controls
        self.ui.channelOffsetSpinBox.valueChanged.connect(self.on_offset_changed)
        self.ui.clearPlotButton.clicked.connect(self.clear_plot)
        
        # Menu actions
        self.ui.actionOpen.triggered.connect(self.open_file)
        self.ui.actionSave.triggered.connect(self.save_data)
        self.ui.actionExport.triggered.connect(self.export_data)
        self.ui.actionExit.triggered.connect(self.close)
        
    def initialize_ui_state(self):
        """Set initial UI state"""
        self.ui.stopButton.setEnabled(False)
        
        # Hide all filter groups initially
        self.ui.sgFilterGroup.setVisible(False)
        self.ui.butterworthGroup.setVisible(False)
        
        # Set default filter visibility
        self.on_filter_changed(self.ui.filterTypeCombo.currentText())
        
    def on_filter_changed(self, filter_type):
        """Handle filter type change and show/hide appropriate filter groups"""
        self.current_filter = filter_type
        
        # Hide all filter groups first
        self.ui.sgFilterGroup.setVisible(False)
        self.ui.butterworthGroup.setVisible(False)
        
        # Show the appropriate filter group based on selection
        if "S-G" in filter_type:
            self.ui.sgFilterGroup.setVisible(True)
            self.ui.statusbar.showMessage("S-G Filter selected - configure window size and polynomial order")
        elif "Butterworth" in filter_type:
            self.ui.butterworthGroup.setVisible(True)
            self.ui.statusbar.showMessage("Butterworth Filter selected - configure cutoff frequencies and order")
        elif "No Filter" in filter_type:
            self.ui.statusbar.showMessage("No filtering applied")
        elif "Smooth" in filter_type:
            self.ui.statusbar.showMessage("Smooth Filter selected - using moving average")
        
        # Force layout update to properly hide/show widgets
        self.ui.settingsGroup.update()
        
    def start_acquisition(self):
        """Start data acquisition"""
        self.data_generator.start_acquisition()
        self.ui.startButton.setEnabled(False)
        self.ui.stopButton.setEnabled(True)
        self.ui.statusbar.showMessage("Acquiring data...")
        
    def stop_acquisition(self):
        """Stop data acquisition"""
        self.data_generator.stop_acquisition()
        self.ui.startButton.setEnabled(True)
        self.ui.stopButton.setEnabled(False)
        self.ui.statusbar.showMessage("Data acquisition stopped")
        
    def reset_system(self):
        """Reset the entire system"""
        self.stop_acquisition()
        self.is_recording = False
        self.recorded_data.clear()
        self.plot_canvas.clear_plot()
        self.ui.recordButton.setText("Record (记录)")
        self.ui.statusbar.showMessage("System reset")
        
    def toggle_recording(self):
        """Toggle data recording"""
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.ui.recordButton.setText("Stop Recording")
            self.ui.statusbar.showMessage("Recording data...")
        else:
            self.ui.recordButton.setText("Record (记录)")
            self.ui.statusbar.showMessage(f"Recording stopped. {len(self.recorded_data)} samples recorded")
    
    def on_new_data(self, data):
        """Handle new data from generator"""
        # Apply signal type conversion
        signal_type = self.ui.signalTypeCombo.currentText()
        if "Optical Density" in signal_type:
            data = self.processor.convert_to_optical_density(data)
        elif "Hemoglobin" in signal_type:
            data = self.processor.convert_to_optical_density(data)
            data = self.processor.convert_to_hemoglobin(data)
        
        # Apply selected filter
        if "S-G" in self.current_filter and len(self.recorded_data) > 20:
            # Apply filter to recent data history for better results
            recent_data = np.array(self.recorded_data[-50:])
            if len(recent_data) > 0:
                window_length = self.ui.windowSpinBox.value()
                poly_order = self.ui.polyOrderSpinBox.value()
                filtered_recent = np.apply_along_axis(
                    lambda x: self.processor.apply_sg_filter(x, window_length, poly_order),
                    0, recent_data
                )
                data = filtered_recent[-1]  # Use most recent filtered point
        elif "Butterworth" in self.current_filter and len(self.recorded_data) > 50:
            # Apply Butterworth filter to recent data
            recent_data = np.array(self.recorded_data[-100:])
            if len(recent_data) > 0:
                try:
                    low_cutoff = float(self.ui.lowCutoffEdit.text())
                    high_cutoff = float(self.ui.highCutoffEdit.text())
                    order = self.ui.orderSpinBox.value()
                    filtered_recent = np.apply_along_axis(
                        lambda x: self.processor.apply_butterworth_filter(x, low_cutoff, high_cutoff, order),
                        0, recent_data
                    )
                    data = filtered_recent[-1]  # Use most recent filtered point
                except (ValueError, Exception):
                    pass  # Use original data if filter fails
        
        # Record data if recording is enabled
        if self.is_recording:
            self.recorded_data.append(data.copy())
        
        # Update plot
        self.plot_canvas.update_data(data)
    
    def apply_sg_filter(self):
        """Apply S-G filter to recorded data"""
        if not self.recorded_data:
            QMessageBox.warning(self, "Warning", "No data to filter. Start recording first.")
            return
            
        window_length = self.ui.windowSpinBox.value()
        poly_order = self.ui.polyOrderSpinBox.value()
        
        # Ensure window length is odd and larger than poly_order
        if window_length % 2 == 0:
            window_length += 1
            self.ui.windowSpinBox.setValue(window_length)
        
        if window_length <= poly_order:
            QMessageBox.warning(self, "Warning", 
                              f"Window length ({window_length}) must be larger than polynomial order ({poly_order})")
            return
        
        self.ui.statusbar.showMessage("Applying S-G filter...")
        QMessageBox.information(self, "Filter Applied", 
                              f"S-G filter applied with window size {window_length} and polynomial order {poly_order}")
    
    def apply_butterworth_filter(self):
        """Apply Butterworth filter to recorded data"""
        if not self.recorded_data:
            QMessageBox.warning(self, "Warning", "No data to filter. Start recording first.")
            return
            
        try:
            low_cutoff = float(self.ui.lowCutoffEdit.text())
            high_cutoff = float(self.ui.highCutoffEdit.text())
            order = self.ui.orderSpinBox.value()
            
            if low_cutoff <= 0 or high_cutoff <= 0:
                QMessageBox.warning(self, "Warning", "Cutoff frequencies must be positive values.")
                return
                
            if low_cutoff >= high_cutoff:
                QMessageBox.warning(self, "Warning", "Low cutoff frequency must be less than high cutoff frequency.")
                return
            
            # Check if frequencies are reasonable for the sample rate
            nyquist = self.processor.sample_rate / 2
            if high_cutoff >= nyquist:
                QMessageBox.warning(self, "Warning", 
                                  f"High cutoff frequency ({high_cutoff} Hz) must be less than Nyquist frequency ({nyquist} Hz)")
                return
                
            self.ui.statusbar.showMessage("Applying Butterworth filter...")
            QMessageBox.information(self, "Filter Applied", 
                                  f"Butterworth filter applied: {low_cutoff}-{high_cutoff} Hz, Order {order}")
            
        except ValueError:
            QMessageBox.warning(self, "Warning", "Please enter valid numeric values for cutoff frequencies.")
    
    def on_offset_changed(self, value):
        """Handle channel offset change"""
        self.plot_canvas.set_channel_offset(value)
    
    def clear_plot(self):
        """Clear the plot"""
        self.plot_canvas.clear_plot()
        self.ui.statusbar.showMessage("Plot cleared")
    
    def save_data(self):
        """Save recorded data to file"""
        if not self.recorded_data:
            QMessageBox.warning(self, "Warning", "No data to save.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(self, "Save Data", 
                                                f"signal_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                                "CSV Files (*.csv);;JSON Files (*.json)")
        
        if filename:
            try:
                data_array = np.array(self.recorded_data)
                if filename.endswith('.json'):
                    # Save as JSON with metadata
                    save_dict = {
                        'data': data_array.tolist(),
                        'metadata': {
                            'timestamp': datetime.now().isoformat(),
                            'sample_rate': 100,
                            'num_channels': data_array.shape[1],
                            'signal_type': self.ui.signalTypeCombo.currentText(),
                            'filter_type': self.current_filter,
                            'num_samples': len(self.recorded_data)
                        }
                    }
                    with open(filename, 'w') as f:
                        json.dump(save_dict, f, indent=2)
                else:
                    # Save as CSV
                    df = pd.DataFrame(data_array, columns=[f'Channel_{i+1}' for i in range(data_array.shape[1])])
                    df['Time'] = np.arange(len(df)) / 100.0  # Assuming 100 Hz
                    df.to_csv(filename, index=False)
                
                QMessageBox.information(self, "Success", f"Data saved to {filename}")
                self.ui.statusbar.showMessage(f"Data saved: {len(self.recorded_data)} samples")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save data: {str(e)}")
    
    def open_file(self):
        """Open and load data file"""
        filename, _ = QFileDialog.getOpenFileName(self, "Open Data File", "",
                                                "CSV Files (*.csv);;JSON Files (*.json)")
        
        if filename:
            try:
                if filename.endswith('.json'):
                    with open(filename, 'r') as f:
                        data_dict = json.load(f)
                    self.recorded_data = data_dict['data']
                    # Load metadata if available
                    if 'metadata' in data_dict:
                        metadata = data_dict['metadata']
                        QMessageBox.information(self, "File Info", 
                                              f"Loaded {metadata.get('num_samples', 'unknown')} samples\n"
                                              f"Signal type: {metadata.get('signal_type', 'unknown')}\n"
                                              f"Filter: {metadata.get('filter_type', 'unknown')}")
                else:
                    df = pd.read_csv(filename)
                    # Remove time column if present
                    data_cols = [col for col in df.columns if 'Channel' in col or col.startswith('Ch')]
                    if data_cols:
                        self.recorded_data = df[data_cols].values.tolist()
                    else:
                        # Assume all columns except 'Time' are data
                        data_cols = [col for col in df.columns if col != 'Time']
                        self.recorded_data = df[data_cols].values.tolist()
                
                self.ui.statusbar.showMessage(f"Loaded {len(self.recorded_data)} samples from {os.path.basename(filename)}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file: {str(e)}")
    
    def export_data(self):
        """Export data in various formats"""
        if not self.recorded_data:
            QMessageBox.warning(self, "Warning", "No data to export.")
            return
        
        filename, file_type = QFileDialog.getSaveFileName(self, "Export Data", 
                                                        f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                                        "PNG Image (*.png);;PDF Document (*.pdf);;CSV Data (*.csv)")
        
        if filename:
            try:
                if filename.endswith(('.png', '.pdf')):
                    # Export plot as image
                    self.plot_canvas.fig.savefig(filename, dpi=300, bbox_inches='tight')
                    QMessageBox.information(self, "Success", f"Plot exported to {filename}")
                else:
                    # Export data as CSV
                    self.save_data()
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")
    
    def closeEvent(self, event):
        """Handle application close event"""
        if self.data_generator.running:
            self.data_generator.stop_acquisition()
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Signal Processing and Data Visualization")
    app.setApplicationVersion("1.0")
    
    # Set application icon (if available)
    # app.setWindowIcon(QIcon('icon.png'))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
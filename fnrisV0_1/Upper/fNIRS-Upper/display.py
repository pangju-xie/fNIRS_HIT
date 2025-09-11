# -*- coding: utf-8 -*-
"""
Display Implementation Template
This file implements the data display interface for fNIRS devices
"""

import logging
import numpy as np
from typing import Dict, List, Optional
from collections import deque
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QGroupBox, QLabel, QPushButton, QSpinBox, QComboBox,
                             QTabWidget, QTextEdit, QSplitter, QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

# Import plotting library (you may need to install matplotlib or pyqtgraph)
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


class PlotWidget(QWidget):
    """Custom plot widget for real-time data display"""
    
    def __init__(self, title="Data", parent=None):
        super().__init__(parent)
        self.title = title
        self.data_buffer = deque(maxlen=1000)  # Store last 1000 points
        self.time_buffer = deque(maxlen=1000)
        
        if MATPLOTLIB_AVAILABLE:
            self.setupMatplotlibPlot()
        else:
            self.setupFallbackPlot()
    
    def setupMatplotlibPlot(self):
        """Setup matplotlib-based plotting"""
        layout = QVBoxLayout(self)
        
        self.figure = Figure(figsize=(8, 4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        self.ax.set_title(self.title)
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Amplitude')
        self.ax.grid(True, alpha=0.3)
        
        layout.addWidget(self.canvas)
    
    def setupFallbackPlot(self):
        """Setup fallback plot when matplotlib is not available"""
        layout = QVBoxLayout(self)
        
        self.plot_label = QLabel(f"{self.title}\n[绘图功能需要安装 matplotlib]")
        self.plot_label.setAlignment(Qt.AlignCenter)
        self.plot_label.setStyleSheet("""
            QLabel {
                border: 1px solid #cccccc;
                border-radius: 5px;
                background-color: #f9f9f9;
                padding: 20px;
                font-size: 14px;
                color: #666666;
            }
        """)
        
        layout.addWidget(self.plot_label)
    
    def update_data(self, time_value, data_value):
        """Update plot with new data point"""
        self.time_buffer.append(time_value)
        self.data_buffer.append(data_value)
        
        if MATPLOTLIB_AVAILABLE:
            self.ax.clear()
            self.ax.plot(list(self.time_buffer), list(self.data_buffer), 'b-', linewidth=1)
            self.ax.set_title(self.title)
            self.ax.set_xlabel('Time (s)')
            self.ax.set_ylabel('Amplitude')
            self.ax.grid(True, alpha=0.3)
            self.canvas.draw()
        else:
            # Update fallback display
            data_stats = f"最新值: {data_value:.3f}, 数据点数: {len(self.data_buffer)}"
            self.plot_label.setText(f"{self.title}\n{data_stats}\n[绘图功能需要安装 matplotlib]")
    
    def clear_data(self):
        """Clear all data from buffers"""
        self.data_buffer.clear()
        self.time_buffer.clear()
        
        if MATPLOTLIB_AVAILABLE:
            self.ax.clear()
            self.ax.set_title(self.title)
            self.ax.set_xlabel('Time (s)')
            self.ax.set_ylabel('Amplitude')
            self.ax.grid(True, alpha=0.3)
            self.canvas.draw()


class DisplayWidget(QWidget):
    """Display interface for real-time fNIRS data visualization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected_devices = {}
        self.device_data = {}
        self.plot_widgets = {}
        self.is_sampling = False
        
        # Data update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_displays)
        self.update_timer.setInterval(50)  # 20 FPS
        
        self.setupUI()
        self.connectSignals()
        
        logger.info("Display widget initialized")
    
    def setupUI(self):
        """Setup the display user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # === CONTROL SECTION ===
        control_group = QGroupBox("显示控制")
        control_layout = QHBoxLayout(control_group)
        
        self.auto_scale_button = QPushButton("自动缩放")
        self.auto_scale_button.setCheckable(True)
        self.auto_scale_button.setChecked(True)
        control_layout.addWidget(self.auto_scale_button)
        
        self.clear_button = QPushButton("清除数据")
        control_layout.addWidget(self.clear_button)
        
        control_layout.addWidget(QLabel("更新间隔:"))
        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItems(["20ms (50fps)", "50ms (20fps)", "100ms (10fps)", "200ms (5fps)"])
        self.update_interval_combo.setCurrentIndex(1)
        control_layout.addWidget(self.update_interval_combo)
        
        self.record_button = QPushButton("记录数据")
        self.record_button.setEnabled(False)
        self.record_button.setCheckable(True)
        control_layout.addWidget(self.record_button)
        
        control_layout.addStretch()
        
        layout.addWidget(control_group)
        
        # === DEVICE STATUS SECTION ===
        status_group = QGroupBox("设备状态")
        status_layout = QGridLayout(status_group)
        
        self.device_count_label = QLabel("连接设备: 0")
        status_layout.addWidget(self.device_count_label, 0, 0)
        
        self.sampling_status_label = QLabel("采样状态: 停止")
        status_layout.addWidget(self.sampling_status_label, 0, 1)
        
        self.data_rate_label = QLabel("数据速率: -- Hz")
        status_layout.addWidget(self.data_rate_label, 0, 2)
        
        self.data_count_label = QLabel("数据点数: 0")
        status_layout.addWidget(self.data_count_label, 0, 3)
        
        layout.addWidget(status_group)
        
        # === MAIN DISPLAY AREA ===
        main_splitter = QSplitter(Qt.Vertical)
        
        # Plot area with tabs for multiple devices
        self.plot_tabs = QTabWidget()
        self.plot_tabs.setTabPosition(QTabWidget.North)
        main_splitter.addWidget(self.plot_tabs)
        
        # Info/Log panel
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        
        log_group = QGroupBox("数据日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(150)
        self.log_display.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_display)
        
        info_layout.addWidget(log_group)
        main_splitter.addWidget(info_widget)
        
        # Set splitter proportions
        main_splitter.setStretchFactor(0, 3)  # Plot area gets more space
        main_splitter.setStretchFactor(1, 1)  # Log area gets less space
        
        layout.addWidget(main_splitter)
        
        # Initial message
        self.log_message("显示界面已初始化")
        self.log_message("等待设备配置完成和采样开始...")
    
    def connectSignals(self):
        """Connect internal signals"""
        self.clear_button.clicked.connect(self.clear_all_data)
        self.auto_scale_button.clicked.connect(self.toggle_auto_scale)
        self.update_interval_combo.currentTextChanged.connect(self.update_refresh_rate)
        self.record_button.clicked.connect(self.toggle_recording)
    
    # === Sampling Control ===
    
    def on_sampling_started(self):
        """Called when sampling starts"""
        try:
            self.is_sampling = True
            self.sampling_status_label.setText("采样状态: 运行中")
            self.sampling_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.record_button.setEnabled(True)
            
            # Start update timer
            self.update_timer.start()
            
            self.log_message("采样已开始")
            logger.info("Display sampling started")
            
        except Exception as e:
            logger.error(f"Failed to start display sampling: {e}")
    
    def on_sampling_stopped(self):
        """Called when sampling stops"""
        try:
            self.is_sampling = False
            self.sampling_status_label.setText("采样状态: 已停止")
            self.sampling_status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            self.record_button.setEnabled(False)
            self.record_button.setChecked(False)
            
            # Stop update timer
            self.update_timer.stop()
            
            self.log_message("采样已停止")
            logger.info("Display sampling stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop display sampling: {e}")
    
    # === Device Management ===
    
    def on_device_connected(self, sensor_id, sensor_type):
        """Called when a device connects (from configure)"""
        try:
            device_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            
            self.connected_devices[device_key] = {
                'id': sensor_id,
                'type': sensor_type,
                'last_update': 0
            }
            
            # Initialize data storage
            self.device_data[device_key] = {
                'time': [],
                'raw_data': [],
                'processed_data': [],
                'channels': []
            }
            
            # Create plot tab for device
            self.create_device_plot_tab(device_key, sensor_id, sensor_type)
            
            self.update_device_count()
            
            id_str = self.format_device_id(sensor_id)
            self.log_message(f"设备显示已准备: {id_str}")
            
        except Exception as e:
            logger.error(f"Failed to handle device connected in display: {e}")
    
    def on_device_disconnected(self, sensor_id, sensor_type):
        """Called when a device disconnects"""
        try:
            device_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            
            if device_key in self.connected_devices:
                del self.connected_devices[device_key]
                del self.device_data[device_key]
                
                # Remove plot tab
                self.remove_device_plot_tab(device_key)
            
            self.update_device_count()
            
        except Exception as e:
            logger.error(f"Failed to handle device disconnected in display: {e}")
    
    def on_battery_update(self, sensor_id, battery_level):
        """Called when battery level updates"""
        # Could be used to display battery status in plots
        pass
    
    def on_data_received(self, sensor_id, sensor_type, data_params):
        """Called when new data is received"""
        try:
            if not self.is_sampling:
                return
                
            device_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            
            if device_key not in self.device_data:
                return
            
            # Parse data (this is example logic - adjust based on actual data format)
            if data_params and len(data_params) > 4:
                timestamp = data_params[0] if len(data_params) > 0 else 0
                
                # Store raw data
                self.device_data[device_key]['time'].append(timestamp)
                self.device_data[device_key]['raw_data'].append(data_params)
                
                # Process data for display (example: extract channel data)
                # Assuming data format: [timestamp, seq, channel1_850nm, channel1_730nm, ...]
                if len(data_params) >= 6:  # At least one channel of data
                    processed_channels = []
                    for i in range(2, len(data_params), 2):  # Skip timestamp and sequence
                        if i + 1 < len(data_params):
                            ch_850 = data_params[i]
                            ch_730 = data_params[i + 1]
                            # Simple processing: calculate ratio or difference
                            processed_value = ch_850 - ch_730 if ch_850 > 0 and ch_730 > 0 else 0
                            processed_channels.append(processed_value)
                    
                    self.device_data[device_key]['processed_data'].append(processed_channels)
                
                # Update device info
                self.connected_devices[device_key]['last_update'] = timestamp
                
                # Limit data buffer size
                max_points = 5000
                if len(self.device_data[device_key]['time']) > max_points:
                    self.device_data[device_key]['time'] = self.device_data[device_key]['time'][-max_points:]
                    self.device_data[device_key]['raw_data'] = self.device_data[device_key]['raw_data'][-max_points:]
                    self.device_data[device_key]['processed_data'] = self.device_data[device_key]['processed_data'][-max_points:]
                
        except Exception as e:
            logger.error(f"Failed to process received data: {e}")
    
    # === Plot Management ===
    
    def create_device_plot_tab(self, device_key, sensor_id, sensor_type):
        """Create plot tab for a device"""
        try:
            id_str = self.format_device_id(sensor_id)
            type_name = self.get_type_name(sensor_type)
            
            # Create tab widget
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            
            # Device info section
            info_layout = QHBoxLayout()
            info_layout.addWidget(QLabel(f"设备: {id_str} ({type_name})"))
            info_layout.addStretch()
            
            tab_layout.addLayout(info_layout)
            
            # Scroll area for multiple plots
            scroll_area = QScrollArea()
            scroll_widget = QWidget()
            scroll_layout = QVBoxLayout(scroll_widget)
            
            # Create multiple plot widgets for different channels/wavelengths
            plots = {}
            
            # Raw data plots
            raw_850_plot = PlotWidget(f"原始数据 - 850nm", tab_widget)
            raw_730_plot = PlotWidget(f"原始数据 - 730nm", tab_widget)
            processed_plot = PlotWidget(f"处理后数据", tab_widget)
            
            plots['raw_850'] = raw_850_plot
            plots['raw_730'] = raw_730_plot
            plots['processed'] = processed_plot
            
            scroll_layout.addWidget(raw_850_plot)
            scroll_layout.addWidget(raw_730_plot)
            scroll_layout.addWidget(processed_plot)
            
            scroll_area.setWidget(scroll_widget)
            scroll_area.setWidgetResizable(True)
            tab_layout.addWidget(scroll_area)
            
            # Store plot references
            self.plot_widgets[device_key] = plots
            
            # Add tab
            self.plot_tabs.addTab(tab_widget, f"{id_str}")
            
        except Exception as e:
            logger.error(f"Failed to create device plot tab: {e}")
    
    def remove_device_plot_tab(self, device_key):
        """Remove plot tab for a device"""
        try:
            if device_key in self.plot_widgets:
                del self.plot_widgets[device_key]
            
            # Find and remove tab (simplified - in practice you'd need to track tab indices)
            for i in range(self.plot_tabs.count()):
                # This is a simplified approach - you might want to store tab mapping
                pass
                
        except Exception as e:
            logger.error(f"Failed to remove device plot tab: {e}")
    
    def update_displays(self):
        """Update all plot displays with latest data"""
        try:
            if not self.is_sampling:
                return
                
            total_data_points = 0
            
            for device_key, device_data in self.device_data.items():
                if not device_data['time'] or device_key not in self.plot_widgets:
                    continue
                
                plots = self.plot_widgets[device_key]
                time_data = device_data['time']
                
                total_data_points += len(time_data)
                
                # Update raw data plots
                if device_data['raw_data'] and len(device_data['raw_data']) > 0:
                    latest_raw = device_data['raw_data'][-1]
                    latest_time = time_data[-1]
                    
                    # Update 850nm and 730nm plots (example)
                    if len(latest_raw) >= 4:  # timestamp, seq, ch1_850, ch1_730
                        if 'raw_850' in plots:
                            plots['raw_850'].update_data(latest_time, latest_raw[2])
                        if 'raw_730' in plots:
                            plots['raw_730'].update_data(latest_time, latest_raw[3])
                
                # Update processed data plot
                if device_data['processed_data'] and len(device_data['processed_data']) > 0:
                    latest_processed = device_data['processed_data'][-1]
                    latest_time = time_data[-1]
                    
                    if latest_processed and len(latest_processed) > 0:
                        if 'processed' in plots:
                            plots['processed'].update_data(latest_time, latest_processed[0])
            
            # Update status displays
            self.data_count_label.setText(f"数据点数: {total_data_points}")
            
            # Calculate and display data rate (simplified)
            if hasattr(self, '_last_data_count'):
                rate = (total_data_points - self._last_data_count) * (1000 / self.update_timer.interval())
                self.data_rate_label.setText(f"数据速率: {rate:.1f} Hz")
            self._last_data_count = total_data_points
                
        except Exception as e:
            logger.error(f"Failed to update displays: {e}")
    
    # === Control Actions ===
    
    def clear_all_data(self):
        """Clear all data from displays"""
        try:
            for device_data in self.device_data.values():
                device_data['time'].clear()
                device_data['raw_data'].clear()
                device_data['processed_data'].clear()
            
            for plots in self.plot_widgets.values():
                for plot in plots.values():
                    plot.clear_data()
            
            self.log_message("所有数据已清除")
            
        except Exception as e:
            logger.error(f"Failed to clear data: {e}")
    
    def toggle_auto_scale(self):
        """Toggle auto-scaling for plots"""
        # Implementation depends on plotting library
        auto_scale = self.auto_scale_button.isChecked()
        self.log_message(f"自动缩放: {'启用' if auto_scale else '禁用'}")
    
    def update_refresh_rate(self, rate_text):
        """Update display refresh rate"""
        try:
            # Parse refresh rate from combo box text
            if "20ms" in rate_text:
                interval = 20
            elif "50ms" in rate_text:
                interval = 50
            elif "100ms" in rate_text:
                interval = 100
            elif "200ms" in rate_text:
                interval = 200
            else:
                interval = 50
            
            self.update_timer.setInterval(interval)
            self.log_message(f"更新间隔设置为: {interval}ms")
            
        except Exception as e:
            logger.error(f"Failed to update refresh rate: {e}")
    
    def toggle_recording(self):
        """Toggle data recording"""
        recording = self.record_button.isChecked()
        
        if recording:
            self.record_button.setText("停止记录")
            self.record_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
            self.log_message("开始记录数据")
        else:
            self.record_button.setText("记录数据")
            self.record_button.setStyleSheet("")
            self.log_message("停止记录数据")
    
    # === Data Management ===
    
    def save_data(self):
        """Save collected data to files"""
        try:
            if not self.device_data:
                self.log_message("没有数据需要保存")
                return
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            saved_files = []
            
            for device_key, device_data in self.device_data.items():
                if not device_data['time']:
                    continue
                
                device_info = self.connected_devices.get(device_key, {})
                device_id_str = self.format_device_id(device_info.get('id', device_key))
                
                # Save to CSV format
                filename = f"fnirs_data_{device_id_str}_{timestamp}.csv"
                
                try:
                    import csv
                    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)
                        
                        # Write header
                        writer.writerow(['Timestamp', 'Raw_Data', 'Processed_Data'])
                        
                        # Write data
                        for i, time_val in enumerate(device_data['time']):
                            raw_data = device_data['raw_data'][i] if i < len(device_data['raw_data']) else []
                            processed_data = device_data['processed_data'][i] if i < len(device_data['processed_data']) else []
                            
                            writer.writerow([time_val, str(raw_data), str(processed_data)])
                    
                    saved_files.append(filename)
                    
                except Exception as e:
                    logger.error(f"Failed to save data for device {device_id_str}: {e}")
            
            if saved_files:
                self.log_message(f"数据已保存到文件: {', '.join(saved_files)}")
            else:
                self.log_message("数据保存失败")
                
        except Exception as e:
            logger.error(f"Failed to save data: {e}")
    
    # === Helper Methods ===
    
    def update_device_count(self):
        """Update device count display"""
        count = len(self.connected_devices)
        self.device_count_label.setText(f"连接设备: {count}")
    
    def format_device_id(self, sensor_id):
        """Format device ID for display"""
        if isinstance(sensor_id, list):
            return "-".join([f"{x:02X}" for x in sensor_id])
        return str(sensor_id)
    
    def get_type_name(self, sensor_type):
        """Get readable type name"""
        type_names = {
            1: "EEG",
            2: "sEMG", 
            3: "EEG/sEMG",
            4: "fNIRS",
            5: "EEG/fNIRS",
            6: "sEMG/fNIRS",
            7: "EEG/sEMG/fNIRS"
        }
        return type_names.get(sensor_type, f"类型{sensor_type}")
    
    def log_message(self, message):
        """Add message to log display"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")
        
        # Scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    # === Cleanup ===
    
    def cleanup(self):
        """Cleanup when widget is destroyed"""
        try:
            if self.update_timer.isActive():
                self.update_timer.stop()
            
            self.device_data.clear()
            self.connected_devices.clear()
            self.plot_widgets.clear()
            
            logger.info("Display widget cleaned up")
            
        except Exception as e:
            logger.error(f"Display cleanup failed: {e}")
        
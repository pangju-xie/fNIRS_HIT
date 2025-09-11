# -*- coding: utf-8 -*-
"""
Configure Implementation Template
This file implements the configuration interface for fNIRS devices
"""

import logging
from typing import Dict, List, Optional
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QGroupBox, QLabel, QPushButton, QSpinBox, QComboBox, 
                             QCheckBox, QListWidget, QListWidgetItem, QProgressBar,
                             QTextEdit, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

logger = logging.getLogger(__name__)


class ConfigureWidget(QWidget):
    """Configuration interface for fNIRS devices"""
    
    # Signals to communicate with main window
    configuration_completed = pyqtSignal(bool)  # True when config is complete
    send_network_command = pyqtSignal(str, object, object, object)  # command, sensor_id, sensor_type, params
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected_devices = {}
        self.device_configurations = {}
        
        self.setupUI()
        self.connectSignals()
        
        logger.info("Configure widget initialized")
    
    def setupUI(self):
        """Setup the configuration user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # === DEVICE LIST SECTION ===
        device_group = QGroupBox("连接的设备")
        device_layout = QVBoxLayout(device_group)
        
        self.device_list = QListWidget()
        self.device_list.setMaximumHeight(150)
        device_layout.addWidget(self.device_list)
        
        # Device info display
        self.device_info_label = QLabel("请选择设备进行配置")
        self.device_info_label.setStyleSheet("color: #666666; font-style: italic;")
        device_layout.addWidget(self.device_info_label)
        
        layout.addWidget(device_group)
        
        # === CONFIGURATION SECTIONS ===
        config_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Configuration controls
        config_panel = QWidget()
        config_layout = QVBoxLayout(config_panel)
        
        # Sample Rate Configuration
        sample_rate_group = QGroupBox("采样率配置")
        sample_rate_layout = QGridLayout(sample_rate_group)
        
        sample_rate_layout.addWidget(QLabel("采样率:"), 0, 0)
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["10 Hz", "20 Hz", "50 Hz", "100 Hz"])
        self.sample_rate_combo.setCurrentText("20 Hz")
        sample_rate_layout.addWidget(self.sample_rate_combo, 0, 1)
        
        self.sample_rate_button = QPushButton("设置采样率")
        self.sample_rate_button.setEnabled(False)
        sample_rate_layout.addWidget(self.sample_rate_button, 0, 2)
        
        config_layout.addWidget(sample_rate_group)
        
        # Channel Configuration
        channel_group = QGroupBox("通道配置")
        channel_layout = QGridLayout(channel_group)
        
        channel_layout.addWidget(QLabel("光源数量:"), 0, 0)
        self.light_spin = QSpinBox()
        self.light_spin.setRange(1, 16)
        self.light_spin.setValue(8)
        channel_layout.addWidget(self.light_spin, 0, 1)
        
        channel_layout.addWidget(QLabel("探测器数量:"), 1, 0)
        self.detector_spin = QSpinBox()
        self.detector_spin.setRange(1, 16) 
        self.detector_spin.setValue(8)
        channel_layout.addWidget(self.detector_spin, 1, 1)
        
        self.channel_button = QPushButton("配置通道")
        self.channel_button.setEnabled(False)
        channel_layout.addWidget(self.channel_button, 2, 0, 1, 2)
        
        # Channel mapping area
        self.channel_list = QListWidget()
        self.channel_list.setMaximumHeight(100)
        channel_layout.addWidget(QLabel("通道映射:"), 3, 0, 1, 2)
        channel_layout.addWidget(self.channel_list, 4, 0, 1, 2)
        
        config_layout.addWidget(channel_group)
        
        # Configuration Status
        status_group = QGroupBox("配置状态")
        status_layout = QVBoxLayout(status_group)
        
        self.config_progress = QProgressBar()
        self.config_progress.setVisible(False)
        status_layout.addWidget(self.config_progress)
        
        self.status_label = QLabel("未配置")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        self.complete_button = QPushButton("完成配置")
        self.complete_button.setEnabled(False)
        self.complete_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        status_layout.addWidget(self.complete_button)
        
        config_layout.addWidget(status_group)
        config_layout.addStretch()
        
        config_splitter.addWidget(config_panel)
        
        # Right panel - Log/Info display
        info_panel = QWidget()
        info_layout = QVBoxLayout(info_panel)
        
        info_group = QGroupBox("配置日志")
        info_group_layout = QVBoxLayout(info_group)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(200)
        self.log_display.setFont(QFont("Consolas", 9))
        info_group_layout.addWidget(self.log_display)
        
        info_layout.addWidget(info_group)
        info_layout.addStretch()
        
        config_splitter.addWidget(info_panel)
        config_splitter.setStretchFactor(0, 2)  # Config panel gets more space
        config_splitter.setStretchFactor(1, 1)  # Info panel gets less space
        
        layout.addWidget(config_splitter)
        
        # Initial log message
        self.log_message("配置界面已初始化")
    
    def connectSignals(self):
        """Connect internal signals"""
        self.device_list.currentRowChanged.connect(self.on_device_selected)
        self.sample_rate_button.clicked.connect(self.on_sample_rate_set)
        self.channel_button.clicked.connect(self.on_channel_config)
        self.complete_button.clicked.connect(self.on_configuration_complete)
        
        # Auto-update channel list when spinbox values change
        self.light_spin.valueChanged.connect(self.update_channel_mapping)
        self.detector_spin.valueChanged.connect(self.update_channel_mapping)
    
    # === Device Management ===
    
    def on_device_connected(self, sensor_id, sensor_type):
        """Called when a device is connected"""
        try:
            device_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            device_info = {
                'id': sensor_id,
                'type': sensor_type,
                'sample_rate_configured': False,
                'channels_configured': False,
                'configuration_complete': False
            }
            
            self.connected_devices[device_key] = device_info
            self.device_configurations[device_key] = {}
            
            # Update device list
            self.update_device_list()
            
            # Format device info
            id_str = self.format_device_id(sensor_id)
            type_name = self.get_type_name(sensor_type)
            
            self.log_message(f"设备连接: {id_str} ({type_name})")
            
        except Exception as e:
            logger.error(f"Failed to handle device connected: {e}")
    
    def on_device_disconnected(self, sensor_id, sensor_type):
        """Called when a device is disconnected"""
        try:
            device_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            
            if device_key in self.connected_devices:
                del self.connected_devices[device_key]
                del self.device_configurations[device_key]
            
            self.update_device_list()
            
            id_str = self.format_device_id(sensor_id)
            self.log_message(f"设备断开: {id_str}")
            
        except Exception as e:
            logger.error(f"Failed to handle device disconnected: {e}")
    
    def on_battery_update(self, sensor_id, battery_level):
        """Called when battery level is updated"""
        try:
            device_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            
            if device_key in self.connected_devices:
                self.connected_devices[device_key]['battery'] = battery_level
                self.update_device_list()
                
        except Exception as e:
            logger.error(f"Failed to handle battery update: {e}")
    
    # === UI Update Methods ===
    
    def update_device_list(self):
        """Update the device list display"""
        self.device_list.clear()
        
        for device_key, device_info in self.connected_devices.items():
            id_str = self.format_device_id(device_info['id'])
            type_name = self.get_type_name(device_info['type'])
            battery = device_info.get('battery', -1)
            
            # Status indicator
            if device_info.get('configuration_complete', False):
                status_icon = "✓"
                status_color = "#4CAF50"
            else:
                status_icon = "○"
                status_color = "#FF9800"
            
            # Format display text
            battery_str = f"{battery}%" if battery >= 0 else "--"
            display_text = f"{status_icon} {id_str} ({type_name}) - 电量:{battery_str}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, device_key)
            self.device_list.addItem(item)
    
    def on_device_selected(self, row):
        """Handle device selection"""
        if row < 0:
            return
            
        item = self.device_list.item(row)
        if not item:
            return
            
        device_key = item.data(Qt.UserRole)
        device_info = self.connected_devices.get(device_key)
        
        if device_info:
            # Update device info display
            id_str = self.format_device_id(device_info['id'])
            type_name = self.get_type_name(device_info['type'])
            self.device_info_label.setText(f"当前选择: {id_str} ({type_name})")
            
            # Enable configuration buttons
            self.sample_rate_button.setEnabled(True)
            self.channel_button.setEnabled(True)
            
            # Update configuration status
            self.update_configuration_status(device_info)
    
    def update_configuration_status(self, device_info):
        """Update configuration status display"""
        sample_configured = device_info.get('sample_rate_configured', False)
        channels_configured = device_info.get('channels_configured', False)
        
        if sample_configured and channels_configured:
            self.status_label.setText("配置完成")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.complete_button.setEnabled(True)
        elif sample_configured or channels_configured:
            self.status_label.setText("部分配置")
            self.status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
            self.complete_button.setEnabled(False)
        else:
            self.status_label.setText("未配置")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            self.complete_button.setEnabled(False)
    
    def update_channel_mapping(self):
        """Update channel mapping display"""
        self.channel_list.clear()
        
        lights = self.light_spin.value()
        detectors = self.detector_spin.value()
        
        # Generate standard channel mapping (example)
        for light in range(1, lights + 1):
            for detector in range(1, detectors + 1):
                if abs(light - detector) <= 3:  # Adjacent channels only
                    channel_text = f"L{light} -> D{detector}"
                    self.channel_list.addItem(channel_text)
    
    # === Configuration Actions ===
    
    def on_sample_rate_set(self):
        """Handle sample rate configuration"""
        try:
            current_item = self.device_list.currentItem()
            if not current_item:
                return
            
            device_key = current_item.data(Qt.UserRole)
            device_info = self.connected_devices.get(device_key)
            
            if not device_info:
                return
            
            # Get selected sample rate
            rate_text = self.sample_rate_combo.currentText()
            rate_value = int(rate_text.split()[0])
            
            # Map to rate index (assuming 10, 20, 50, 100 Hz mapping to 0, 1, 2, 3)
            rate_mapping = {10: 0, 20: 1, 50: 2, 100: 3}
            rate_index = rate_mapping.get(rate_value, 1)
            
            # Send network command
            self.send_network_command.emit('sendSampleRate', device_info['id'], device_info['type'], rate_index)
            
            # Update status
            device_info['sample_rate_configured'] = True
            self.device_configurations[device_key]['sample_rate'] = rate_value
            
            self.update_configuration_status(device_info)
            self.log_message(f"设置采样率: {rate_value} Hz")
            
        except Exception as e:
            logger.error(f"Failed to set sample rate: {e}")
            self.log_message(f"设置采样率失败: {e}")
    
    def on_channel_config(self):
        """Handle channel configuration"""
        try:
            current_item = self.device_list.currentItem()
            if not current_item:
                return
            
            device_key = current_item.data(Qt.UserRole)
            device_info = self.connected_devices.get(device_key)
            
            if not device_info:
                return
            
            lights = self.light_spin.value()
            detectors = self.detector_spin.value()
            
            # Generate channel pairs (example logic)
            channel_pairs = []
            for light in range(1, lights + 1):
                for detector in range(1, detectors + 1):
                    if abs(light - detector) <= 3:  # Adjacent channels
                        channel_pairs.append([light, detector])
            
            # Send network command
            self.send_network_command.emit('sendChannels', device_info['id'], device_info['type'], 
                                         (lights, detectors, channel_pairs))
            
            # Update status
            device_info['channels_configured'] = True
            self.device_configurations[device_key]['channels'] = {
                'lights': lights,
                'detectors': detectors,
                'pairs': channel_pairs
            }
            
            self.update_configuration_status(device_info)
            self.log_message(f"配置通道: {lights}个光源, {detectors}个探测器, {len(channel_pairs)}个通道")
            
        except Exception as e:
            logger.error(f"Failed to configure channels: {e}")
            self.log_message(f"通道配置失败: {e}")
    
    def on_configuration_complete(self):
        """Handle configuration completion"""
        try:
            # Check if all devices are configured
            all_configured = True
            for device_info in self.connected_devices.values():
                if not (device_info.get('sample_rate_configured', False) and 
                        device_info.get('channels_configured', False)):
                    all_configured = False
                    break
            
            if all_configured and len(self.connected_devices) > 0:
                # Mark all devices as configuration complete
                for device_info in self.connected_devices.values():
                    device_info['configuration_complete'] = True
                
                # Update display
                self.update_device_list()
                self.status_label.setText("所有设备配置完成")
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                
                # Signal completion to main window
                self.configuration_completed.emit(True)
                self.log_message("配置完成 - 可以切换到显示界面")
                
            else:
                self.log_message("请完成所有设备的配置")
                
        except Exception as e:
            logger.error(f"Failed to complete configuration: {e}")
    
    # === Helper Methods ===
    
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
            self.connected_devices.clear()
            self.device_configurations.clear()
            logger.info("Configure widget cleaned up")
        except Exception as e:
            logger.error(f"Configure cleanup failed: {e}")
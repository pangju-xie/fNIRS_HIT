# -*- coding: utf-8 -*-

"""
Enhanced UI Configuration Module
Handles all UI-related operations for device configuration management
"""

from typing import List, Dict, Set, Any, Optional, Union
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox
from PyQt5.QtCore import Qt
import numpy as np
import logging
import locate

logger = logging.getLogger(__name__)

class UIConstants:
    """Constants for UI configuration"""
    SENSOR_CONTROL_MAPPINGS = {
        'sampling': {
            'eeg': ['eegSamplingLabel', 'eegSamplingCombo'],
            'fnirs': ['fnirsSamplingLabel', 'fnirsSamplingCombo'],
            'semg': ['semgSamplingLabel', 'semgSamplingCombo']
        },
        'channels': {
            'eeg': ['eegChannelsLabel_2', 'eegChannelsSpinBox_2'],
            'semg': ['semgChannelsLabel_2', 'semgChannelsSpinBox_2'],
            'fnirs': ['fnirsSourcesLabel_2', 'fnirsSourcesSpinBox_2', 
                     'fnirsDetectorsLabel_2', 'fnirsDetectorsSpinBox_2']
        }
    }
    
    SAMPLING_CONFIG = {
        'eeg': {'control': 'eegSamplingCombo', 'rates': [500, 1000, 2000]},
        'fnirs': {'control': 'fnirsSamplingCombo', 'rates': [10, 20]},
        'semg': {'control': 'semgSamplingCombo', 'rates': [500, 1000, 2000]}
    }
    
    SENSOR_COLORS = {
        'eeg': '#2196F3',
        'semg': '#FF9800',
        'fnirs_source': '#E91E63',
        'fnirs_detector': '#1040ff'
    }


class Ui_ConfigForm(object):
    def setupUi(self, ConfigForm):
        ConfigForm.setObjectName("ConfigForm")
        ConfigForm.resize(1188, 838)
        ConfigForm.setWindowTitle("Device Configuration")
        ConfigForm.setStyleSheet("QGroupBox { font-weight: bold; }")

        # Sampling Rate Configuration Group
        self._setup_sampling_rate_group(ConfigForm)
        
        # Channel Configuration Group
        self._setup_channel_config_group(ConfigForm)

        QtCore.QMetaObject.connectSlotsByName(ConfigForm)

    def _setup_sampling_rate_group(self, ConfigForm):
        """Setup sampling rate configuration group"""
        self.samplingRateGroup = QtWidgets.QGroupBox(ConfigForm)
        self.samplingRateGroup.setGeometry(QtCore.QRect(20, 20, 1160, 80))
        self.samplingRateGroup.setObjectName("samplingRateGroup")
        self.samplingRateGroup.setTitle("采样率配置")

        self.samplingRateWidget = QtWidgets.QWidget(self.samplingRateGroup)
        self.samplingRateWidget.setGeometry(QtCore.QRect(10, 25, 1140, 45))
        self.samplingRateWidget.setObjectName("samplingRateWidget")
        
        self.samplingRateLayout = QtWidgets.QHBoxLayout(self.samplingRateWidget)
        self.samplingRateLayout.setContentsMargins(0, 0, 0, 0)
        self.samplingRateLayout.setObjectName("samplingRateLayout")

        self._setup_sampling_controls()

    def _setup_sampling_controls(self):
        """Setup individual sampling rate controls"""
        # EEG Sampling Rate
        self.eegSamplingLabel = QtWidgets.QLabel(self.samplingRateWidget)
        self.eegSamplingLabel.setText("EEG (Hz):")
        self.eegSamplingLabel.setObjectName("eegSamplingLabel")
        self.samplingRateLayout.addWidget(self.eegSamplingLabel)

        self.eegSamplingCombo = QtWidgets.QComboBox(self.samplingRateWidget)
        self.eegSamplingCombo.setObjectName("eegSamplingCombo")
        self.eegSamplingCombo.addItems(["500", "1000", "2000"])
        self.eegSamplingCombo.setCurrentText("1000")
        self.samplingRateLayout.addWidget(self.eegSamplingCombo)

        self._add_spacer()

        # fNIRS Sampling Rate
        self.fnirsSamplingLabel = QtWidgets.QLabel(self.samplingRateWidget)
        self.fnirsSamplingLabel.setText("fNIRS (Hz):")
        self.fnirsSamplingLabel.setObjectName("fnirsSamplingLabel")
        self.samplingRateLayout.addWidget(self.fnirsSamplingLabel)

        self.fnirsSamplingCombo = QtWidgets.QComboBox(self.samplingRateWidget)
        self.fnirsSamplingCombo.setObjectName("fnirsSamplingCombo")
        self.fnirsSamplingCombo.addItems(["10", "20", "50"])
        self.fnirsSamplingCombo.setCurrentText("10")
        self.samplingRateLayout.addWidget(self.fnirsSamplingCombo)

        self._add_spacer()

        # sEMG Sampling Rate
        self.semgSamplingLabel = QtWidgets.QLabel(self.samplingRateWidget)
        self.semgSamplingLabel.setText("sEMG (Hz):")
        self.semgSamplingLabel.setObjectName("semgSamplingLabel")
        self.samplingRateLayout.addWidget(self.semgSamplingLabel)

        self.semgSamplingCombo = QtWidgets.QComboBox(self.samplingRateWidget)
        self.semgSamplingCombo.setObjectName("semgSamplingCombo")
        self.semgSamplingCombo.addItems(["500", "1000", "2000"])
        self.semgSamplingCombo.setCurrentText("1000")
        self.samplingRateLayout.addWidget(self.semgSamplingCombo)

        self._add_spacer()

    def _add_spacer(self):
        """Add horizontal spacer"""
        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.samplingRateLayout.addItem(spacer)

    def _setup_channel_config_group(self, ConfigForm):
        """Setup channel configuration group"""
        self.channelConfigGroup = QtWidgets.QGroupBox(ConfigForm)
        self.channelConfigGroup.setGeometry(QtCore.QRect(20, 110, 1160, 711))
        self.channelConfigGroup.setObjectName("channelConfigGroup")
        self.channelConfigGroup.setTitle("通道配置")

        self._setup_control_buttons()
        self._setup_device_params()
        self._setup_config_tabs()

    def _setup_control_buttons(self):
        """Setup control buttons"""
        self.controlButtonsWidget = QtWidgets.QWidget(self.channelConfigGroup)
        self.controlButtonsWidget.setGeometry(QtCore.QRect(10, 25, 1140, 40))
        self.controlButtonsWidget.setObjectName("controlButtonsWidget")
        
        self.controlButtonsLayout = QtWidgets.QHBoxLayout(self.controlButtonsWidget)
        self.controlButtonsLayout.setContentsMargins(0, 0, 0, 0)
        self.controlButtonsLayout.setObjectName("controlButtonsLayout")

        # Create buttons
        button_configs = [
            ("loadConfigBtn", "加载配置"),
            ("createConfigBtn", "新建配置"),
            ("saveConfigBtn", "保存配置"),
            ("resetConfigBtn", "全部重置")
        ]

        for btn_name, btn_text in button_configs:
            button = QtWidgets.QPushButton(self.controlButtonsWidget)
            button.setText(btn_text)
            button.setObjectName(btn_name)
            self.controlButtonsLayout.addWidget(button)
            setattr(self, btn_name, button)

        # Control spacer
        controlSpacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.controlButtonsLayout.addItem(controlSpacer)

        # Generate config button
        self.generateConfigBtn = QtWidgets.QPushButton(self.controlButtonsWidget)
        self.generateConfigBtn.setText("设置")
        self.generateConfigBtn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        self.generateConfigBtn.setObjectName("generateConfigBtn")
        self.controlButtonsLayout.addWidget(self.generateConfigBtn)

    def _setup_device_params(self):
        """Setup device parameters controls"""
        self.deviceParamsWidget = QtWidgets.QWidget(self.channelConfigGroup)
        self.deviceParamsWidget.setGeometry(QtCore.QRect(10, 75, 1140, 31))
        self.deviceParamsWidget.setObjectName("deviceParamsWidget")
        
        self.deviceParamsLayout = QtWidgets.QHBoxLayout(self.deviceParamsWidget)
        self.deviceParamsLayout.setContentsMargins(0, 0, 0, 0)
        self.deviceParamsLayout.setObjectName("deviceParamsLayout")

        self._setup_sensor_param_controls()

        # Add horizontal spacer
        horizontalSpacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.deviceParamsLayout.addItem(horizontalSpacer)

    def _setup_sensor_param_controls(self):
        """Setup sensor parameter controls"""
        # EEG Channels
        self._add_sensor_control("EEG通道数:", "eegChannelsLabel_2", "eegChannelsSpinBox_2", 
                                UIConstants.SENSOR_COLORS['eeg'], 1, 256, 32)
        
        # sEMG Channels
        self._add_sensor_control("sEMG通道数:", "semgChannelsLabel_2", "semgChannelsSpinBox_2", 
                                UIConstants.SENSOR_COLORS['semg'], 1, 64, 8)
        
        # fNIRS Sources
        self._add_sensor_control("fNIRS光源数:", "fnirsSourcesLabel_2", "fnirsSourcesSpinBox_2", 
                                UIConstants.SENSOR_COLORS['fnirs_source'], 1, 32, 8)
        
        # fNIRS Detectors
        self._add_sensor_control("fNIRS探测器数:", "fnirsDetectorsLabel_2", "fnirsDetectorsSpinBox_2", 
                                UIConstants.SENSOR_COLORS['fnirs_detector'], 1, 32, 8)

    def _add_sensor_control(self, label_text: str, label_name: str, spinbox_name: str, 
                           color: str, min_val: int, max_val: int, default_val: int):
        """Add a sensor control group"""
        layout = QtWidgets.QHBoxLayout()
        
        label = QtWidgets.QLabel(self.deviceParamsWidget)
        label.setStyleSheet(f"font-weight: bold; color: {color};")
        label.setText(label_text)
        label.setObjectName(label_name)
        layout.addWidget(label)

        spinbox = QtWidgets.QSpinBox(self.deviceParamsWidget)
        spinbox.setMinimum(min_val)
        spinbox.setMaximum(max_val)
        spinbox.setValue(default_val)
        spinbox.setObjectName(spinbox_name)
        layout.addWidget(spinbox)

        self.deviceParamsLayout.addLayout(layout)
        setattr(self, label_name, label)
        setattr(self, spinbox_name, spinbox)

    def _setup_config_tabs(self):
        """Setup configuration tab widget"""
        self.configTabWidget = QtWidgets.QTabWidget(self.channelConfigGroup)
        self.configTabWidget.setGeometry(QtCore.QRect(10, 110, 1140, 595))
        self.configTabWidget.setCurrentIndex(0)
        self.configTabWidget.setObjectName("configTabWidget")

        # Initial placeholder tabs - will be customized by UIManager
        self._create_placeholder_tabs()

    def _create_placeholder_tabs(self):
        """Create placeholder tabs that will be customized later"""
        # Brain tab placeholder
        self.brainTab = QtWidgets.QWidget()
        self.brainTab.setObjectName("brainTab")
        self.configTabWidget.addTab(self.brainTab, "Brain Configuration")

        # Trunk tab placeholder  
        self.trunkTab = QtWidgets.QWidget()
        self.trunkTab.setObjectName("trunkTab")
        self.configTabWidget.addTab(self.trunkTab, "Trunk Configuration")

        # Empty third tab
        self.emptyTab = QtWidgets.QWidget()
        self.emptyTab.setObjectName("emptyTab")
        self.configTabWidget.addTab(self.emptyTab, "")

    def retranslateUi(self, ConfigForm):
        _translate = QtCore.QCoreApplication.translate
        ConfigForm.setWindowTitle(_translate("ConfigForm", "Device Configuration"))
        self.samplingRateGroup.setTitle(_translate("ConfigForm", "采样率配置"))
        self.channelConfigGroup.setTitle(_translate("ConfigForm", "通道配置"))


class UIManager:
    """Manages UI operations and customization"""
    
    def __init__(self, parent):
        self.parent = parent
        logger.info("UIManager initialized")

    def setup_ui_for_sensors(self, enabled_sensor_types: Set[str]):
        """Customize UI to show only enabled sensor controls"""
        logger.info("Setting up UI for enabled sensors")
        
        # Show/hide controls based on enabled sensors
        for control_type, mappings in UIConstants.SENSOR_CONTROL_MAPPINGS.items():
            for sensor, controls in mappings.items():
                visible = sensor in enabled_sensor_types
                for control_name in controls:
                    if hasattr(self.parent, control_name):
                        getattr(self.parent, control_name).setVisible(visible)
        
        self._customize_tab_widget(enabled_sensor_types)
        logger.debug("UI setup for sensors completed")

    def _customize_tab_widget(self, enabled_sensor_types: Set[str]):
        """Customize tab widget based on sensor associations"""
        if not hasattr(self.parent, 'configTabWidget'):
            return
        
        # Clear existing tabs
        while self.parent.configTabWidget.count() > 0:
            self.parent.configTabWidget.removeTab(0)
        
        # Add tabs based on enabled sensors
        brain_sensors = {'eeg', 'fnirs'}
        if brain_sensors.intersection(enabled_sensor_types):
            self._add_brain_configuration_tab(enabled_sensor_types)
        
        if 'semg' in enabled_sensor_types:
            self._add_trunk_configuration_tab()
        
        if self.parent.configTabWidget.count() == 0:
            self._add_placeholder_tab()

    def _add_brain_configuration_tab(self, enabled_sensor_types: Set[str]):
        """Add Brain Configuration tab for EEG and fNIRS"""
        try:
            self.parent.brainTab = QtWidgets.QWidget()
            self.parent.brainTab.setObjectName("brainTab")
            self.parent.configTabWidget.addTab(self.parent.brainTab, "脑部配置")

            # Create scroll area
            self.parent.brainScrollArea = QtWidgets.QScrollArea(self.parent.brainTab)
            self.parent.brainScrollArea.setGeometry(QtCore.QRect(5, 5, 560, 560))
            self.parent.brainScrollArea.setWidgetResizable(True)

            self.parent.brainScrollWidget = QtWidgets.QWidget()
            self.parent.brainScrollArea.setWidget(self.parent.brainScrollWidget)

            self.parent.brainMainLayout = QtWidgets.QVBoxLayout(self.parent.brainScrollWidget)

            # Add sensor sections
            if 'eeg' in enabled_sensor_types:
                self._add_sensor_group_box("EEG", "EEG通道配置", UIConstants.SENSOR_COLORS['eeg'])
            
            if 'fnirs' in enabled_sensor_types:
                self._add_fnirs_section()
            
            self._add_brain_locator_widget()
            
            logger.debug("Brain configuration tab created successfully")
        except Exception as e:
            logger.error(f"Failed to create brain configuration tab: {e}")
            raise

    def _add_sensor_group_box(self, sensor_key: str, title: str, color: str):
        """Add a generic sensor group box"""
        group_box = QGroupBox(title)
        group_box.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {color}; }}")
        
        grid_layout = QtWidgets.QGridLayout(group_box)
        setattr(self.parent, f"{sensor_key.lower()}GroupBox", group_box)
        setattr(self.parent, f"{sensor_key.lower()}GridLayout", grid_layout)
        
        self.parent.brainMainLayout.addWidget(group_box)

    def _add_fnirs_section(self):
        """Add fNIRS section to brain configuration tab"""
        self.parent.fnirsGroupBox = QGroupBox("fNIRS通道配置")
        self.parent.fnirsGroupBox.setStyleSheet("QGroupBox { font-weight: bold; color: #E91E63; }")
        
        self.parent.fnirsMainLayout = QtWidgets.QVBoxLayout(self.parent.fnirsGroupBox)
        self.parent.fnirsGridLayout = QtWidgets.QGridLayout()
        self.parent.fnirsMainLayout.addLayout(self.parent.fnirsGridLayout)
        
        self.parent.brainMainLayout.addWidget(self.parent.fnirsGroupBox)

    def _add_brain_locator_widget(self):
        """Add brain electrode locator widget"""
        try:
            self.parent.brain_config_right = locate.Locate() # type: ignore
            self.parent.brain_config_right.setParent(self.parent.brainTab)
            self.parent.brain_config_right.setGeometry(QtCore.QRect(570, 5, 560, 560))
        except Exception as e:
            logger.error(f"Failed to add brain locator widget: {e}")
            self._create_placeholder_locator_widget()

    def _create_placeholder_locator_widget(self):
        """Create placeholder widget when locator is unavailable"""
        self.parent.brain_config_right = QtWidgets.QWidget(self.parent.brainTab)
        self.parent.brain_config_right.setGeometry(QtCore.QRect(570, 5, 560, 560))
        layout = QVBoxLayout(self.parent.brain_config_right)
        layout.addWidget(QLabel("Locator not available"))

    def _add_trunk_configuration_tab(self):
        """Add Trunk Configuration tab for sEMG"""
        try:
            self.parent.trunkTab = QtWidgets.QWidget()
            self.parent.trunkTab.setObjectName("trunkTab")
            self.parent.configTabWidget.addTab(self.parent.trunkTab, "躯干配置")

            # Create scroll area and content
            self.parent.trunkScrollArea = QtWidgets.QScrollArea(self.parent.trunkTab)
            self.parent.trunkScrollArea.setGeometry(QtCore.QRect(5, 5, 560, 560))
            self.parent.trunkScrollArea.setWidgetResizable(True)

            self.parent.trunkScrollWidget = QtWidgets.QWidget()
            self.parent.trunkScrollArea.setWidget(self.parent.trunkScrollWidget)

            # Add sEMG group box
            self.parent.semgGroupBox = QGroupBox("sEMG通道配置")
            self.parent.semgGroupBox.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {UIConstants.SENSOR_COLORS['semg']}; }}")
            
            self.parent.semgGridLayout = QtWidgets.QGridLayout(self.parent.semgGroupBox)
            
            layout = QVBoxLayout(self.parent.trunkScrollWidget)
            layout.addWidget(self.parent.semgGroupBox)
            layout.addStretch()
            
            # Right widget placeholder
            self.parent.widget_trunk_right = QtWidgets.QWidget(self.parent.trunkTab)
            self.parent.widget_trunk_right.setGeometry(QtCore.QRect(570, 5, 560, 560))
            
        except Exception as e:
            logger.error(f"Failed to create trunk configuration tab: {e}")
            raise

    def _add_placeholder_tab(self):
        """Add placeholder tab when no sensors are configured"""
        placeholder_tab = QtWidgets.QWidget()
        placeholder_label = QLabel("No sensor types enabled for configuration")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(placeholder_tab)
        layout.addWidget(placeholder_label)
        self.parent.configTabWidget.addTab(placeholder_tab, "No Configuration")

    def initialize_ui_values(self, config):
        """Initialize UI with default values"""
        try:
            self._initialize_sampling_rates(config)
            self._initialize_channel_counts(config)
            logger.info("UI values initialization completed")
        except Exception as e:
            logger.error(f"UI values initialization failed: {e}")
            raise

    def _initialize_sampling_rates(self, config):
        """Initialize sampling rate controls"""
        for sensor, control_name in [
            ('eeg', 'eegSamplingCombo'),
            ('fnirs', 'fnirsSamplingCombo'),
            ('semg', 'semgSamplingCombo')
        ]:
            if sensor in config.enabled_sensors and hasattr(self.parent, control_name):
                control = getattr(self.parent, control_name)
                rate = config.sampling_rates[sensor]
                control.setCurrentText(str(rate))
                control.currentIndexChanged.connect(self.parent.modify_sample_rate)

    def _initialize_channel_counts(self, config):
        """Initialize channel count controls"""
        channel_controls = [
            ('eeg', 'eegChannelsSpinBox_2'),
            ('semg', 'semgChannelsSpinBox_2')
        ]
        
        for sensor, control_name in channel_controls:
            if sensor in config.enabled_sensors and hasattr(self.parent, control_name):
                control = getattr(self.parent, control_name)
                count = config.channel_counts[sensor]
                control.setValue(count)
        
        # fNIRS special handling
        if 'fnirs' in config.enabled_sensors:
            fnirs_controls = [
                ('fnirsSourcesSpinBox_2', 'fnirs_sources'),
                ('fnirsDetectorsSpinBox_2', 'fnirs_detectors')
            ]
            for control_name, count_key in fnirs_controls:
                if hasattr(self.parent, control_name):
                    control = getattr(self.parent, control_name)
                    control.setValue(config.channel_counts[count_key])

    def connect_controls(self, config, parent):
        """Connect control signals"""
        self._connect_channel_controls(config, parent)

    def _connect_channel_controls(self, config, parent):
        """Connect channel control signals"""
        channel_controls = {
            'eeg': 'eegChannelsSpinBox_2',
            'semg': 'semgChannelsSpinBox_2'
        }
        
        for sensor, control_name in channel_controls.items():
            if sensor in config.enabled_sensors and hasattr(parent, control_name):
                getattr(parent, control_name).valueChanged.connect(
                    lambda sensor=sensor: parent._safe_update_channel_configuration(sensor))
        
        # fNIRS special handling
        if 'fnirs' in config.enabled_sensors:
            for control_name in ['fnirsSourcesSpinBox_2', 'fnirsDetectorsSpinBox_2']:
                if hasattr(parent, control_name):
                    getattr(parent, control_name).valueChanged.connect(
                        lambda: parent._safe_update_channel_configuration('fnirs'))

    def update_channel_counts_from_ui(self, config):
        """Update channel counts from UI spinboxes"""
        try:
            channel_mappings = [
                ('eeg', 'eegChannelsSpinBox_2'),
                ('semg', 'semgChannelsSpinBox_2')
            ]
            
            for sensor, control_name in channel_mappings:
                if sensor in config.enabled_sensors and hasattr(self.parent, control_name):
                    config.channel_counts[sensor] = getattr(self.parent, control_name).value()
            
            # fNIRS special handling
            if 'fnirs' in config.enabled_sensors:
                fnirs_mappings = [
                    ('fnirsSourcesSpinBox_2', 'fnirs_sources'),
                    ('fnirsDetectorsSpinBox_2', 'fnirs_detectors')
                ]
                for control_name, count_key in fnirs_mappings:
                    if hasattr(self.parent, control_name):
                        config.channel_counts[count_key] = getattr(self.parent, control_name).value()
                        
        except Exception as e:
            logger.error(f"Failed to update channel counts from UI: {e}")
            raise

    def add_control_buttons(self, enabled_sensor_types: Set[str], parent):
        """Add control buttons for brain configuration"""
        try:
            brain_sensors = {'eeg', 'fnirs'}
            if brain_sensors.intersection(enabled_sensor_types) and hasattr(parent, 'brainTab'):
                self._add_brain_control_buttons(parent)
        except Exception as e:
            logger.error(f"Failed to add control buttons: {e}")

    def _add_brain_control_buttons(self, parent):
        """Add control buttons for brain configuration"""
        try:
            if not hasattr(parent, 'brainTab') or not hasattr(parent, 'brain_config_right'):
                logger.warning("Brain tab or config widget not available")
                return
            
            self._remove_existing_control_buttons(parent)
            
            # Create buttons with common styling
            button_configs = [
                ('reset_locator_btn', '重置', '#f44336', self._get_reset_callback(parent)),
                ('finish_locator_btn', '完成', '#4CAF50', self._get_finish_callback(parent))
            ]
            
            parent_width = parent.brainTab.width() if parent.brainTab.width() > 0 else 1140
            
            for i, (name, text, color, callback) in enumerate(button_configs):
                button = QtWidgets.QPushButton(parent.brainTab)
                button.setObjectName(name)
                button.setText(text)
                button.setStyleSheet(self._get_button_style(color))
                
                # Position buttons
                x_pos = min(parent_width - (180 - i * 90), 580 + i * 90)
                button.setGeometry(QtCore.QRect(x_pos, 10, 80, 30))
                
                button.clicked.connect(callback)
                button.show()
                button.raise_()
                
                setattr(parent, name, button)
                logger.info(f"Created {name} at position ({x_pos}, 10)")
            
            if hasattr(parent.brainTab, 'update'):
                parent.brainTab.update()
                
        except Exception as e:
            logger.error(f"Failed to add brain control buttons: {e}")

    def _get_button_style(self, color: str) -> str:
        """Get button style string"""
        return f"""
            QPushButton {{ 
                background-color: {color}; 
                color: white; 
                border: none; 
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{ 
                background-color: {self._darken_color(color)}; 
            }}
            QPushButton:pressed {{ 
                background-color: {self._darken_color(color, 0.8)}; 
            }}
        """

    def _darken_color(self, hex_color: str, factor: float = 0.9) -> str:
        """Darken a hex color by a factor"""
        try:
            hex_color = hex_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            darkened = tuple(int(c * factor) for c in rgb)
            return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"
        except:
            return hex_color

    def _get_reset_callback(self, parent):
        """Get reset button callback"""
        if hasattr(parent, 'brain_config_right') and hasattr(parent.brain_config_right, 'reset_all_electrodes'):
            return parent.brain_config_right.reset_all_electrodes
        return self._fallback_reset_electrodes

    def _get_finish_callback(self, parent):
        """Get finish button callback"""
        if hasattr(parent, 'brain_config_right') and hasattr(parent.brain_config_right, 'get_channel_pairs_summary'):
            return lambda: self._get_config_summary(parent)
        return lambda: self._fallback_show_summary(parent)

    def _get_config_summary(self, parent):
        """Get configuration summary from brain locator"""
        parent.brain_config_right.get_channel_pairs_summary()
        
        if hasattr(parent.brain_config_right, 'get_sources'):
            source_config = parent.brain_config_right.get_sources()
            parent.config.enabled_channels['fnirs' + 'source'] = source_config
        
        if hasattr(parent.brain_config_right, 'get_detectors'):
            detect_config = parent.brain_config_right.get_detectors()
            parent.config.enabled_channels['fnirs' + 'detect'] = detect_config
        
        if hasattr(parent.brain_config_right, 'get_fnirs_pairs'):
            fnirs_config = parent.brain_config_right.get_fnirs_pairs()
            parent.config.enabled_channels['fnirs'] = fnirs_config
                
        if hasattr(parent.brain_config_right, 'get_eeg_electrodes'):
            eeg_config = parent.brain_config_right.get_eeg_electrodes()
            parent.config.enabled_channels['eeg'] = eeg_config

    def _remove_existing_control_buttons(self, parent):
        """Remove existing control buttons to prevent duplicates"""
        for button_name in ['reset_locator_btn', 'finish_locator_btn']:
            if hasattr(parent, button_name):
                button = getattr(parent, button_name)
                if button is not None:
                    button.deleteLater()
                    setattr(parent, button_name, None)

    def _fallback_reset_electrodes(self):
        """Fallback method for reset functionality"""
        try:
            logger.info("Executing fallback reset electrode functionality")
            
            # Clear checkbox selections
            checkbox_groups = ['Source', 'Detect'] + list(self.parent.enabled_sensor_types)
            for group in checkbox_groups:
                if group in self.parent.sensor_checkboxes:
                    for checkbox in self.parent.sensor_checkboxes[group]:
                        checkbox.setChecked(False)
            
            self.parent._show_info_message("Reset Complete", "电极配置已重置")
            
        except Exception as e:
            logger.error(f"Fallback reset failed: {e}")
            self.parent._show_error_message("Reset Failed", f"重置失败：{str(e)}")

    def _fallback_show_summary(self, parent):
        """Fallback method for showing summary"""
        try:
            summary = parent.get_channel_summary()
            msg = QtWidgets.QMessageBox(parent)
            msg.setWindowTitle("Channel Configuration Summary")
            msg.setText("通道配置摘要")
            msg.setDetailedText(summary)
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.exec_()
        except Exception as e:
            logger.error(f"Fallback summary failed: {e}")
            parent._show_error_message("Summary Failed", f"显示摘要失败：{str(e)}")

    def generate_standard_sensor_config(self, sensor_type: str, config, sensor_checkboxes: Dict, parent):
        """Generate standard sensor configuration (EEG/sEMG)"""
        logger.info(f"Generating {sensor_type} configuration")
        
        try:
            layout_name = f"{sensor_type}GridLayout"
            if not hasattr(parent, layout_name):
                logger.warning(f"{sensor_type} grid layout not available")
                return
            
            layout = getattr(parent, layout_name)
            self._clear_layout(layout)
            sensor_checkboxes[sensor_type].clear()
            
            sensor_config = config.sensor_configs[sensor_type]
            channel_count = config.channel_counts[sensor_type]
            
            for i in range(channel_count):
                row, col = divmod(i, sensor_config.channels_per_row)
                
                checkbox = QCheckBox(f"{sensor_config.prefix}{i+1:02d}")
                checkbox.setStyleSheet(f"QCheckBox {{ color: {sensor_config.color}; font-weight: bold; }}")
                checkbox.stateChanged.connect(
                    lambda state, idx=i: parent.update_sensor_channels(sensor_type, idx, state))
                
                layout.addWidget(checkbox, row, col)
                sensor_checkboxes[sensor_type].append(checkbox)
            
            logger.info(f"Generated {channel_count} {sensor_type} channel checkboxes")
            
        except Exception as e:
            logger.error(f"Failed to generate {sensor_type} configuration: {e}")
            raise

    def generate_fnirs_configuration(self, config, sensor_checkboxes: Dict, parent):
        """Generate fNIRS source-detector matrix configuration"""
        logger.info("Generating fNIRS configuration")
        
        try:
            if not hasattr(parent, 'fnirsGridLayout'):
                logger.warning("fNIRS grid layout not available")
                return
            
            self._clear_layout(parent.fnirsGridLayout)
            sensor_checkboxes['Source'].clear()
            sensor_checkboxes['Detect'].clear()
            
            # Update counts from UI
            self._update_fnirs_counts_from_ui(config, parent)
            
            sensor_config = config.sensor_configs['fnirs']
            source_count = config.channel_counts['fnirs_sources']
            detector_count = config.channel_counts['fnirs_detectors']
            
            # Generate sources and detectors
            self._generate_fnirs_components('Source', source_count, sensor_config, 0, sensor_checkboxes, parent)
            source_rows = int(np.ceil(source_count / sensor_config.channels_per_row))
            self._generate_fnirs_components('Detect', detector_count, sensor_config, source_rows, sensor_checkboxes, parent)
            
            logger.info(f"Generated {source_count} source and {detector_count} detector checkboxes")
            
        except Exception as e:
            logger.error(f"Failed to generate fNIRS configuration: {e}")
            raise

    def _update_fnirs_counts_from_ui(self, config, parent):
        """Update fNIRS counts from UI"""
        if 'fnirs' in config.enabled_sensors:
            for control_name, count_key in [
                ('fnirsSourcesSpinBox_2', 'fnirs_sources'),
                ('fnirsDetectorsSpinBox_2', 'fnirs_detectors')
            ]:
                if hasattr(parent, control_name):
                    config.channel_counts[count_key] = getattr(parent, control_name).value()

    def _generate_fnirs_components(self, component_type: str, count: int, sensor_config, row_offset: int, sensor_checkboxes: Dict, parent):
        """Generate fNIRS components (sources or detectors)"""
        color_idx = 0 if component_type == 'Source' else 1
        prefix_idx = 0 if component_type == 'Source' else 1
        
        for i in range(count):
            row = i // sensor_config.channels_per_row + row_offset
            col = i % sensor_config.channels_per_row
            
            checkbox = QCheckBox(f"{sensor_config.prefix[prefix_idx]}{i+1:02d}")
            checkbox.setStyleSheet(f"QCheckBox {{ color: {sensor_config.color[color_idx]}; font-weight: bold; }}")
            checkbox.stateChanged.connect(
                lambda state, idx=i: parent.update_sensor_channels(component_type, idx, state))
            
            parent.fnirsGridLayout.addWidget(checkbox, row, col)
            sensor_checkboxes[component_type].append(checkbox)

    def _clear_layout(self, layout):
        """Clear all widgets from a layout"""
        try:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        except Exception as e:
            logger.error(f"Failed to clear layout: {e}")

    def process_sensor_configurations(self, enabled_sensor_types: Set[str], operation_type: str):
        """Generic method to process sensor configurations"""
        updated_sensors = []
        sensor_id_map = {
            'eeg': 1,
            'semg': 2,
            'fnirs': 4
        }
        
        for sensor_type in enabled_sensor_types:
            if sensor_type not in UIConstants.SAMPLING_CONFIG:
                continue
                
            config = UIConstants.SAMPLING_CONFIG[sensor_type]
            control_name = config['control']
            valid_rates = config['rates']
            
            if not hasattr(self.parent, control_name):
                continue
                
            try:
                control = getattr(self.parent, control_name)
                rate = int(control.currentText())
                
                if rate not in valid_rates:
                    raise ValueError(f"Rate {rate}Hz not in allowed rates {valid_rates}")
                
                updated_sensors.extend([
                    sensor_id_map[sensor_type],
                    valid_rates.index(rate) + 1
                ])
                
                logger.info(f"Updated {sensor_type} {operation_type} to {rate}Hz")
                
            except (ValueError, AttributeError) as e:
                raise ValueError(f"Invalid {operation_type} for {sensor_type}: {e}")
        print(f"sample rate data done: len {len(updated_sensors)}")
        return updated_sensors

    def modify_sample_rate(self, config, enabled_sensor_types: Set[str]):
        """Update sampling rates from UI controls"""
        sampling_controls = [
            ('eeg', 'eegSamplingCombo'),
            ('semg', 'semgSamplingCombo'),
            ('fnirs', 'fnirsSamplingCombo')
        ]
        
        for sensor, control_name in sampling_controls:
            if sensor in enabled_sensor_types and hasattr(self.parent, control_name):
                control = getattr(self.parent, control_name)
                config.sampling_rates[sensor] = int(control.currentText())

    def apply_loaded_configuration(self, config_dict: Dict[str, Any], config, enabled_sensor_types: Set[str]):
        """Apply loaded configuration to UI"""
        logger.info("Applying loaded configuration")
        
        try:
            config_sections = [
                ('sampling_rates', self._apply_loaded_sampling_rates),
                ('channel_counts', self._apply_loaded_channel_counts),
                ('enabled_channels', self._apply_loaded_enabled_channels)
            ]
            
            for section_key, apply_method in config_sections:
                if section_key in config_dict:
                    apply_method(config_dict[section_key], config, enabled_sensor_types)
            
            self._apply_loaded_electrode_positions(config_dict['enabled_channels'])
            
        except Exception as e:
            logger.error(f"Failed to apply loaded configuration: {e}")
            raise

    def _apply_loaded_sampling_rates(self, sampling_rates: Dict[str, int], config, enabled_sensor_types: Set[str]):
        """Apply loaded sampling rates"""
        sampling_controls = {
            'eeg': 'eegSamplingCombo',
            'fnirs': 'fnirsSamplingCombo',
            'semg': 'semgSamplingCombo'
        }
        
        for sensor in enabled_sensor_types:
            if sensor in sampling_rates and sensor in sampling_controls:
                control_name = sampling_controls[sensor]
                if hasattr(self.parent, control_name):
                    try:
                        control = getattr(self.parent, control_name)
                        control.setCurrentText(str(sampling_rates[sensor]))
                        config.sampling_rates[sensor] = sampling_rates[sensor]
                    except Exception as e:
                        logger.warning(f"Failed to set {sensor} sampling rate: {e}")

    def _apply_loaded_channel_counts(self, channel_counts: Dict[str, int], config, enabled_sensor_types: Set[str]):
        """Apply loaded channel counts"""
        try:
            # Standard sensors
            channel_mappings = [
                ('eeg', 'eegChannelsSpinBox_2'),
                ('semg', 'semgChannelsSpinBox_2')
            ]
            
            for sensor, control_name in channel_mappings:
                if (sensor in enabled_sensor_types and 
                    sensor in channel_counts and hasattr(self.parent, control_name)):
                    getattr(self.parent, control_name).setValue(channel_counts[sensor])
                    config.channel_counts[sensor] = channel_counts[sensor]
            
            # fNIRS special handling
            if 'fnirs' in enabled_sensor_types:
                fnirs_mappings = [
                    ('fnirs_sources', 'fnirsSourcesSpinBox_2'),
                    ('fnirs_detectors', 'fnirsDetectorsSpinBox_2')
                ]
                
                for count_key, control_name in fnirs_mappings:
                    if count_key in channel_counts and hasattr(self.parent, control_name):
                        getattr(self.parent, control_name).setValue(channel_counts[count_key])
                        config.channel_counts[count_key] = channel_counts[count_key]
                        
        except Exception as e:
            logger.error(f"Failed to apply loaded channel counts: {e}")
            raise

    def _apply_loaded_enabled_channels(self, enabled_channels: Dict[str, Any], config, enabled_sensor_types: Set[str]):
        """Apply loaded enabled channels - 修复版本"""
        try:
            logger.info(f"Applying loaded enabled channels: {list(enabled_channels.keys())}")
            
            # 首先直接将数据保存到config中 - 这是关键修复
            for key, value in enabled_channels.items():
                config.enabled_channels[key] = value
                logger.debug(f"Loaded enabled channels for {key}: {type(value)} with {len(value) if hasattr(value, '__len__') else 'N/A'} items")
            
            # 然后应用到UI（如果checkboxes存在的话）
            for sensor in enabled_sensor_types:
                if sensor in enabled_channels and hasattr(self.parent, 'sensor_checkboxes') and sensor in self.parent.sensor_checkboxes:
                    self._apply_sensor_channels_to_ui(sensor, enabled_channels[sensor])
            
            # 处理fNIRS特殊组件
            if 'fnirs' in enabled_sensor_types:
                fnirs_mappings = [
                    ('fnirssource', 'Source'),
                    ('fnirsdetect', 'Detect')
                ]
                
                for key, checkbox_key in fnirs_mappings:
                    if (key in enabled_channels and 
                        hasattr(self.parent, 'sensor_checkboxes') and 
                        checkbox_key in self.parent.sensor_checkboxes):
                        channels = enabled_channels[key]
                        self._apply_fnirs_channels_to_ui(checkbox_key, channels)
            
            logger.info(f"Successfully applied loaded enabled channels to config and UI")
            
        except Exception as e:
            logger.error(f"Failed to apply loaded enabled channels: {e}")
            raise

    def _apply_sensor_channels_to_ui(self, sensor: str, sensor_channels: Union[List, Dict, Any]):
        """Apply sensor channels to UI checkboxes"""
        try:
            if not hasattr(self.parent, 'sensor_checkboxes') or sensor not in self.parent.sensor_checkboxes:
                logger.warning(f"No checkboxes found for sensor {sensor}")
                return
            
            checkboxes = self.parent.sensor_checkboxes[sensor]
            
            # Clear all checkboxes first
            for checkbox in checkboxes:
                checkbox.setChecked(False)
            
            if isinstance(sensor_channels, list):
                # For list of channel indices
                for channel_idx in sensor_channels:
                    if isinstance(channel_idx, int) and 0 <= channel_idx < len(checkboxes):
                        checkboxes[channel_idx].setChecked(True)
                        
            elif isinstance(sensor_channels, dict):
                # For dictionary format (like channel pairs)
                for key in sensor_channels.keys():
                    try:
                        if isinstance(key, str) and key.isdigit():
                            channel_idx = int(key) - 1  # Convert to 0-based index
                            if 0 <= channel_idx < len(checkboxes):
                                checkboxes[channel_idx].setChecked(True)
                        elif isinstance(key, int):
                            if 0 <= key < len(checkboxes):
                                checkboxes[key].setChecked(True)
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to apply channel {key} for {sensor}: {e}")
                        
            logger.debug(f"Applied {sensor} channels to UI checkboxes")
                        
        except Exception as e:
            logger.error(f"Failed to apply {sensor} channels to UI: {e}")

    def _apply_fnirs_channels_to_ui(self, checkbox_key: str, channels):
        """Apply fNIRS channels to UI checkboxes"""
        try:
            if not hasattr(self.parent, 'sensor_checkboxes') or checkbox_key not in self.parent.sensor_checkboxes:
                logger.warning(f"No checkboxes found for {checkbox_key}")
                return
            
            checkboxes = self.parent.sensor_checkboxes[checkbox_key]
            
            # Clear all first
            for checkbox in checkboxes:
                checkbox.setChecked(False)
            
            # Apply channels
            if isinstance(channels, (list, tuple)):
                for i, should_enable in enumerate(channels):
                    if i < len(checkboxes) and should_enable:
                        checkboxes[i].setChecked(True)
            elif isinstance(channels, dict):
                for key in channels.keys():
                    try:
                        if isinstance(key, str) and key.isdigit():
                            idx = int(key) - 1
                            if 0 <= idx < len(checkboxes):
                                checkboxes[idx].setChecked(True)
                    except (ValueError, IndexError):
                        continue
                        
            logger.debug(f"Applied {checkbox_key} channels to UI")
            
        except Exception as e:
            logger.error(f"Failed to apply {checkbox_key} channels to UI: {e}")

    def _apply_sensor_channels(self, sensor: str, sensor_channels: List[int]):
        """Apply enabled channels for a specific sensor"""
        if isinstance(sensor_channels, list):
            checkboxes = self.parent.sensor_checkboxes[sensor]
            for i in range(len(sensor_channels)):
                if i < len(checkboxes):
                    checkboxes[i].setChecked(True)

    def _apply_loaded_electrode_positions(self, enabled_channels: Dict[str, Any]):
        """Apply loaded electrode positions to the locator"""
        if not hasattr(self.parent, 'brain_config_right'):
            return
        
        try:
            if hasattr(self.parent.brain_config_right, 'load_pairs_info'):
                self.parent.brain_config_right.load_pairs_info(enabled_channels)
                logger.info("Applied electrode positions from loaded configuration")
        except Exception as e:
            logger.error(f"Failed to apply electrode positions: {e}")

    def clear_all_configurations(self, sensor_checkboxes: Dict):
        """Clear all sensor configurations"""
        # Clear layouts
        layout_mappings = {
            'eeg': 'eegGridLayout',
            'semg': 'semgGridLayout',
            'fnirs': 'fnirsGridLayout'
        }
        
        for sensor, layout_name in layout_mappings.items():
            if hasattr(self.parent, layout_name):
                self._clear_layout(getattr(self.parent, layout_name))
        
        # Clear checkbox references
        for sensor_type in sensor_checkboxes:
            sensor_checkboxes[sensor_type].clear()


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    ConfigForm = QtWidgets.QWidget()
    ui = Ui_ConfigForm()
    ui.setupUi(ConfigForm)
    ConfigForm.show()
    sys.exit(app.exec_())
# -*- coding: utf-8 -*-

"""
Optimized Device Configuration Management System
Handles EEG, sEMG, and fNIRS device configuration with improved error handling and logging
"""

import sys
import json
import os
from typing import List, Dict, Set, Any, Optional, Tuple, Union, Callable
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import traceback

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (QApplication, QWidget, QCheckBox, QLabel, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QMessageBox, QFileDialog, QGroupBox)
from PyQt5.QtCore import Qt, pyqtSignal
import numpy as np

# Configure comprehensive logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('device_config.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import UI and locate modules with error handling
try:
    from ui_config import Ui_ConfigForm # type: ignore
    logger.info("Successfully imported ui_config module")
except ImportError as e:
    logger.error(f"Failed to import ui_config: {e}")
    class Ui_ConfigForm:
        def setupUi(self, widget): pass

try:
    import locate # pyright: ignore[reportAssignmentType]
    logger.info("Successfully imported locate module")
except ImportError as e:
    logger.error(f"Failed to import locate module: {e}")
    class locate:
        class Locate(QtWidgets.QWidget):
            def __init__(self): super().__init__()


class SensorTypes:
    """Define sensor types as bit flags"""
    NotInit = 0
    EEG = 1
    SEMG = 2
    EEG_SEMG = 3
    FNIRS = 4
    EEG_FNIRS = 5
    SEMG_FNIRS = 6
    EEG_SEMG_FNIRS = 7


class SensorType(Enum):
    """Enum for sensor types with validation"""
    EEG = "eeg"
    SEMG = "semg" 
    FNIRS = "fnirs"
    
    @classmethod
    def get_all_types(cls) -> List[str]:
        return [sensor.value for sensor in cls]
    
    @classmethod
    def validate_sensor_type(cls, sensor_type: str) -> bool:
        return sensor_type in cls.get_all_types()


@dataclass
class SensorConfig:
    """Configuration for individual sensor types"""
    color: Union[str, List[str]]
    prefix: Union[str, List[str]]
    max_channels: int
    min_channels: int
    channels_per_row: int
    max_sources: Optional[int] = None
    max_detectors: Optional[int] = None
    min_sources: Optional[int] = None
    min_detectors: Optional[int] = None


@dataclass
class DeviceConfiguration:
    """Enhanced data class for device configuration with validation"""
    enabled_sensors: Set[str] = field(default_factory=set)
    sampling_rates: Dict[str, int] = field(default_factory=dict)
    channel_counts: Dict[str, int] = field(default_factory=dict)
    enabled_channels: Dict[str, Union[List[int], Dict]] = field(default_factory=dict)
    enabled_channel_pairs: Dict[str, Dict] = field(default_factory=dict)
    current_checkbox: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize configuration after object creation"""
        logger.info(f"Initializing DeviceConfiguration with sensors: {self.enabled_sensors}")
        self._initialize_sensor_configs()
        self._initialize_default_settings()
    
    def _initialize_sensor_configs(self):
        """Initialize sensor-specific configurations"""
        self.sensor_configs = {
            SensorType.EEG.value: SensorConfig(
                color='#2196F3', prefix='EEG', max_channels=64, min_channels=1, channels_per_row=8
            ),
            SensorType.SEMG.value: SensorConfig(
                color='#FF9800', prefix='EMG', max_channels=16, min_channels=1, channels_per_row=4
            ),
            SensorType.FNIRS.value: SensorConfig(
                color=['#E91E63', '#1040ff'], prefix=['S', 'D'], max_channels=0, min_channels=0,
                channels_per_row=8, max_sources=32, max_detectors=32, min_sources=1, min_detectors=1
            )
        }
        logger.debug("Sensor configurations initialized")
    
    def _initialize_default_settings(self):
        """Initialize default sampling rates and channel counts"""
        defaults = {
            'sampling_rates': {
                SensorType.EEG.value: 1000,
                SensorType.FNIRS.value: 10,
                SensorType.SEMG.value: 1000
            },
            'channel_counts': {
                SensorType.EEG.value: 32,
                SensorType.SEMG.value: 8,
                'fnirs_sources': 16,
                'fnirs_detectors': 16
            }
        }
        
        for sensor in self.enabled_sensors:
            if sensor in defaults['sampling_rates']:
                self.sampling_rates[sensor] = defaults['sampling_rates'][sensor]
                logger.debug(f"Set default sampling rate for {sensor}: {defaults['sampling_rates'][sensor]}")
            
            if sensor == SensorType.FNIRS.value:
                self.channel_counts.update({
                    'fnirs_sources': defaults['channel_counts']['fnirs_sources'],
                    'fnirs_detectors': defaults['channel_counts']['fnirs_detectors']
                })
                self.enabled_channels.update({
                    sensor: {},
                    sensor + 'source': [],
                    sensor + 'detect': []
                })
            else:
                if sensor in defaults['channel_counts']:
                    self.channel_counts[sensor] = defaults['channel_counts'][sensor]
                self.enabled_channels[sensor] = []
            
            self.enabled_channel_pairs[sensor] = {}
    
    def validate_configuration(self) -> Dict[str, List[str]]:
        """Validate current configuration and return any issues"""
        errors, warnings = [], []
        
        try:
            # Validate sampling rates
            for sensor, rate in self.sampling_rates.items():
                if not isinstance(rate, int) or rate <= 0:
                    errors.append(f"Invalid sampling rate for {sensor}: {rate}")
                elif sensor == SensorType.FNIRS.value and rate > 100:
                    warnings.append(f"High fNIRS sampling rate: {rate} Hz")
            
            # Validate channel counts
            for sensor in self.enabled_sensors:
                config = self.sensor_configs.get(sensor)
                if not config:
                    continue
                
                if sensor == SensorType.FNIRS.value:
                    for component, key in [('sources', 'fnirs_sources'), ('detectors', 'fnirs_detectors')]:
                        count = self.channel_counts.get(key, 0)
                        min_val = getattr(config, f'min_{component}')
                        max_val = getattr(config, f'max_{component}')
                        if count < min_val or count > max_val:
                            errors.append(f"fNIRS {component} out of range: {count} (valid: {min_val}-{max_val})")
                else:
                    count = self.channel_counts.get(sensor, 0)
                    if count < config.min_channels or count > config.max_channels:
                        errors.append(f"{sensor.upper()} channels out of range: {count} (valid: {config.min_channels}-{config.max_channels})")
            
            logger.info(f"Configuration validation complete: {len(errors)} errors, {len(warnings)} warnings")
            
        except Exception as e:
            logger.error(f"Error during configuration validation: {e}")
            errors.append(f"Validation error: {str(e)}")
        
        return {'errors': errors, 'warnings': warnings}


class UIConstants:
    """Constants for UI configuration"""
    SENSOR_CONTROL_MAPPINGS = {
        'sampling': {
            SensorType.EEG.value: ['eegSamplingLabel', 'eegSamplingCombo'],
            SensorType.FNIRS.value: ['fnirsSamplingLabel', 'fnirsSamplingCombo'],
            SensorType.SEMG.value: ['semgSamplingLabel', 'semgSamplingCombo']
        },
        'channels': {
            SensorType.EEG.value: ['eegChannelsLabel_2', 'eegChannelsSpinBox_2'],
            SensorType.SEMG.value: ['semgChannelsLabel_2', 'semgChannelsSpinBox_2'],
            SensorType.FNIRS.value: ['fnirsSourcesLabel_2', 'fnirsSourcesSpinBox_2', 
                                   'fnirsDetectorsLabel_2', 'fnirsDetectorsSpinBox_2']
        }
    }
    
    SAMPLING_CONFIG = {
        SensorType.EEG.value: {'control': 'eegSamplingCombo', 'rates': [500, 1000, 2000]},
        SensorType.FNIRS.value: {'control': 'fnirsSamplingCombo', 'rates': [10, 20]},
        SensorType.SEMG.value: {'control': 'semgSamplingCombo', 'rates': [500, 1000, 2000]}
    }


def parse_sensor_types(sensor_type_int: int) -> List[str]:
    """Convert integer sensor type to list of sensor strings"""
    sensor_list = []
    if sensor_type_int == SensorTypes.NotInit:
        return sensor_list
    
    for sensor_bit, sensor_type in [(SensorTypes.EEG, SensorType.EEG.value),
                                    (SensorTypes.SEMG, SensorType.SEMG.value),
                                    (SensorTypes.FNIRS, SensorType.FNIRS.value)]:
        if sensor_type_int & sensor_bit:
            sensor_list.append(sensor_type)
    
    return sensor_list


def get_montage_directory() -> Path:
    """Get or create the montage directory in the current working directory"""
    try:
        montage_dir = Path.cwd() / "montage"
        montage_dir.mkdir(exist_ok=True)
        logger.info(f"Montage directory: {montage_dir}")
        return montage_dir
    except Exception as e:
        logger.error(f"Failed to create montage directory: {e}")
        return Path.cwd()


def get_default_config_path(filename: str = "device_config.json") -> str:
    """Get default configuration file path in montage directory"""
    try:
        return str(get_montage_directory() / filename)
    except Exception as e:
        logger.error(f"Failed to get default config path: {e}")
        return filename


class ConfigurationManager(QWidget, Ui_ConfigForm):
    """Main configuration management class with enhanced error handling"""
    
    OnSampleRateSet = pyqtSignal(int, int)
    OnChannelConfigSet = pyqtSignal(int, list)
    
    def __init__(self, sensor_types: Optional[int] = None, parent=None):
        super().__init__(parent)
        
        logger.info("Initializing ConfigurationManager")
        self.montage_dir = get_montage_directory()
        self.sensor_types = sensor_types
        
        # Process sensor types
        if sensor_types is None:
            sensor_types_list = [SensorType.FNIRS.value]
        elif isinstance(sensor_types, int):
            sensor_types_list = parse_sensor_types(sensor_types)
        else:
            raise ValueError(f"Invalid sensor_types format: {type(sensor_types)}. Expected int or None")
        
        self.enabled_sensor_types = self._validate_sensor_types(sensor_types_list)
        
        # Initialize components
        self._initialize_ui()
        self._initialize_configuration()
        self._setup_connections()
        logger.info("ConfigurationManager initialization completed successfully")
    
    def _validate_sensor_types(self, sensor_types: List[str]) -> Set[str]:
        """Validate and filter sensor types"""
        valid_sensors = {sensor for sensor in sensor_types if SensorType.validate_sensor_type(sensor)}
        
        if not valid_sensors:
            raise ValueError("At least one valid sensor type must be provided")
        
        return valid_sensors
    
    def _initialize_ui(self):
        """Initialize UI components with error handling"""
        try:
            self.setupUi(self)
            
            # Initialize sensor checkboxes storage
            self.sensor_checkboxes = {}
            for sensor in self.enabled_sensor_types:
                if sensor == SensorType.FNIRS.value:
                    self.sensor_checkboxes.update({'Source': [], 'Detect': []})
                else:
                    self.sensor_checkboxes[sensor] = []
            
            logger.debug("UI setup completed")
        except Exception as e:
            logger.error(f"UI initialization failed: {e}")
            raise
    
    def _initialize_configuration(self):
        """Initialize device configuration"""
        try:
            self.config = DeviceConfiguration(enabled_sensors=self.enabled_sensor_types)
            self._customize_ui_for_sensors()
            self._initialize_ui_values()
            logger.info("Configuration initialization completed")
        except Exception as e:
            logger.error(f"Configuration initialization failed: {e}")
            raise
    
    def _setup_connections(self):
        """Setup signal connections with error handling"""
        try:
            # Button connections
            button_mappings = {
                'generateConfigBtn': self._safe_apply_channel_config,
                'loadConfigBtn': self._safe_load_configuration,
                'createConfigBtn': self._safe_create_configuration,
                'saveConfigBtn': self._safe_save_configuration,
                'resetConfigBtn': self._safe_reset_configuration
            }
            
            for button_name, callback in button_mappings.items():
                if hasattr(self, button_name):
                    getattr(self, button_name).clicked.connect(callback)
            
            self._connect_channel_controls()
            logger.debug("Signal connections established")
        except Exception as e:
            logger.error(f"Failed to setup connections: {e}")
            raise
    
    def _connect_channel_controls(self):
        """Connect channel control signals"""
        channel_controls = {
            SensorType.EEG.value: 'eegChannelsSpinBox_2',
            SensorType.SEMG.value: 'semgChannelsSpinBox_2'
        }
        
        for sensor, control_name in channel_controls.items():
            if sensor in self.enabled_sensor_types and hasattr(self, control_name):
                getattr(self, control_name).valueChanged.connect(
                    lambda sensor=sensor: self._safe_update_channel_configuration(sensor))
        
        # fNIRS special handling
        if SensorType.FNIRS.value in self.enabled_sensor_types:
            for control_name in ['fnirsSourcesSpinBox_2', 'fnirsDetectorsSpinBox_2']:
                if hasattr(self, control_name):
                    getattr(self, control_name).valueChanged.connect(
                        lambda: self._safe_update_channel_configuration(SensorType.FNIRS.value))
    
    def _safe_wrapper(self, func: Callable, *args, **kwargs):
        """Safe wrapper for method calls with error handling"""
        try:
            logger.debug(f"Executing {func.__name__}")
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            self._show_error_message("操作失败 Operation Failed", 
                                   f"执行 {func.__name__} 时出错：{str(e)}")
            return None
    
    # Safe wrapper methods
    def _safe_apply_channel_config(self): return self._safe_wrapper(self.apply_channel_config)
    def _safe_load_configuration(self): return self._safe_wrapper(self.load_configuration)
    def _safe_create_configuration(self): return self._safe_wrapper(self.create_configuration)
    def _safe_save_configuration(self): return self._safe_wrapper(self.save_configuration)
    def _safe_reset_configuration(self): return self._safe_wrapper(self.reset_configuration)
    def _safe_update_channel_configuration(self, sensor_type): 
        return self._safe_wrapper(self.update_channel_configuration, sensor_type)
    
    def _customize_ui_for_sensors(self):
        """Customize UI to show only enabled sensor controls"""
        logger.info("Customizing UI for enabled sensors")
        
        # Show/hide controls based on enabled sensors
        for control_type, mappings in UIConstants.SENSOR_CONTROL_MAPPINGS.items():
            for sensor, controls in mappings.items():
                visible = sensor in self.enabled_sensor_types
                for control_name in controls:
                    if hasattr(self, control_name):
                        getattr(self, control_name).setVisible(visible)
        
        self._customize_tab_widget()
        logger.debug("UI customization completed")
    
    def _customize_tab_widget(self):
        """Customize tab widget based on sensor associations"""
        if not hasattr(self, 'configTabWidget'):
            return
        
        # Clear existing tabs
        while self.configTabWidget.count() > 0:
            self.configTabWidget.removeTab(0)
        
        # Add tabs based on enabled sensors
        brain_sensors = {SensorType.EEG.value, SensorType.FNIRS.value}
        if brain_sensors.intersection(self.enabled_sensor_types):
            self._add_brain_configuration_tab()
        
        if SensorType.SEMG.value in self.enabled_sensor_types:
            self._add_trunk_configuration_tab()
        
        if self.configTabWidget.count() == 0:
            self._add_placeholder_tab()
    
    def _add_brain_configuration_tab(self):
        """Add Brain Configuration tab for EEG and fNIRS"""
        try:
            self.brainTab = QtWidgets.QWidget()
            self.brainTab.setObjectName("brainTab")
            self.configTabWidget.addTab(self.brainTab, "脑极配置")

            # Create scroll area
            self.brainScrollArea = QtWidgets.QScrollArea(self.brainTab)
            self.brainScrollArea.setGeometry(QtCore.QRect(5, 5, 560, 560))
            self.brainScrollArea.setWidgetResizable(True)

            self.brainScrollWidget = QtWidgets.QWidget()
            self.brainScrollArea.setWidget(self.brainScrollWidget)

            self.brainMainLayout = QtWidgets.QVBoxLayout(self.brainScrollWidget)

            # Add sensor sections
            if SensorType.EEG.value in self.enabled_sensor_types:
                self._add_sensor_group_box("EEG", "EEG通道配置", "#2196F3")
            
            if SensorType.FNIRS.value in self.enabled_sensor_types:
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
        setattr(self, f"{sensor_key.lower()}GroupBox", group_box)
        setattr(self, f"{sensor_key.lower()}GridLayout", grid_layout)
        
        self.brainMainLayout.addWidget(group_box)
    
    def _add_fnirs_section(self):
        """Add fNIRS section to brain configuration tab"""
        self.fnirsGroupBox = QGroupBox("fNIRS通道配置")
        self.fnirsGroupBox.setStyleSheet("QGroupBox { font-weight: bold; color: #E91E63; }")
        
        self.fnirsMainLayout = QtWidgets.QVBoxLayout(self.fnirsGroupBox)
        self.fnirsGridLayout = QtWidgets.QGridLayout()
        self.fnirsMainLayout.addLayout(self.fnirsGridLayout)
        
        self.brainMainLayout.addWidget(self.fnirsGroupBox)
    
    def _add_brain_locator_widget(self):
        """Add brain electrode locator widget"""
        try:
            self.brain_config_right = locate.Locate()
            self.brain_config_right.setParent(self.brainTab)
            self.brain_config_right.setGeometry(QtCore.QRect(570, 5, 560, 560))
        except Exception as e:
            logger.error(f"Failed to add brain locator widget: {e}")
            self._create_placeholder_locator_widget()
    
    def _create_placeholder_locator_widget(self):
        """Create placeholder widget when locator is unavailable"""
        self.brain_config_right = QtWidgets.QWidget(self.brainTab)
        self.brain_config_right.setGeometry(QtCore.QRect(570, 5, 560, 560))
        layout = QVBoxLayout(self.brain_config_right)
        layout.addWidget(QLabel("Locator not available"))
    
    def _add_trunk_configuration_tab(self):
        """Add Trunk Configuration tab for sEMG"""
        try:
            self.trunkTab = QtWidgets.QWidget()
            self.trunkTab.setObjectName("trunkTab")
            self.configTabWidget.addTab(self.trunkTab, "躯干配置")

            # Create scroll area and content
            self.trunkScrollArea = QtWidgets.QScrollArea(self.trunkTab)
            self.trunkScrollArea.setGeometry(QtCore.QRect(5, 5, 560, 560))
            self.trunkScrollArea.setWidgetResizable(True)

            self.trunkScrollWidget = QtWidgets.QWidget()
            self.trunkScrollArea.setWidget(self.trunkScrollWidget)

            # Add sEMG group box
            self.semgGroupBox = QGroupBox("sEMG通道配置")
            self.semgGroupBox.setStyleSheet("QGroupBox { font-weight: bold; color: #FF9800; }")
            
            self.semgGridLayout = QtWidgets.QGridLayout(self.semgGroupBox)
            
            layout = QVBoxLayout(self.trunkScrollWidget)
            layout.addWidget(self.semgGroupBox)
            layout.addStretch()
            
            # Right widget placeholder
            self.widget_trunk_right = QtWidgets.QWidget(self.trunkTab)
            self.widget_trunk_right.setGeometry(QtCore.QRect(570, 5, 560, 560))
            
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
        self.configTabWidget.addTab(placeholder_tab, "No Configuration")
    
    def _initialize_ui_values(self):
        """Initialize UI with default values"""
        try:
            self._initialize_sampling_rates()
            self._initialize_channel_counts()
            logger.info("UI values initialization completed")
        except Exception as e:
            logger.error(f"UI values initialization failed: {e}")
            raise
    
    def _initialize_sampling_rates(self):
        """Initialize sampling rate controls"""
        for sensor, control_name in [
            (SensorType.EEG.value, 'eegSamplingCombo'),
            (SensorType.FNIRS.value, 'fnirsSamplingCombo'),
            (SensorType.SEMG.value, 'semgSamplingCombo')
        ]:
            if sensor in self.enabled_sensor_types and hasattr(self, control_name):
                control = getattr(self, control_name)
                rate = self.config.sampling_rates[sensor]
                control.setCurrentText(str(rate))
                control.currentIndexChanged.connect(self.modify_sample_rate)
    
    def _initialize_channel_counts(self):
        """Initialize channel count controls"""
        channel_controls = [
            (SensorType.EEG.value, 'eegChannelsSpinBox_2', 'generate_eeg_configuration'),
            (SensorType.SEMG.value, 'semgChannelsSpinBox_2', 'generate_semg_configuration')
        ]
        
        for sensor, control_name, callback_name in channel_controls:
            if sensor in self.enabled_sensor_types and hasattr(self, control_name):
                control = getattr(self, control_name)
                count = self.config.channel_counts[sensor]
                control.setValue(count)
                if hasattr(self, callback_name):
                    control.valueChanged.connect(getattr(self, callback_name))
        
        # fNIRS special handling
        if SensorType.FNIRS.value in self.enabled_sensor_types:
            fnirs_controls = [
                ('fnirsSourcesSpinBox_2', 'fnirs_sources'),
                ('fnirsDetectorsSpinBox_2', 'fnirs_detectors')
            ]
            for control_name, count_key in fnirs_controls:
                if hasattr(self, control_name):
                    control = getattr(self, control_name)
                    control.setValue(self.config.channel_counts[count_key])
                    control.valueChanged.connect(self.generate_fnirs_configuration)
    
    def _show_message(self, msg_type: str, title: str, message: str) -> int:
        """Generic message display method"""
        try:
            if msg_type == "error":
                QMessageBox.critical(self, title, message)
                return QMessageBox.Ok
            elif msg_type == "info":
                QMessageBox.information(self, title, message)
                return QMessageBox.Ok
            elif msg_type == "warning":
                return QMessageBox.warning(self, title, message, QMessageBox.Yes | QMessageBox.No)
        except Exception as e:
            logger.error(f"Failed to show {msg_type} message: {e}")
            return QMessageBox.No
    
    def _show_error_message(self, title: str, message: str):
        self._show_message("error", title, message)
    
    def _show_info_message(self, title: str, message: str):
        self._show_message("info", title, message)
    
    def _show_warning_message(self, title: str, message: str) -> int:
        return self._show_message("warning", title, message)
    
    def apply_channel_config(self):
        """Apply channel configuration"""
        logger.info("Apply channel config called")
        
        try:
            sample_rate_order = self._generate_sample_rate_order()
            config_order = self._generate_config_order()
            return self.sensor_types, sample_rate_order
        except Exception as e:
            logger.error(f"Failed to apply sampling rates: {e}")
            self._show_error_message("Error", f"无效的采样率值：{str(e)}")
    
    def _generate_sample_rate_order(self):
        """Generate sample rate order for enabled sensor types"""
        return self._process_sensor_configurations(UIConstants.SAMPLING_CONFIG, "sampling rate")
    
    def _generate_config_order(self):
        """Generate config order for enabled sensor types"""
        return self._process_sensor_configurations(UIConstants.SAMPLING_CONFIG, "config")
    
    def _process_sensor_configurations(self, config_mapping: Dict, operation_type: str):
        """Generic method to process sensor configurations"""
        updated_sensors = []
        sensor_id_map = {
            SensorType.EEG.value: 1,
            SensorType.SEMG.value: 2,
            SensorType.FNIRS.value: 4
        }
        
        for sensor_type in self.enabled_sensor_types:
            if sensor_type not in config_mapping:
                continue
                
            config = config_mapping[sensor_type]
            control_name = config['control']
            valid_rates = config['rates']
            
            if not hasattr(self, control_name):
                continue
                
            try:
                control = getattr(self, control_name)
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
        
        return updated_sensors
    
    def create_configuration(self):
        """Generate channel configuration based on current settings"""
        logger.info("Creating configuration")
        
        try:
            self._update_channel_counts_from_ui()
            
            if hasattr(self, 'brainTab'):
                self._add_brain_control_buttons()
            
            for sensor_type in self.enabled_sensor_types:
                self.generate_sensor_configuration(sensor_type)
            
            logger.info("Configuration creation completed successfully")
        except Exception as e:
            logger.error(f"Configuration creation failed: {e}")
            self._show_error_message("Error", f"配置生成失败：{str(e)}")
    
    def _update_channel_counts_from_ui(self):
        """Update channel counts from UI spinboxes"""
        try:
            channel_mappings = [
                (SensorType.EEG.value, 'eegChannelsSpinBox_2'),
                (SensorType.SEMG.value, 'semgChannelsSpinBox_2')
            ]
            
            for sensor, control_name in channel_mappings:
                if sensor in self.enabled_sensor_types and hasattr(self, control_name):
                    self.config.channel_counts[sensor] = getattr(self, control_name).value()
            
            # fNIRS special handling
            if SensorType.FNIRS.value in self.enabled_sensor_types:
                fnirs_mappings = [
                    ('fnirsSourcesSpinBox_2', 'fnirs_sources'),
                    ('fnirsDetectorsSpinBox_2', 'fnirs_detectors')
                ]
                for control_name, count_key in fnirs_mappings:
                    if hasattr(self, control_name):
                        self.config.channel_counts[count_key] = getattr(self, control_name).value()
                        
        except Exception as e:
            logger.error(f"Failed to update channel counts from UI: {e}")
            raise
    
    def _add_brain_control_buttons(self):
        """Add control buttons for brain configuration"""
        try:
            if not hasattr(self, 'brainTab') or not hasattr(self, 'brain_config_right'):
                logger.warning("Brain tab or config widget not available")
                return
            
            self._remove_existing_control_buttons()
            
            # Create buttons with common styling
            button_configs = [
                ('reset_locator_btn', '重置', '#f44336', self._get_reset_callback()),
                ('finish_locator_btn', '完成', '#4CAF50', self._get_finish_callback())
            ]
            
            parent_width = self.brainTab.width() if self.brainTab.width() > 0 else 1140
            
            for i, (name, text, color, callback) in enumerate(button_configs):
                button = QtWidgets.QPushButton(self.brainTab)
                button.setObjectName(name)
                button.setText(text)
                button.setStyleSheet(self._get_button_style(color))
                
                # Position buttons
                x_pos = min(parent_width - (180 - i * 90), 580 + i * 90)
                button.setGeometry(QtCore.QRect(x_pos, 10, 80, 30))
                
                button.clicked.connect(callback)
                button.show()
                button.raise_()
                
                setattr(self, name, button)
                logger.info(f"Created {name} at position ({x_pos}, 10)")
            
            if hasattr(self.brainTab, 'update'):
                self.brainTab.update()
                
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
    
    def _get_reset_callback(self):
        """Get reset button callback"""
        if hasattr(self.brain_config_right, 'reset_all_electrodes'):
            return self.brain_config_right.reset_all_electrodes
        return self._fallback_reset_electrodes
    
    def _get_finish_callback(self):
        """Get finish button callback"""
        if hasattr(self.brain_config_right, 'get_channel_pairs_summary'):
            return self._get_config_summary
        return self._fallback_show_summary
    
    def _get_config_summary(self):
        """Get configuration summary from brain locator"""
        self.brain_config_right.get_channel_pairs_summary()
        
        if hasattr(self.brain_config_right, 'get_sources'):
            source_config = self.brain_config_right.get_sources()
            self.config.enabled_channels[SensorType.FNIRS.value + 'source'] = [
                electrode_name for _, electrode_name in source_config.items()
            ]
        
        if hasattr(self.brain_config_right, 'get_detectors'):
            detect_config = self.brain_config_right.get_detectors()
            self.config.enabled_channels[SensorType.FNIRS.value + 'detect'] = [
                electrode_name for _, electrode_name in detect_config.items()
            ]
        
        if hasattr(self.brain_config_right, 'get_fnirs_pairs'):
            fnirs_config = self.brain_config_right.get_fnirs_pairs()
            for chn_name, node_info in fnirs_config.items():
                self.config.enabled_channels[SensorType.FNIRS.value][chn_name] = node_info['node_pair']
    
    def _remove_existing_control_buttons(self):
        """Remove existing control buttons to prevent duplicates"""
        for button_name in ['reset_locator_btn', 'finish_locator_btn']:
            if hasattr(self, button_name):
                button = getattr(self, button_name)
                if button is not None:
                    button.deleteLater()
                    setattr(self, button_name, None)
    
    def _fallback_reset_electrodes(self):
        """Fallback method for reset functionality"""
        try:
            logger.info("Executing fallback reset electrode functionality")
            
            if hasattr(self.config, 'enabled_channel_pairs'):
                self.config.enabled_channel_pairs.clear()
            
            # Clear checkbox selections
            checkbox_groups = ['Source', 'Detect'] + list(self.enabled_sensor_types)
            for group in checkbox_groups:
                if group in self.sensor_checkboxes:
                    for checkbox in self.sensor_checkboxes[group]:
                        checkbox.setChecked(False)
            
            self._show_info_message("Reset Complete", "电极配置已重置")
            
        except Exception as e:
            logger.error(f"Fallback reset failed: {e}")
            self._show_error_message("Reset Failed", f"重置失败：{str(e)}")
    
    def _fallback_show_summary(self):
        """Fallback method for showing summary"""
        try:
            summary = self.get_channel_summary()
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Channel Configuration Summary")
            msg.setText("通道配置摘要")
            msg.setDetailedText(summary)
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.exec_()
        except Exception as e:
            logger.error(f"Fallback summary failed: {e}")
            self._show_error_message("Summary Failed", f"显示摘要失败：{str(e)}")
    
    def generate_sensor_configuration(self, sensor_type: str):
        """Generate configuration for specific sensor type"""
        try:
            config_methods = {
                SensorType.EEG.value: self.generate_eeg_configuration,
                SensorType.SEMG.value: self.generate_semg_configuration,
                SensorType.FNIRS.value: self.generate_fnirs_configuration
            }
            
            if sensor_type in config_methods:
                config_methods[sensor_type]()
            else:
                logger.warning(f"Unknown sensor type: {sensor_type}")
                
        except Exception as e:
            logger.error(f"Failed to generate configuration for {sensor_type}: {e}")
            raise
    
    def generate_eeg_configuration(self):
        """Generate EEG channel configuration"""
        self._generate_standard_sensor_config(SensorType.EEG.value, 'eegGridLayout')
    
    def generate_semg_configuration(self):
        """Generate sEMG channel configuration"""
        self._generate_standard_sensor_config(SensorType.SEMG.value, 'semgGridLayout')
    
    def _generate_standard_sensor_config(self, sensor_type: str, layout_name: str):
        """Generate standard sensor configuration (EEG/sEMG)"""
        logger.info(f"Generating {sensor_type} configuration")
        
        try:
            if not hasattr(self, layout_name):
                logger.warning(f"{sensor_type} grid layout not available")
                return
            
            layout = getattr(self, layout_name)
            self._clear_layout(layout)
            self.sensor_checkboxes[sensor_type].clear()
            
            sensor_config = self.config.sensor_configs[sensor_type]
            channel_count = self.config.channel_counts[sensor_type]
            
            for i in range(channel_count):
                row, col = divmod(i, sensor_config.channels_per_row)
                
                checkbox = QCheckBox(f"{sensor_config.prefix}{i+1:02d}")
                checkbox.setStyleSheet(f"QCheckBox {{ color: {sensor_config.color}; font-weight: bold; }}")
                checkbox.stateChanged.connect(
                    lambda state, idx=i: self.update_sensor_channels(sensor_type, idx, state))
                
                layout.addWidget(checkbox, row, col)
                self.sensor_checkboxes[sensor_type].append(checkbox)
            
            logger.info(f"Generated {channel_count} {sensor_type} channel checkboxes")
            
        except Exception as e:
            logger.error(f"Failed to generate {sensor_type} configuration: {e}")
            raise
    
    def generate_fnirs_configuration(self):
        """Generate fNIRS source-detector matrix configuration"""
        logger.info("Generating fNIRS configuration")
        
        try:
            if not hasattr(self, 'fnirsGridLayout'):
                logger.warning("fNIRS grid layout not available")
                return
            
            self._clear_layout(self.fnirsGridLayout)
            self.sensor_checkboxes['Source'].clear()
            self.sensor_checkboxes['Detect'].clear()
            
            # Update counts from UI
            self._update_fnirs_counts_from_ui()
            
            sensor_config = self.config.sensor_configs[SensorType.FNIRS.value]
            source_count = self.config.channel_counts['fnirs_sources']
            detector_count = self.config.channel_counts['fnirs_detectors']
            
            # Generate sources and detectors
            self._generate_fnirs_components('Source', source_count, sensor_config, 0)
            source_rows = int(np.ceil(source_count / sensor_config.channels_per_row))
            self._generate_fnirs_components('Detect', detector_count, sensor_config, source_rows)
            
            logger.info(f"Generated {source_count} source and {detector_count} detector checkboxes")
            
        except Exception as e:
            logger.error(f"Failed to generate fNIRS configuration: {e}")
            raise
    
    def _update_fnirs_counts_from_ui(self):
        """Update fNIRS counts from UI"""
        if SensorType.FNIRS.value in self.enabled_sensor_types:
            for control_name, count_key in [
                ('fnirsSourcesSpinBox_2', 'fnirs_sources'),
                ('fnirsDetectorsSpinBox_2', 'fnirs_detectors')
            ]:
                if hasattr(self, control_name):
                    self.config.channel_counts[count_key] = getattr(self, control_name).value()
    
    def _generate_fnirs_components(self, component_type: str, count: int, sensor_config: SensorConfig, row_offset: int):
        """Generate fNIRS components (sources or detectors)"""
        color_idx = 0 if component_type == 'Source' else 1
        prefix_idx = 0 if component_type == 'Source' else 1
        
        for i in range(count):
            row = i // sensor_config.channels_per_row + row_offset
            col = i % sensor_config.channels_per_row
            
            checkbox = QCheckBox(f"{sensor_config.prefix[prefix_idx]}{i+1:02d}")
            checkbox.setStyleSheet(f"QCheckBox {{ color: {sensor_config.color[color_idx]}; font-weight: bold; }}")
            checkbox.stateChanged.connect(
                lambda state, idx=i: self.update_sensor_channels(component_type, idx, state))
            
            self.fnirsGridLayout.addWidget(checkbox, row, col)
            self.sensor_checkboxes[component_type].append(checkbox)
    
    def update_sensor_channels(self, sensor_type: str, channel_idx: int, state: int):
        """Update sensor channel configuration"""
        try:
            logger.debug(f"Updating {sensor_type} channel {channel_idx} to state {state}")
            
            # Update brain locator if available
            if (hasattr(self, 'brain_config_right') and 
                hasattr(self.brain_config_right, 'set_current_node_info')):
                try:
                    self.brain_config_right.set_current_node_info(sensor_type, channel_idx + 1, state)
                except Exception as e:
                    logger.warning(f"Failed to update brain locator: {e}")
            
            # Update enabled channels list
            if sensor_type in self.sensor_checkboxes and sensor_type in self.config.enabled_channels:
                checkboxes = self.sensor_checkboxes[sensor_type]
                self.config.enabled_channels[sensor_type] = [
                    i for i, checkbox in enumerate(checkboxes) if checkbox.isChecked()
                ]
            
        except Exception as e:
            logger.error(f"Failed to update sensor channels for {sensor_type}: {e}")
    
    def update_channel_configuration(self, sensor_type: str):
        """Update channel configuration when counts change"""
        try:
            # Check if configuration exists
            has_config = (sensor_type in self.sensor_checkboxes and 
                         bool(self.sensor_checkboxes[sensor_type]))
            
            if sensor_type == SensorType.FNIRS.value:
                has_config = bool(self.sensor_checkboxes.get('Source', []))
            
            if has_config:
                self.generate_sensor_configuration(sensor_type)
                logger.info(f"Regenerated configuration for {sensor_type}")
                
        except Exception as e:
            logger.error(f"Failed to update channel configuration for {sensor_type}: {e}")
    
    def modify_sample_rate(self):
        """Update sampling rates from UI controls"""
        sampling_controls = [
            (SensorType.EEG.value, 'eegSamplingCombo'),
            (SensorType.SEMG.value, 'semgSamplingCombo'),
            (SensorType.FNIRS.value, 'fnirsSamplingCombo')
        ]
        
        for sensor, control_name in sampling_controls:
            if sensor in self.enabled_sensor_types and hasattr(self, control_name):
                control = getattr(self, control_name)
                self.config.sampling_rates[sensor] = int(control.currentText())
    
    def _clear_layout(self, layout):
        """Clear all widgets from a layout"""
        try:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        except Exception as e:
            logger.error(f"Failed to clear layout: {e}")
    
    def get_configuration_dict(self) -> Dict[str, Any]:
        """Get current comprehensive configuration as dictionary"""
        logger.info("Getting configuration dictionary")
        
        try:
            config_dict = {
                'enabled_sensor_types': list(self.enabled_sensor_types),
                'sampling_rates': self.config.sampling_rates.copy(),
                'channel_counts': self.config.channel_counts.copy(),
                'enabled_channels': self.config.enabled_channels.copy(),
                'sensor_configs': {k: v.__dict__ if hasattr(v, '__dict__') else v 
                                 for k, v in self.config.sensor_configs.items() 
                                 if k in self.enabled_sensor_types},
                'electrode_mapping': self.config.enabled_channel_pairs.copy(),
                'metadata': self._generate_metadata()
            }
            
            # Add electrode position data if available
            if hasattr(self, 'brain_config_right'):
                self._add_electrode_position_data(config_dict)
            
            return config_dict
            
        except Exception as e:
            logger.error(f"Failed to create configuration dictionary: {e}")
            raise
    
    def _generate_metadata(self) -> Dict[str, Any]:
        """Generate metadata for configuration"""
        return {
            'total_channels': {sensor: len(self.config.enabled_channels.get(sensor, [])) 
                             for sensor in self.enabled_sensor_types},
            'configuration_timestamp': QtCore.QDateTime.currentDateTime().toString(),
            'enabled_sensors': list(self.enabled_sensor_types),
            'version': '2.0',
            'has_electrode_positions': bool(self.config.enabled_channel_pairs),
            'has_valid_channels': bool(self.config.enabled_channel_pairs)
        }
    
    def _add_electrode_position_data(self, config_dict: Dict[str, Any]):
        """Add electrode position data to configuration dictionary"""
        try:
            electrode_methods = [
                ('fnirs_pairs', 'get_fnirs_pairs', SensorType.FNIRS.value),
                ('sources', 'get_sources', SensorType.FNIRS.value),
                ('detectors', 'get_detectors', SensorType.FNIRS.value),
                ('eeg_pairs', 'get_eeg_pairs', SensorType.EEG.value),
                ('eeg_electrodes', 'get_eeg_electrodes', SensorType.EEG.value)
            ]
            
            for key, method_name, required_sensor in electrode_methods:
                if (required_sensor in self.enabled_sensor_types and 
                    hasattr(self.brain_config_right, method_name)):
                    config_dict[key] = getattr(self.brain_config_right, method_name)()
            
        except Exception as e:
            logger.warning(f"Failed to get electrode data: {e}")
    
    def save_configuration(self):
        """Save current configuration to JSON file"""
        logger.info("Starting configuration save")
        
        try:
            default_path = get_default_config_path("device_config.json")
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存配置 Save Configuration", 
                default_path, "JSON files (*.json);;All files (*)")
            
            if not file_path:
                return
            
            config_dict = self.get_configuration_dict()
            validation_result = self._validate_configuration_for_save(config_dict)
            
            if not validation_result['valid']:
                if self._show_warning_message("Configuration Validation",
                    self._format_validation_message(validation_result['warnings'])) != QMessageBox.Yes:
                    return
            
            # Save configuration
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            summary = self._get_save_summary(config_dict)
            enabled_sensors_str = ", ".join([s.upper() for s in self.enabled_sensor_types])
            
            self._show_info_message("Success", 
                f"配置保存成功！\nConfiguration saved for {enabled_sensors_str}\n\n"
                f"Summary:\n{summary}\n\nFile: {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            self._show_error_message("Error", f"配置保存失败：{str(e)}")
    
    def _format_validation_message(self, warnings: List[str]) -> str:
        """Format validation warnings message"""
        warning_text = "\n".join(warnings)
        return (f"配置验证发现问题：\n{warning_text}\n\n是否仍然保存？\n\n"
                f"Configuration validation found issues:\n{warning_text}\n\nSave anyway?")
    
    def _validate_configuration_for_save(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration before saving"""
        warnings = []
        
        try:
            validation_checks = [
                (not config_dict.get('electrode_mapping') and SensorType.FNIRS.value in self.enabled_sensor_types,
                 "No electrode positions defined for fNIRS"),
                (not config_dict.get('fnirs_pairs') and SensorType.FNIRS.value in self.enabled_sensor_types,
                 "No valid fNIRS channel pairs found")
            ]
            
            for condition, message in validation_checks:
                if condition:
                    warnings.append(message)
            
            # Check sampling rates
            for sensor in self.enabled_sensor_types:
                if sensor not in config_dict.get('sampling_rates', {}):
                    warnings.append(f"No sampling rate defined for {sensor.upper()}")
            
        except Exception as e:
            warnings.append(f"Validation error: {str(e)}")
        
        return {'valid': len(warnings) == 0, 'warnings': warnings}
    
    def _get_save_summary(self, config_dict: Dict[str, Any]) -> str:
        """Get summary of saved configuration"""
        lines = []
        
        summary_mappings = [
            ('fnirs_pairs', lambda x: f"fNIRS Channels: {len(x)}"),
            ('sources', lambda x: f"Sources: {len(x)}"),
            ('detectors', lambda x: f"Detectors: {len(x)}"),
            ('eeg_electrodes', lambda x: f"EEG Electrodes: {len(x)}")
        ]
        
        for key, formatter in summary_mappings:
            if key in config_dict:
                lines.append(formatter(config_dict[key]))
        
        # Add sampling rates
        if 'sampling_rates' in config_dict:
            for sensor, rate in config_dict['sampling_rates'].items():
                lines.append(f"{sensor.upper()} Rate: {rate}Hz")
        
        return '\n'.join(lines) if lines else "Basic configuration saved"
    
    def load_configuration(self):
        """Load configuration from JSON file"""
        logger.info("Starting configuration load")
        
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "加载配置 Load Configuration", 
                str(self.montage_dir), "JSON files (*.json);;All files (*)")
            
            if not file_path or not os.path.exists(file_path):
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            if not self._validate_loaded_config(config_dict):
                return
            
            self._apply_loaded_configuration(config_dict)
            self._show_info_message("Success", f"配置加载成功！\nConfiguration loaded from:\n{file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self._show_error_message("Error", f"配置加载失败：{str(e)}")
    
    def _validate_loaded_config(self, config_dict: Dict[str, Any]) -> bool:
        """Validate that loaded configuration is compatible"""
        try:
            if 'enabled_sensor_types' not in config_dict:
                self._show_error_message("Error", "配置文件格式不兼容")
                return False
            
            loaded_sensors = set(config_dict['enabled_sensor_types'])
            incompatible_sensors = loaded_sensors - self.enabled_sensor_types
            
            if incompatible_sensors:
                if self._show_warning_message("Sensor Type Mismatch",
                    self._format_sensor_mismatch_message(incompatible_sensors)) != QMessageBox.Yes:
                    return False
            
            return True
            
        except Exception as e:
            self._show_error_message("Error", f"Configuration validation failed: {str(e)}")
            return False
    
    def _format_sensor_mismatch_message(self, incompatible_sensors: Set[str]) -> str:
        """Format sensor mismatch message"""
        incompatible_str = ", ".join([s.upper() for s in incompatible_sensors])
        current_str = ", ".join([s.upper() for s in self.enabled_sensor_types])
        
        return (f"配置文件包含当前未启用的传感器类型：{incompatible_str}\n"
                f"当前启用的传感器：{current_str}\n\n是否继续加载兼容部分？\n\n"
                f"Loaded config contains sensors not enabled: {incompatible_str}\n"
                f"Currently enabled: {current_str}\n\nContinue loading compatible parts?")
    
    def _apply_loaded_configuration(self, config_dict: Dict[str, Any]):
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
                    apply_method(config_dict[section_key])
            
            self._apply_loaded_electrode_positions(config_dict.get('enabled_channels', {}))
            
        except Exception as e:
            logger.error(f"Failed to apply loaded configuration: {e}")
            raise
    
    def _apply_loaded_sampling_rates(self, sampling_rates: Dict[str, int]):
        """Apply loaded sampling rates"""
        sampling_controls = {
            SensorType.EEG.value: 'eegSamplingCombo',
            SensorType.FNIRS.value: 'fnirsSamplingCombo',
            SensorType.SEMG.value: 'semgSamplingCombo'
        }
        
        for sensor in self.enabled_sensor_types:
            if sensor in sampling_rates and sensor in sampling_controls:
                control_name = sampling_controls[sensor]
                if hasattr(self, control_name):
                    try:
                        control = getattr(self, control_name)
                        control.setCurrentText(str(sampling_rates[sensor]))
                        self.config.sampling_rates[sensor] = sampling_rates[sensor]
                    except Exception as e:
                        logger.warning(f"Failed to set {sensor} sampling rate: {e}")
    
    def _apply_loaded_channel_counts(self, channel_counts: Dict[str, int]):
        """Apply loaded channel counts"""
        try:
            # Standard sensors
            channel_mappings = [
                (SensorType.EEG.value, 'eegChannelsSpinBox_2'),
                (SensorType.SEMG.value, 'semgChannelsSpinBox_2')
            ]
            
            for sensor, control_name in channel_mappings:
                if (sensor in self.enabled_sensor_types and 
                    sensor in channel_counts and hasattr(self, control_name)):
                    getattr(self, control_name).setValue(channel_counts[sensor])
                    self.config.channel_counts[sensor] = channel_counts[sensor]
            
            # fNIRS special handling
            if SensorType.FNIRS.value in self.enabled_sensor_types:
                fnirs_mappings = [
                    ('fnirs_sources', 'fnirsSourcesSpinBox_2'),
                    ('fnirs_detectors', 'fnirsDetectorsSpinBox_2')
                ]
                
                for count_key, control_name in fnirs_mappings:
                    if count_key in channel_counts and hasattr(self, control_name):
                        getattr(self, control_name).setValue(channel_counts[count_key])
                        self.config.channel_counts[count_key] = channel_counts[count_key]
                        
        except Exception as e:
            logger.error(f"Failed to apply loaded channel counts: {e}")
            raise
    
    def _apply_loaded_enabled_channels(self, enabled_channels: Dict[str, Any]):
        """Apply loaded enabled channels to checkboxes"""
        try:
            for sensor in self.enabled_sensor_types:
                if sensor in enabled_channels and sensor in self.sensor_checkboxes:
                    self._apply_sensor_channels(sensor, enabled_channels[sensor])
            
            # Handle fNIRS components
            if SensorType.FNIRS.value in self.enabled_sensor_types:
                fnirs_mappings = [
                    ('fnirssource', 'Source'),
                    ('fnirsdetect', 'Detect')
                ]
                
                for key, checkbox_key in fnirs_mappings:
                    if key in enabled_channels and checkbox_key in self.sensor_checkboxes:
                        channels = enabled_channels[key]
                        for i in range(len(channels)):
                            if i < len(self.sensor_checkboxes[checkbox_key]):
                                self.sensor_checkboxes[checkbox_key][i].setChecked(True)
            
        except Exception as e:
            logger.error(f"Failed to apply loaded enabled channels: {e}")
    
    def _apply_sensor_channels(self, sensor: str, sensor_channels: List[int]):
        """Apply enabled channels for a specific sensor"""
        if isinstance(sensor_channels, list):
            checkboxes = self.sensor_checkboxes[sensor]
            for i in range(len(sensor_channels)):
                if i < len(checkboxes):
                    checkboxes[i].setChecked(True)
    
    def _apply_loaded_electrode_positions(self, enabled_channels: Dict[str, Any]):
        """Apply loaded electrode positions to the locator"""
        if not hasattr(self, 'brain_config_right'):
            return
        
        try:
            if hasattr(self.brain_config_right, 'load_pairs_info'):
                self.brain_config_right.load_pairs_info(enabled_channels)
                logger.info("Applied electrode positions from loaded configuration")
        except Exception as e:
            logger.error(f"Failed to apply electrode positions: {e}")
            self._show_warning_message("Warning", f"重建电极位置时出错：{str(e)}")
    
    def reset_configuration(self):
        """Reset all configuration to default values"""
        logger.info("Resetting configuration")
        
        try:
            enabled_sensors_str = ", ".join([s.upper() for s in self.enabled_sensor_types])
            
            if self._show_warning_message("重置配置 Reset Configuration", 
                f"确定要将所有配置重置为默认值吗？\n传感器类型：{enabled_sensors_str}\n\n"
                f"Are you sure you want to reset all configuration to default values?\n"
                f"Sensor types: {enabled_sensors_str}") == QMessageBox.Yes:
                
                # Reset configuration
                self.config = DeviceConfiguration(enabled_sensors=self.enabled_sensor_types)
                self._initialize_ui_values()
                self._clear_all_configurations()
                
                # Reset brain locator if available
                if (hasattr(self, 'brain_config_right') and 
                    hasattr(self.brain_config_right, 'reset_all_electrodes')):
                    self.brain_config_right.reset_all_electrodes()
                
                self._show_info_message("Success", 
                    f"配置已重置为默认值！\n传感器类型：{enabled_sensors_str}")
                
        except Exception as e:
            logger.error(f"Failed to reset configuration: {e}")
            self._show_error_message("Error", f"重置配置失败：{str(e)}")
    
    def _clear_all_configurations(self):
        """Clear all sensor configurations"""
        # Clear layouts
        layout_mappings = {
            SensorType.EEG.value: 'eegGridLayout',
            SensorType.SEMG.value: 'semgGridLayout',
            SensorType.FNIRS.value: 'fnirsGridLayout'
        }
        
        for sensor, layout_name in layout_mappings.items():
            if sensor in self.enabled_sensor_types and hasattr(self, layout_name):
                self._clear_layout(getattr(self, layout_name))
        
        # Clear checkbox references
        for sensor_type in self.sensor_checkboxes:
            self.sensor_checkboxes[sensor_type].clear()
    
    def get_sensor_summary(self) -> Dict[str, Any]:
        """Get a summary of current sensor configuration"""
        try:
            summary = {
                'enabled_sensors': list(self.enabled_sensor_types),
                'sampling_rates': self.config.sampling_rates.copy(),
                'total_channels': {},
                'channel_counts': self.config.channel_counts.copy(),
                'enabled_channels': self.config.enabled_channels.copy()
            }
            
            # Calculate total enabled channels
            for sensor in self.enabled_sensor_types:
                if sensor in self.config.enabled_channels:
                    channels = self.config.enabled_channels[sensor]
                    summary['total_channels'][sensor] = len(channels) if isinstance(channels, (list, dict)) else 0
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate sensor summary: {e}")
            return {'error': str(e)}
    
    def validate_current_configuration(self) -> Dict[str, List[str]]:
        """Validate current configuration and return results"""
        try:
            return self.config.validate_configuration()
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return {'errors': [f"Validation failed: {str(e)}"], 'warnings': []}
    
    def get_enabled_sensor_types(self) -> List[str]:
        """Get list of enabled sensor types"""
        return list(self.enabled_sensor_types)
    
    def is_sensor_enabled(self, sensor_type: str) -> bool:
        """Check if a specific sensor type is enabled"""
        return sensor_type in self.enabled_sensor_types
    
    def get_channel_summary(self) -> str:
        """Get comprehensive channel summary for display"""
        try:
            summary_lines = []
            
            # Basic sensor info
            for sensor in self.enabled_sensor_types:
                if sensor == SensorType.FNIRS.value:
                    sources = self.config.channel_counts.get('fnirs_sources', 0)
                    detectors = self.config.channel_counts.get('fnirs_detectors', 0)
                    enabled_sources = len(self.config.enabled_channels.get('Source', []))
                    enabled_detectors = len(self.config.enabled_channels.get('Detect', []))
                    summary_lines.append(f"fNIRS: {sources} sources ({enabled_sources} enabled), "
                                       f"{detectors} detectors ({enabled_detectors} enabled)")
                else:
                    total = self.config.channel_counts.get(sensor, 0)
                    enabled = len(self.config.enabled_channels.get(sensor, []))
                    summary_lines.append(f"{sensor.upper()}: {total} channels ({enabled} enabled)")
            
            # Add electrode position info if available
            if hasattr(self, 'brain_config_right'):
                self._add_electrode_summary_info(summary_lines)
            
            return '\n'.join(summary_lines) if summary_lines else "No configuration available"
            
        except Exception as e:
            logger.error(f"Failed to generate channel summary: {e}")
            return f"Summary generation failed: {str(e)}"
    
    def _add_electrode_summary_info(self, summary_lines: List[str]):
        """Add electrode summary information"""
        try:
            electrode_info = [
                (SensorType.FNIRS.value, 'get_fnirs_pairs', 'fNIRS Valid Pairs'),
                (SensorType.EEG.value, 'get_eeg_electrodes', 'EEG Positioned Electrodes')
            ]
            
            for sensor, method_name, label in electrode_info:
                if (sensor in self.enabled_sensor_types and 
                    hasattr(self.brain_config_right, method_name)):
                    data = getattr(self.brain_config_right, method_name)()
                    summary_lines.append(f"{label}: {len(data)}")
                    
        except Exception as e:
            logger.warning(f"Failed to get electrode summary: {e}")


def create_configuration_manager(sensor_types: Union[List[str], int], parent=None) -> ConfigurationManager:
    """Factory function to create configuration manager with specific sensor types"""
    logger.info(f"Creating configuration manager with sensor types: {sensor_types}")
    
    try:
        return ConfigurationManager(sensor_types, parent)
    except Exception as e:
        logger.error(f"Failed to create configuration manager: {e}")
        raise


def main():
    """Main application entry point with enhanced error handling"""
    
    # Setup application
    app = QApplication(sys.argv)
    app.setApplicationName("设备配置管理器 Device Configuration Manager")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("生物医学工程实验室 Biomedical Engineering Lab")
    
    logger.info("Starting Device Configuration Manager v2.0.0")
    
    # Default sensor configuration
    sensor_types = SensorTypes.FNIRS
    
    try:
        # Create and show main window
        window = ConfigurationManager(sensor_types)
        enabled_sensors = window.get_enabled_sensor_types()
        enabled_sensors_str = ", ".join([s.upper() for s in enabled_sensors])
        window.setWindowTitle(f"设备配置管理器 v2.0 - {enabled_sensors_str}")
        window.show()
        
        # Log initial configuration
        logger.info(f"Configuration Manager started successfully with sensors: {enabled_sensors_str}")
        initial_config = window.get_sensor_summary()
        logger.info(f"Initial configuration: {initial_config}")
        
        # Start application event loop
        exit_code = app.exec_()
        logger.info(f"Application exited with code: {exit_code}")
        sys.exit(exit_code)
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Critical)
        error_dialog.setWindowTitle("Configuration Error")
        error_dialog.setText(f"配置错误 Configuration Error:\n{str(e)}")
        error_dialog.exec_()
        sys.exit(1)
        
    except Exception as e:
        logger.critical(f"Critical application error: {e}")
        logger.critical(traceback.format_exc())
        
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Critical)
        error_dialog.setWindowTitle("Critical Error")
        error_dialog.setText(f"应用程序发生严重错误 Critical Application Error:\n{str(e)}\n\n"
                           f"请查看日志文件获取详细信息\nPlease check the log file for details")
        error_dialog.setDetailedText(traceback.format_exc())
        error_dialog.exec_()
        sys.exit(1)


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-

"""
Optimized Device Configuration Management System
Handles EEG, sEMG, and fNIRS device configuration with improved error handling and logging
"""

import sys
import json
import os
from typing import List, Dict, Set, Any, Optional, Tuple, Union
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
    from ui_config import Ui_ConfigForm
    logger.info("Successfully imported ui_config module")
except ImportError as e:
    logger.error(f"Failed to import ui_config: {e}")
    # Create a dummy class to prevent crashes
    class Ui_ConfigForm:
        def setupUi(self, widget): pass

try:
    import locate
    logger.info("Successfully imported locate module")
except ImportError as e:
    logger.error(f"Failed to import locate module: {e}")
    # Create a dummy class
    class locate:
        class Locate(QtWidgets.QWidget):
            def __init__(self): super().__init__()

class SensorTypes:
    """Define sensor types"""
    NotInit = 0
    EEG = 1
    SEMG = 2
    EEG_SEMG = 3
    FNIRS = 4
    EEG_FNIRS = 5
    SEMG_FNIRS = 6
    EEG_SEMG_FNIRS = 7

def parse_sensor_types(sensor_type_int: int) -> List[str]:
    """Convert integer sensor type to list of sensor strings"""
    sensor_list = []
    
    if sensor_type_int == SensorTypes.NotInit:
        return sensor_list
    
    # Check for EEG
    if sensor_type_int & SensorTypes.EEG:
        sensor_list.append(SensorType.EEG.value)
    
    # Check for SEMG
    if sensor_type_int & SensorTypes.SEMG:
        sensor_list.append(SensorType.SEMG.value)
    
    # Check for FNIRS
    if sensor_type_int & SensorTypes.FNIRS:
        sensor_list.append(SensorType.FNIRS.value)
    
    return sensor_list

class SensorType(Enum):
    """Enum for sensor types with validation"""
    EEG = "eeg"
    SEMG = "semg" 
    FNIRS = "fnirs"
    
    @classmethod
    def get_all_types(cls) -> List[str]:
        """Get all sensor type values"""
        return [sensor.value for sensor in cls]
    
    @classmethod
    def validate_sensor_type(cls, sensor_type: str) -> bool:
        """Validate if sensor type is supported"""
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

def get_montage_directory() -> Path:
    """Get or create the montage directory in the current working directory"""
    try:
        current_dir = Path.cwd()
        montage_dir = current_dir / "montage"
        
        # Create directory if it doesn't exist
        montage_dir.mkdir(exist_ok=True)
        
        logger.info(f"Montage directory: {montage_dir}")
        return montage_dir
        
    except Exception as e:
        logger.error(f"Failed to create montage directory: {e}")
        # Fall back to current directory
        return Path.cwd()


def get_default_config_path(filename: str = "device_config.json") -> str:
    """Get default configuration file path in montage directory"""
    try:
        montage_dir = get_montage_directory()
        config_path = montage_dir / filename
        return str(config_path)
    except Exception as e:
        logger.error(f"Failed to get default config path: {e}")
        return filename
    

@dataclass
class DeviceConfiguration:
    """Enhanced data class for device configuration with validation"""
    enabled_sensors: Set[str] = field(default_factory=set)
    sampling_rates: Dict[str, int] = field(default_factory=dict)
    channel_counts: Dict[str, int] = field(default_factory=dict)
    enabled_channels: Dict[str, Union[List[int] , Dict]] = field(default_factory=dict)
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
                color='#2196F3',
                prefix='EEG',
                max_channels=64,
                min_channels=1,
                channels_per_row=8
            ),
            SensorType.SEMG.value: SensorConfig(
                color='#FF9800',
                prefix='EMG',
                max_channels=16,
                min_channels=1,
                channels_per_row=4
            ),
            SensorType.FNIRS.value: SensorConfig(
                color=['#E91E63', '#1040ff'],
                prefix=['S', 'D'],
                max_channels=0,  # Not applicable for fNIRS
                min_channels=0,  # Not applicable for fNIRS
                channels_per_row=8,
                max_sources=32,
                max_detectors=32,
                min_sources=1,
                min_detectors=1
            )
        }
        logger.debug("Sensor configurations initialized")
    
    def _initialize_default_settings(self):
        """Initialize default sampling rates and channel counts"""
        # Default sampling rates
        default_sampling_rates = {
            SensorType.EEG.value: 1000,
            SensorType.FNIRS.value: 10,
            SensorType.SEMG.value: 1000
        }
        
        # Default channel counts
        default_channel_counts = {
            SensorType.EEG.value: 32,
            SensorType.SEMG.value: 8,
            'fnirs_sources': 16,
            'fnirs_detectors': 16
        }
        
        # Initialize only for enabled sensors
        for sensor in self.enabled_sensors:
            if sensor in default_sampling_rates:
                self.sampling_rates[sensor] = default_sampling_rates[sensor]
                logger.debug(f"Set default sampling rate for {sensor}: {default_sampling_rates[sensor]}")
            
            if sensor == SensorType.FNIRS.value:
                self.channel_counts['fnirs_sources'] = default_channel_counts['fnirs_sources']
                self.channel_counts['fnirs_detectors'] = default_channel_counts['fnirs_detectors']
                self.enabled_channels[sensor] = {}
                self.enabled_channels[sensor + 'source'] = []
                self.enabled_channels[sensor + 'detect'] = []
                logger.debug(f"Initialized fNIRS channels: sources={default_channel_counts['fnirs_sources']}, detectors={default_channel_counts['fnirs_detectors']}")
            else:
                if sensor in default_channel_counts:
                    self.channel_counts[sensor] = default_channel_counts[sensor]
                    logger.debug(f"Set default channel count for {sensor}: {default_channel_counts[sensor]}")
                self.enabled_channels[sensor] = []
            
            self.enabled_channel_pairs[sensor] = {}
    
    def validate_configuration(self) -> Dict[str, List[str]]:
        """Validate current configuration and return any issues"""
        errors = []
        warnings = []
        
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
                    sources = self.channel_counts.get('fnirs_sources', 0)
                    detectors = self.channel_counts.get('fnirs_detectors', 0)
                    if sources < config.min_sources or sources > config.max_sources:
                        errors.append(f"fNIRS sources out of range: {sources} (valid: {config.min_sources}-{config.max_sources})")
                    if detectors < config.min_detectors or detectors > config.max_detectors:
                        errors.append(f"fNIRS detectors out of range: {detectors} (valid: {config.min_detectors}-{config.max_detectors})")
                else:
                    count = self.channel_counts.get(sensor, 0)
                    if count < config.min_channels or count > config.max_channels:
                        errors.append(f"{sensor.upper()} channels out of range: {count} (valid: {config.min_channels}-{config.max_channels})")
            
            logger.info(f"Configuration validation complete: {len(errors)} errors, {len(warnings)} warnings")
            
        except Exception as e:
            logger.error(f"Error during configuration validation: {e}")
            errors.append(f"Validation error: {str(e)}")
        
        return {'errors': errors, 'warnings': warnings}


class ConfigurationManager(QWidget, Ui_ConfigForm):
    """Main configuration management class with enhanced error handling"""
    
    OnSampleRateSet = pyqtSignal(int, int)
    OnChannelConfigSet = pyqtSignal(int, list)
    
    def __init__(self, sensor_types: Optional[int] = None, parent=None):
        super().__init__(parent)
        
        logger.info("Initializing ConfigurationManager")
        
        # Ensure montage directory exists
        self.montage_dir = get_montage_directory()
        logger.info(f"Using montage directory: {self.montage_dir}")
        
        self.sensor_types = sensor_types
         # Handle different sensor_types input formats
        if sensor_types is None:
            # Default to fNIRS only
            sensor_types_list = [SensorType.FNIRS.value]
            logger.info("No sensor types provided, defaulting to fNIRS")
        elif isinstance(sensor_types, int):
            # Convert integer sensor type to list of strings
            sensor_types_list = parse_sensor_types(sensor_types)
            logger.info(f"Converted integer sensor type {sensor_types} to: {sensor_types_list}")
        else:
            raise ValueError(f"Invalid sensor_types format: {type(sensor_types)}. Expected int, List[str], or None")
        
        # Validate and filter sensor types
        self.enabled_sensor_types = self._validate_sensor_types(sensor_types_list)
        logger.info(f"Enabled sensor types: {self.enabled_sensor_types}")
        
        # Initialize UI and configuration
        try:
            self._initialize_ui()
            self._initialize_configuration()
            self._setup_connections()
            logger.info("ConfigurationManager initialization completed successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ConfigurationManager: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _validate_sensor_types(self, sensor_types: List[str]) -> Set[str]:
        """Validate and filter sensor types"""
        valid_sensors = set()
        
        for sensor in sensor_types:
            if SensorType.validate_sensor_type(sensor):
                valid_sensors.add(sensor)
                logger.debug(f"Validated sensor type: {sensor}")
            else:
                logger.warning(f"Invalid sensor type ignored: {sensor}")
        
        if not valid_sensors:
            error_msg = "At least one valid sensor type must be provided"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        return valid_sensors
    
    def _initialize_ui(self):
        """Initialize UI components with error handling"""
        try:
            self.setupUi(self)
            logger.debug("UI setup completed")
            
            # Initialize sensor checkboxes storage
            self.sensor_checkboxes = {}
            for sensor in self.enabled_sensor_types:
                if sensor == SensorType.FNIRS.value:
                    self.sensor_checkboxes['Source'] = []
                    self.sensor_checkboxes['Detect'] = []
                else:
                    self.sensor_checkboxes[sensor] = []
            
            logger.debug("Sensor checkboxes storage initialized")
            
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
            # Configuration controls
            if hasattr(self, 'generateConfigBtn'):
                self.generateConfigBtn.clicked.connect(self._safe_apply_channel_config)
            if hasattr(self, 'loadConfigBtn'):
                self.loadConfigBtn.clicked.connect(self._safe_load_configuration)
            if hasattr(self, 'createConfigBtn'):
                self.createConfigBtn.clicked.connect(self._safe_create_configuration)
            if hasattr(self, 'saveConfigBtn'):
                self.saveConfigBtn.clicked.connect(self._safe_save_configuration)
            if hasattr(self, 'resetConfigBtn'):
                self.resetConfigBtn.clicked.connect(self._safe_reset_configuration)
            
            # Channel count changes
            self._connect_channel_controls()
            
            logger.debug("Signal connections established")
            
        except Exception as e:
            logger.error(f"Failed to setup connections: {e}")
            raise
    
    def _connect_channel_controls(self):
        """Connect channel control signals"""
        try:
            if SensorType.EEG.value in self.enabled_sensor_types and hasattr(self, 'eegChannelsSpinBox_2'):
                self.eegChannelsSpinBox_2.valueChanged.connect(
                    lambda: self._safe_update_channel_configuration(SensorType.EEG.value))
            
            if SensorType.SEMG.value in self.enabled_sensor_types and hasattr(self, 'semgChannelsSpinBox_2'):
                self.semgChannelsSpinBox_2.valueChanged.connect(
                    lambda: self._safe_update_channel_configuration(SensorType.SEMG.value))
            
            if SensorType.FNIRS.value in self.enabled_sensor_types:
                if hasattr(self, 'fnirsSourcesSpinBox_2'):
                    self.fnirsSourcesSpinBox_2.valueChanged.connect(
                        lambda: self._safe_update_channel_configuration(SensorType.FNIRS.value))
                if hasattr(self, 'fnirsDetectorsSpinBox_2'):
                    self.fnirsDetectorsSpinBox_2.valueChanged.connect(
                        lambda: self._safe_update_channel_configuration(SensorType.FNIRS.value))
            
            logger.debug("Channel control connections established")
            
        except Exception as e:
            logger.error(f"Failed to connect channel controls: {e}")
    
    def _safe_wrapper(self, func, *args, **kwargs):
        """Safe wrapper for method calls with error handling"""
        try:
            logger.debug(f"Executing {func.__name__} with args={args}, kwargs={kwargs}")
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            logger.error(traceback.format_exc())
            self._show_error_message(f"操作失败 Operation Failed", 
                                   f"执行 {func.__name__} 时出错：{str(e)}\nError in {func.__name__}: {str(e)}")
            return None
    
    def _safe_apply_channel_config(self):
        """Safe wrapper for apply_channel_config"""
        return self._safe_wrapper(self.apply_channel_config)
    
    def _safe_load_configuration(self):
        """Safe wrapper for load_configuration"""
        return self._safe_wrapper(self.load_configuration)
    
    def _safe_create_configuration(self):
        """Safe wrapper for create_configuration"""
        return self._safe_wrapper(self.create_configuration)
    
    def _safe_save_configuration(self):
        """Safe wrapper for save_configuration"""
        return self._safe_wrapper(self.save_configuration)
    
    def _safe_reset_configuration(self):
        """Safe wrapper for reset_configuration"""
        return self._safe_wrapper(self.reset_configuration)
    
    def _safe_update_channel_configuration(self, sensor_type):
        """Safe wrapper for update_channel_configuration"""
        return self._safe_wrapper(self.update_channel_configuration, sensor_type)
    
    def _customize_ui_for_sensors(self):
        """Customize UI to show only enabled sensor controls"""
        logger.info("Customizing UI for enabled sensors")
        
        try:
            self._customize_sampling_rate_controls()
            self._customize_device_parameter_controls() 
            self._customize_tab_widget()
            logger.debug("UI customization completed")
        except Exception as e:
            logger.error(f"UI customization failed: {e}")
            raise
    
    def _customize_sampling_rate_controls(self):
        """Show/hide sampling rate controls based on enabled sensors"""
        controls_map = {
            SensorType.EEG.value: ['eegSamplingLabel', 'eegSamplingCombo'],
            SensorType.FNIRS.value: ['fnirsSamplingLabel', 'fnirsSamplingCombo'],
            SensorType.SEMG.value: ['semgSamplingLabel', 'semgSamplingCombo']
        }
        
        for sensor, controls in controls_map.items():
            visible = sensor in self.enabled_sensor_types
            for control_name in controls:
                if hasattr(self, control_name):
                    getattr(self, control_name).setVisible(visible)
                    logger.debug(f"Set {control_name} visibility to {visible} for sensor {sensor}")
    
    def _customize_device_parameter_controls(self):
        """Show/hide device parameter controls based on enabled sensors"""
        controls_map = {
            SensorType.EEG.value: ['eegChannelsLabel_2', 'eegChannelsSpinBox_2'],
            SensorType.SEMG.value: ['semgChannelsLabel_2', 'semgChannelsSpinBox_2'],
            SensorType.FNIRS.value: ['fnirsSourcesLabel_2', 'fnirsSourcesSpinBox_2', 
                                   'fnirsDetectorsLabel_2', 'fnirsDetectorsSpinBox_2']
        }
        
        for sensor, controls in controls_map.items():
            visible = sensor in self.enabled_sensor_types
            for control_name in controls:
                if hasattr(self, control_name):
                    getattr(self, control_name).setVisible(visible)
                    logger.debug(f"Set {control_name} visibility to {visible} for sensor {sensor}")
    
    def _customize_tab_widget(self):
        """Customize tab widget based on sensor associations"""
        if not hasattr(self, 'configTabWidget'):
            logger.warning("configTabWidget not found, skipping tab customization")
            return
        
        # Clear existing tabs
        while self.configTabWidget.count() > 0:
            self.configTabWidget.removeTab(0)
        
        # Add tabs based on enabled sensors
        brain_sensors = {SensorType.EEG.value, SensorType.FNIRS.value}
        if brain_sensors.intersection(self.enabled_sensor_types):
            self._add_brain_configuration_tab()
            logger.debug("Added brain configuration tab")
        
        if SensorType.SEMG.value in self.enabled_sensor_types:
            self._add_trunk_configuration_tab()
            logger.debug("Added trunk configuration tab")
        
        # Add placeholder if no tabs
        if self.configTabWidget.count() == 0:
            self._add_placeholder_tab()
            logger.debug("Added placeholder tab")
    
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
            self.brainScrollArea.setObjectName("brainScrollArea")

            self.brainScrollWidget = QtWidgets.QWidget()
            self.brainScrollWidget.setGeometry(QtCore.QRect(0, 0, 558, 558))
            self.brainScrollWidget.setObjectName("brainScrollWidget")
            self.brainScrollArea.setWidget(self.brainScrollWidget)

            self.brainMainLayout = QtWidgets.QVBoxLayout(self.brainScrollWidget)
            self.brainMainLayout.setObjectName("brainMainLayout")

            # Add sensor sections
            if SensorType.EEG.value in self.enabled_sensor_types:
                self._add_eeg_section_to_brain_tab()
            
            if SensorType.FNIRS.value in self.enabled_sensor_types:
                self._add_fnirs_section_to_brain_tab()
            
            # Add right widget (locator)
            self._add_brain_locator_widget()
            
            logger.debug("Brain configuration tab created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create brain configuration tab: {e}")
            raise
    
    def _add_eeg_section_to_brain_tab(self):
        """Add EEG section to brain configuration tab"""
        self.eegGroupBox = QGroupBox("EEG通道配置")
        self.eegGroupBox.setStyleSheet("QGroupBox { font-weight: bold; color: #2196F3; }")
        
        self.eegGridLayout = QtWidgets.QGridLayout(self.eegGroupBox)
        self.eegGridLayout.setObjectName("eegGridLayout")
        
        self.brainMainLayout.addWidget(self.eegGroupBox)
        logger.debug("EEG section added to brain tab")
    
    def _add_fnirs_section_to_brain_tab(self):
        """Add fNIRS section to brain configuration tab"""
        self.fnirsGroupBox = QGroupBox("fNIRS通道配置")
        self.fnirsGroupBox.setStyleSheet("QGroupBox { font-weight: bold; color: #E91E63; }")
        
        self.fnirsMainLayout = QtWidgets.QVBoxLayout(self.fnirsGroupBox)
        self.fnirsMainLayout.setObjectName("fnirsMainLayout")

        self.fnirsGridLayout = QtWidgets.QGridLayout()
        self.fnirsGridLayout.setObjectName("fnirsGridLayout")
        self.fnirsMainLayout.addLayout(self.fnirsGridLayout)
        
        self.brainMainLayout.addWidget(self.fnirsGroupBox)
        logger.debug("fNIRS section added to brain tab")
    
    def _add_brain_locator_widget(self):
        """Add brain electrode locator widget"""
        try:
            self.brain_config_right = locate.Locate()
            self.brain_config_right.setParent(self.brainTab)
            self.brain_config_right.setGeometry(QtCore.QRect(570, 5, 560, 560))
            self.brain_config_right.setObjectName("brain_electrode_locator")
            logger.debug("Brain locator widget added")
        except Exception as e:
            logger.error(f"Failed to add brain locator widget: {e}")
            # Create placeholder widget
            self.brain_config_right = QtWidgets.QWidget(self.brainTab)
            self.brain_config_right.setGeometry(QtCore.QRect(570, 5, 560, 560))
            placeholder_label = QLabel("Locator not available")
            placeholder_label.setAlignment(Qt.AlignCenter)
            layout = QVBoxLayout(self.brain_config_right)
            layout.addWidget(placeholder_label)
    
    def _add_trunk_configuration_tab(self):
        """Add Trunk Configuration tab for sEMG"""
        try:
            self.trunkTab = QtWidgets.QWidget()
            self.trunkTab.setObjectName("trunkTab")
            self.configTabWidget.addTab(self.trunkTab, "躯干配置")

            self.trunkScrollArea = QtWidgets.QScrollArea(self.trunkTab)
            self.trunkScrollArea.setGeometry(QtCore.QRect(5, 5, 560, 560))
            self.trunkScrollArea.setWidgetResizable(True)
            self.trunkScrollArea.setObjectName("trunkScrollArea")

            self.trunkScrollWidget = QtWidgets.QWidget()
            self.trunkScrollWidget.setGeometry(QtCore.QRect(0, 0, 558, 558))
            self.trunkScrollWidget.setObjectName("trunkScrollWidget")
            self.trunkScrollArea.setWidget(self.trunkScrollWidget)

            # sEMG Group Box
            self.semgGroupBox = QGroupBox("sEMG通道配置")
            self.semgGroupBox.setStyleSheet("QGroupBox { font-weight: bold; color: #FF9800; }")
            
            self.semgGridLayout = QtWidgets.QGridLayout(self.semgGroupBox)
            self.semgGridLayout.setObjectName("semgGridLayout")
            
            # Add to scroll widget
            semg_layout = QVBoxLayout(self.trunkScrollWidget)
            semg_layout.addWidget(self.semgGroupBox)
            semg_layout.addStretch()
            
            # Right widget placeholder
            self.widget_trunk_right = QtWidgets.QWidget(self.trunkTab)
            self.widget_trunk_right.setGeometry(QtCore.QRect(570, 5, 560, 560))
            self.widget_trunk_right.setObjectName("widget_trunk_right")
            
            logger.debug("Trunk configuration tab created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create trunk configuration tab: {e}")
            raise
    
    def _add_placeholder_tab(self):
        """Add placeholder tab when no sensors are configured"""
        placeholder_tab = QtWidgets.QWidget()
        placeholder_label = QLabel("No sensor types enabled for configuration")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_layout = QVBoxLayout(placeholder_tab)
        placeholder_layout.addWidget(placeholder_label)
        self.configTabWidget.addTab(placeholder_tab, "No Configuration")
    
    def _initialize_ui_values(self):
        """Initialize UI with default values"""
        try:
            # Set default sampling rates
            sampling_controls = {
                SensorType.EEG.value: 'eegSamplingCombo',
                SensorType.FNIRS.value: 'fnirsSamplingCombo', 
                SensorType.SEMG.value: 'semgSamplingCombo'
            }
            
            for sensor, control_name in sampling_controls.items():
                if sensor in self.enabled_sensor_types and hasattr(self, control_name):
                    control = getattr(self, control_name)
                    rate = self.config.sampling_rates[sensor]
                    control.setCurrentText(str(rate))
                    control.currentIndexChanged.connect(self.modify_sample_rate)
                    logger.debug(f"Set {sensor} sampling rate to {rate}")
            
            # Set default channel counts
            channel_controls = {
                SensorType.EEG.value: ('eegChannelsSpinBox_2', 'generate_eeg_configuration'),
                SensorType.SEMG.value: ('semgChannelsSpinBox_2', 'generate_semg_configuration'),
            }
            
            for sensor, (control_name, callback_name) in channel_controls.items():
                if sensor in self.enabled_sensor_types and hasattr(self, control_name):
                    control = getattr(self, control_name)
                    count = self.config.channel_counts[sensor]
                    control.setValue(count)
                    if hasattr(self, callback_name):
                        control.valueChanged.connect(getattr(self, callback_name))
                    logger.debug(f"Set {sensor} channel count to {count}")
            
            # Special handling for fNIRS
            if SensorType.FNIRS.value in self.enabled_sensor_types:
                if hasattr(self, 'fnirsSourcesSpinBox_2'):
                    self.fnirsSourcesSpinBox_2.setValue(self.config.channel_counts['fnirs_sources'])
                    self.fnirsSourcesSpinBox_2.valueChanged.connect(self.generate_fnirs_configuration)
                if hasattr(self, 'fnirsDetectorsSpinBox_2'):
                    self.fnirsDetectorsSpinBox_2.setValue(self.config.channel_counts['fnirs_detectors'])
                    self.fnirsDetectorsSpinBox_2.valueChanged.connect(self.generate_fnirs_configuration)
                logger.debug("fNIRS channel counts initialized")
            
            logger.info("UI values initialization completed")
            
        except Exception as e:
            logger.error(f"UI values initialization failed: {e}")
            raise
    
    def _show_error_message(self, title: str, message: str):
        """Show error message to user"""
        try:
            QMessageBox.critical(self, title, message)
            logger.debug(f"Showed error message: {title}")
        except Exception as e:
            logger.error(f"Failed to show error message: {e}")
    
    def _show_info_message(self, title: str, message: str):
        """Show info message to user"""
        try:
            QMessageBox.information(self, title, message)
            logger.debug(f"Showed info message: {title}")
        except Exception as e:
            logger.error(f"Failed to show info message: {e}")
    
    def _show_warning_message(self, title: str, message: str) -> int:
        """Show warning message to user and return response"""
        try:
            response = QMessageBox.warning(self, title, message, QMessageBox.Yes | QMessageBox.No)
            logger.debug(f"Showed warning message: {title}, response: {response}")
            return response
        except Exception as e:
            logger.error(f"Failed to show warning message: {e}")
            return QMessageBox.No
    
    
    def apply_channel_config(self):
        """Apply channel configuration (placeholder for future implementation)"""
        logger.info("Apply channel config called")
        
        try:
            self._generate_sample_rate_order()
            
            self._generate_config_order()
                
        except Exception as e:
            logger.error(f"Failed to apply sampling rates: {e}")
            self._show_error_message("Error", 
                f"无效的采样率值：{str(e)}\nInvalid sampling rate values: {str(e)}")
    
    def _generate_sample_rate_order(self):
        """Generate sample rate order for enabled sensor types."""
        
        # Configuration mapping for sensors
        SENSOR_CONFIG = {
            SensorType.EEG.value: {
                'control': 'eegSamplingCombo',
                'rates': [500, 1000, 2000]
            },
            SensorType.FNIRS.value: {
                'control': 'fnirsSamplingCombo', 
                'rates': [10, 20]
            },
            SensorType.SEMG.value: {
                'control': 'semgSamplingCombo',
                'rates': [500, 1000, 2000]
            }
        }
        
        updated_sensors = []
        
        for sensor_type in self.enabled_sensor_types:
            if sensor_type not in SENSOR_CONFIG:
                continue
                
            config = SENSOR_CONFIG[sensor_type]
            control_name = config['control']
            valid_rates = config['rates']
            
            # Skip if control doesn't exist
            if not hasattr(self, control_name):
                continue
                
            try:
                control = getattr(self, control_name)
                rate = int(control.currentText())
                
                # Validate rate is in allowed list
                if rate not in valid_rates:
                    raise ValueError(f"Rate {rate}Hz not in allowed rates {valid_rates}")
                
                # # Update configuration
                # self.config.sampling_rates[sensor_type] = rate
                
                # Add sensor identifier and rate index
                updated_sensors.append(1)  # Sensor identifier
                rate_index = valid_rates.index(rate) + 1
                updated_sensors.append(rate_index)
                
                logger.info(f"Updated {sensor_type} sampling rate to {rate}Hz")
                
            except (ValueError, AttributeError) as e:
                error_msg = f"Failed to set sampling rate for {sensor_type}: {e}"
                logger.error(error_msg)
                raise ValueError(f"Invalid sampling rate for {sensor_type}: {e}")
        
        return self.sensor_types, updated_sensors
    
    def _generate_config_order(self):
        """Generate config order for enabled sensor types."""
        updated_sensors = []
        
        for sensor_type in self.enabled_sensor_types:
            if sensor_type not in SENSOR_CONFIG:
                continue
                
            config = SENSOR_CONFIG[sensor_type]
            control_name = config['control']
            valid_rates = config['rates']
            
            # Skip if control doesn't exist
            if not hasattr(self, control_name):
                continue
                
            try:
                control = getattr(self, control_name)
                rate = int(control.currentText())
                
                # Validate rate is in allowed list
                if rate not in valid_rates:
                    raise ValueError(f"Rate {rate}Hz not in allowed rates {valid_rates}")
                
                # # Update configuration
                # self.config.sampling_rates[sensor_type] = rate
                
                # Add sensor identifier and rate index
                updated_sensors.append(1)  # Sensor identifier
                rate_index = valid_rates.index(rate) + 1
                updated_sensors.append(rate_index)
                
                logger.info(f"Updated {sensor_type} sampling rate to {rate}Hz")
                
            except (ValueError, AttributeError) as e:
                error_msg = f"Failed to set sampling rate for {sensor_type}: {e}"
                logger.error(error_msg)
                raise ValueError(f"Invalid sampling rate for {sensor_type}: {e}")
        
        return self.sensor_types, updated_sensors
    
    def create_configuration(self):
        """Generate channel configuration based on current settings"""
        logger.info("Creating configuration")
        
        try:
            # Update channel counts from UI
            self._update_channel_counts_from_ui()
            
            # Add control buttons for brain configuration
            if hasattr(self, 'brainTab'):
                self._add_brain_control_buttons()
            
            # Generate UI for each enabled sensor type
            for sensor_type in self.enabled_sensor_types:
                logger.info(f"Generating configuration for {sensor_type}")
                self.generate_sensor_configuration(sensor_type)
            
            logger.info("Configuration creation completed successfully")
            
        except Exception as e:
            logger.error(f"Configuration creation failed: {e}")
            self._show_error_message("Error", f"配置生成失败：{str(e)}\nConfiguration generation failed: {str(e)}")
    
    def _update_channel_counts_from_ui(self):
        """Update channel counts from UI spinboxes"""
        try:
            if SensorType.EEG.value in self.enabled_sensor_types and hasattr(self, 'eegChannelsSpinBox_2'):
                self.config.channel_counts[SensorType.EEG.value] = self.eegChannelsSpinBox_2.value()
                logger.debug(f"Updated EEG channel count: {self.eegChannelsSpinBox_2.value()}")
            
            if SensorType.SEMG.value in self.enabled_sensor_types and hasattr(self, 'semgChannelsSpinBox_2'):
                self.config.channel_counts[SensorType.SEMG.value] = self.semgChannelsSpinBox_2.value()
                logger.debug(f"Updated sEMG channel count: {self.semgChannelsSpinBox_2.value()}")
            
            if SensorType.FNIRS.value in self.enabled_sensor_types:
                if hasattr(self, 'fnirsSourcesSpinBox_2'):
                    self.config.channel_counts['fnirs_sources'] = self.fnirsSourcesSpinBox_2.value()
                    logger.debug(f"Updated fNIRS sources count: {self.fnirsSourcesSpinBox_2.value()}")
                if hasattr(self, 'fnirsDetectorsSpinBox_2'):
                    self.config.channel_counts['fnirs_detectors'] = self.fnirsDetectorsSpinBox_2.value()
                    logger.debug(f"Updated fNIRS detectors count: {self.fnirsDetectorsSpinBox_2.value()}")
                    
        except Exception as e:
            logger.error(f"Failed to update channel counts from UI: {e}")
            raise
    
    def _add_brain_control_buttons(self):
        """Add control buttons for brain configuration"""
        try:
            # Check if brainTab exists
            if not hasattr(self, 'brainTab') or self.brainTab is None:
                logger.warning("brainTab not available, cannot create control buttons")
                return
            
            # Check if brain_config_right exists
            if not hasattr(self, 'brain_config_right'):
                logger.warning("Brain config widget not available, skipping control buttons")
                return
            
            # Remove existing buttons if they exist to prevent duplicates
            self._remove_existing_control_buttons()
            
            # Create reset button
            try:
                self.reset_locator_btn = QtWidgets.QPushButton(self.brainTab)
                self.reset_locator_btn.setObjectName("reset_locator_btn")
                
                # Set geometry - ensure coordinates are within parent bounds
                parent_width = self.brainTab.width() if self.brainTab.width() > 0 else 1140
                parent_height = self.brainTab.height() if self.brainTab.height() > 0 else 570
                
                # Position reset button in top-right area
                reset_x = min(parent_width - 90, 1050)  # 90 = button width + margin
                reset_y = 10
                self.reset_locator_btn.setGeometry(QtCore.QRect(reset_x, reset_y, 80, 30))
                
                self.reset_locator_btn.setText("重置")
                self.reset_locator_btn.setStyleSheet("""
                    QPushButton { 
                        background-color: #f44336; 
                        color: white; 
                        border: none; 
                        border-radius: 4px;
                        font-weight: bold;
                    }
                    QPushButton:hover { 
                        background-color: #d32f2f; 
                    }
                    QPushButton:pressed { 
                        background-color: #b71c1c; 
                    }
                """)
                
                # Connect signal if method exists
                if hasattr(self.brain_config_right, 'reset_all_electrodes'):
                    self.reset_locator_btn.clicked.connect(self.brain_config_right.reset_all_electrodes)
                    logger.debug("Connected reset button to reset_all_electrodes method")
                else:
                    # Provide fallback functionality
                    self.reset_locator_btn.clicked.connect(self._fallback_reset_electrodes)
                    logger.warning("reset_all_electrodes method not found, using fallback")
                
                # Make button visible
                self.reset_locator_btn.show()
                self.reset_locator_btn.raise_()
                
                logger.info(f"Created reset button at position ({reset_x}, {reset_y})")
                
            except Exception as e:
                logger.error(f"Failed to create reset button: {e}")
            
            # Create finish button
            try:
                self.finish_locator_btn = QtWidgets.QPushButton(self.brainTab)
                self.finish_locator_btn.setObjectName("finish_locator_btn")
                
                # Position finish button in top area, left of reset button
                finish_x = min(parent_width - 180, 580)  # Leave space for reset button
                finish_y = 10
                self.finish_locator_btn.setGeometry(QtCore.QRect(finish_x, finish_y, 80, 30))
                
                self.finish_locator_btn.setText("完成")
                self.finish_locator_btn.setStyleSheet("""
                    QPushButton { 
                        background-color: #4CAF50; 
                        color: white; 
                        border: none; 
                        border-radius: 4px;
                        font-weight: bold;
                    }
                    QPushButton:hover { 
                        background-color: #45a049; 
                    }
                    QPushButton:pressed { 
                        background-color: #3d8b40; 
                    }
                """)
                
                # Connect signal if method exists
                if hasattr(self.brain_config_right, 'get_channel_pairs_summary'):
                    self.finish_locator_btn.clicked.connect(self._get_config_summary)
                    logger.debug("Connected finish button to get_channel_pairs_summary method")
                else:
                    # Provide fallback functionality
                    self.finish_locator_btn.clicked.connect(self._fallback_show_summary)
                    logger.warning("get_channel_pairs_summary method not found, using fallback")
                
                # Make button visible
                self.finish_locator_btn.show()
                self.finish_locator_btn.raise_()
                
                logger.info(f"Created finish button at position ({finish_x}, {finish_y})")
                
            except Exception as e:
                logger.error(f"Failed to create finish button: {e}")
            
            # Force layout update
            if hasattr(self.brainTab, 'update'):
                self.brainTab.update()
            
            logger.info("Brain control buttons creation completed")
                
        except Exception as e:
            logger.error(f"Failed to add brain control buttons: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")
    
    def _get_config_summary(self):
        self.brain_config_right.get_channel_pairs_summary()
        
        source_config = self.brain_config_right.get_sources()
        self.config.enabled_channels[SensorType.FNIRS.value +'source'] = [electrode_name for _, electrode_name in source_config.items()]
        
        detect_config = self.brain_config_right.get_detectors()
        self.config.enabled_channels[SensorType.FNIRS.value +'detect'] = [electrode_name for _, electrode_name in detect_config.items()]
        
        fnirs_config = self.brain_config_right.get_fnirs_pairs()
        for chn_name, node_info in fnirs_config.items():
            self.config.enabled_channels[SensorType.FNIRS.value][chn_name] = node_info['node_pair']
        

    def _remove_existing_control_buttons(self):
        """Remove existing control buttons to prevent duplicates"""
        try:
            # Remove reset button if it exists
            if hasattr(self, 'reset_locator_btn') and self.reset_locator_btn is not None:
                self.reset_locator_btn.deleteLater()
                self.reset_locator_btn = None
                logger.debug("Removed existing reset button")
            
            # Remove finish button if it exists
            if hasattr(self, 'finish_locator_btn') and self.finish_locator_btn is not None:
                self.finish_locator_btn.deleteLater()
                self.finish_locator_btn = None
                logger.debug("Removed existing finish button")
                
        except Exception as e:
            logger.warning(f"Error removing existing buttons: {e}")
    
    def _fallback_reset_electrodes(self):
        """Fallback method for reset functionality when brain_config_right method is unavailable"""
        try:
            logger.info("Executing fallback reset electrode functionality")
            
            # Reset internal configuration
            if hasattr(self.config, 'enabled_channel_pairs'):
                self.config.enabled_channel_pairs.clear()
            
            # Clear checkbox selections for fNIRS
            if 'Source' in self.sensor_checkboxes:
                for checkbox in self.sensor_checkboxes['Source']:
                    checkbox.setChecked(False)
            
            if 'Detect' in self.sensor_checkboxes:
                for checkbox in self.sensor_checkboxes['Detect']:
                    checkbox.setChecked(False)
            
            # Clear EEG selections if present
            if SensorType.EEG.value in self.sensor_checkboxes:
                for checkbox in self.sensor_checkboxes[SensorType.EEG.value]:
                    checkbox.setChecked(False)
            
            self._show_info_message("Reset Complete", "电极配置已重置\nElectrode configuration has been reset")
            logger.info("Fallback reset completed successfully")
            
        except Exception as e:
            logger.error(f"Fallback reset failed: {e}")
            self._show_error_message("Reset Failed", f"重置失败：{str(e)}\nReset failed: {str(e)}")
    
    def _fallback_show_summary(self):
        """Fallback method for showing summary when brain_config_right method is unavailable"""
        try:
            logger.info("Executing fallback show summary functionality")
            
            summary = self.get_channel_summary()
            
            # Create a simple summary dialog
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Channel Configuration Summary")
            msg.setText("通道配置摘要 Channel Configuration Summary")
            msg.setDetailedText(summary)
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.exec_()
            
            logger.info("Fallback summary display completed")
            
        except Exception as e:
            logger.error(f"Fallback summary failed: {e}")
            self._show_error_message("Summary Failed", f"显示摘要失败：{str(e)}\nShow summary failed: {str(e)}")
    
    def generate_sensor_configuration(self, sensor_type: str):
        """Generate configuration for specific sensor type"""
        try:
            if sensor_type == SensorType.EEG.value:
                self.generate_eeg_configuration()
            elif sensor_type == SensorType.SEMG.value:
                self.generate_semg_configuration()
            elif sensor_type == SensorType.FNIRS.value:
                self.generate_fnirs_configuration()
            else:
                logger.warning(f"Unknown sensor type: {sensor_type}")
                
        except Exception as e:
            logger.error(f"Failed to generate configuration for {sensor_type}: {e}")
            raise
    
    def generate_eeg_configuration(self):
        """Generate EEG channel configuration"""
        logger.info("Generating EEG configuration")
        
        try:
            if not hasattr(self, 'eegGridLayout'):
                logger.warning("EEG grid layout not available")
                return
            
            # Clear existing layout
            self._clear_layout(self.eegGridLayout)
            self.sensor_checkboxes[SensorType.EEG.value].clear()
            
            # Get configuration
            sensor_config = self.config.sensor_configs[SensorType.EEG.value]
            channel_count = self.config.channel_counts[SensorType.EEG.value]
            channels_per_row = sensor_config.channels_per_row
            
            logger.debug(f"Creating {channel_count} EEG checkboxes, {channels_per_row} per row")
            
            # Create channel checkboxes
            for i in range(channel_count):
                row = i // channels_per_row
                col = i % channels_per_row
                
                # Create checkbox with channel label
                checkbox = QCheckBox(f"{sensor_config.prefix}{i+1:02d}")
                checkbox.setStyleSheet(f"QCheckBox {{ color: {sensor_config.color}; font-weight: bold; }}")
                checkbox.stateChanged.connect(
                    lambda state, idx=i: self.update_sensor_channels(SensorType.EEG.value, idx, state))
                
                self.eegGridLayout.addWidget(checkbox, row, col)
                self.sensor_checkboxes[SensorType.EEG.value].append(checkbox)
            
            logger.info(f"Generated {channel_count} EEG channel checkboxes")
            
        except Exception as e:
            logger.error(f"Failed to generate EEG configuration: {e}")
            raise
    
    def generate_semg_configuration(self):
        """Generate sEMG channel configuration"""
        logger.info("Generating sEMG configuration")
        
        try:
            if not hasattr(self, 'semgGridLayout'):
                logger.warning("sEMG grid layout not available")
                return
            
            # Clear existing layout
            self._clear_layout(self.semgGridLayout)
            self.sensor_checkboxes[SensorType.SEMG.value].clear()
            
            # Get configuration
            sensor_config = self.config.sensor_configs[SensorType.SEMG.value]
            channel_count = self.config.channel_counts[SensorType.SEMG.value]
            channels_per_row = sensor_config.channels_per_row
            
            logger.debug(f"Creating {channel_count} sEMG checkboxes, {channels_per_row} per row")
            
            # Create channel checkboxes
            for i in range(channel_count):
                row = i // channels_per_row
                col = i % channels_per_row
                
                # Create checkbox with channel label
                checkbox = QCheckBox(f"{sensor_config.prefix}{i+1:02d}")
                checkbox.setStyleSheet(f"QCheckBox {{ color: {sensor_config.color}; font-weight: bold; }}")
                checkbox.stateChanged.connect(
                    lambda state, idx=i: self.update_sensor_channels(SensorType.SEMG.value, idx, state))
                
                self.semgGridLayout.addWidget(checkbox, row, col)
                self.sensor_checkboxes[SensorType.SEMG.value].append(checkbox)
            
            logger.info(f"Generated {channel_count} sEMG channel checkboxes")
            
        except Exception as e:
            logger.error(f"Failed to generate sEMG configuration: {e}")
            raise
    
    def modify_sample_rate(self):
        # Update channel counts from UI
        if SensorType.EEG.value in self.enabled_sensor_types:
            if hasattr(self, 'eegSamplingCombo'):
                self.config.sampling_rates[SensorType.EEG.value] = int(self.eegSamplingCombo.currentText())
        if SensorType.SEMG.value in self.enabled_sensor_types:
            if hasattr(self, 'semgSamplingCombo'):
                self.config.sampling_rates[SensorType.SEMG.value] = int(self.semgSamplingCombo.currentText())
        if SensorType.FNIRS.value in self.enabled_sensor_types:
            if hasattr(self, 'fnirsSamplingCombo'):
                self.config.sampling_rates[SensorType.FNIRS.value] = int(self.fnirsSamplingCombo.currentText())
    
    def generate_fnirs_configuration(self):
        """Generate fNIRS source-detector matrix configuration"""
        logger.info("Generating fNIRS configuration")
        
        try:
            if not hasattr(self, 'fnirsGridLayout'):
                logger.warning("fNIRS grid layout not available")
                return
            
            # Clear existing layout
            self._clear_layout(self.fnirsGridLayout)
            self.sensor_checkboxes['Source'].clear()
            self.sensor_checkboxes['Detect'].clear()
            
            # Update channel counts from UI
            if SensorType.FNIRS.value in self.enabled_sensor_types:
                if hasattr(self, 'fnirsSourcesSpinBox_2'):
                    self.config.channel_counts['fnirs_sources'] = self.fnirsSourcesSpinBox_2.value()
                if hasattr(self, 'fnirsDetectorsSpinBox_2'):
                    self.config.channel_counts['fnirs_detectors'] = self.fnirsDetectorsSpinBox_2.value()
            
            sensor_config = self.config.sensor_configs[SensorType.FNIRS.value]
            source_count = self.config.channel_counts['fnirs_sources']
            detector_count = self.config.channel_counts['fnirs_detectors']
            channels_per_row = sensor_config.channels_per_row
            
            logger.debug(f"Creating {source_count} sources and {detector_count} detectors, {channels_per_row} per row")
            
            # Create source checkboxes
            for i in range(source_count):
                row = i // channels_per_row
                col = i % channels_per_row
                
                checkbox = QCheckBox(f"{sensor_config.prefix[0]}{i+1:02d}")
                checkbox.setStyleSheet(f"QCheckBox {{ color: {sensor_config.color[0]}; font-weight: bold; }}")
                checkbox.stateChanged.connect(
                    lambda state, idx=i: self.update_sensor_channels('Source', idx, state))
                
                self.fnirsGridLayout.addWidget(checkbox, row, col)
                self.sensor_checkboxes['Source'].append(checkbox)
            
            # Create detector checkboxes (offset by source rows)
            source_rows = int(np.ceil(source_count / channels_per_row))
            
            for i in range(detector_count):
                row = i // channels_per_row + source_rows
                col = i % channels_per_row
                
                checkbox = QCheckBox(f"{sensor_config.prefix[1]}{i+1:02d}")
                checkbox.setStyleSheet(f"QCheckBox {{ color: {sensor_config.color[1]}; font-weight: bold; }}")
                checkbox.stateChanged.connect(
                    lambda state, idx=i: self.update_sensor_channels('Detect', idx, state))
                
                self.fnirsGridLayout.addWidget(checkbox, row, col)
                self.sensor_checkboxes['Detect'].append(checkbox)
            
            logger.info(f"Generated {source_count} source and {detector_count} detector checkboxes")
            
        except Exception as e:
            logger.error(f"Failed to generate fNIRS configuration: {e}")
            raise
    
    def update_sensor_channels(self, sensor_type: str, channel_idx: int, state: int):
        """Update sensor channel configuration"""
        try:
            logger.debug(f"Updating {sensor_type} channel {channel_idx} to state {state}")
            
            # Update brain locator if available
            if hasattr(self, 'brain_config_right') and hasattr(self.brain_config_right, 'set_current_node_info'):
                try:
                    self.brain_config_right.set_current_node_info(sensor_type, channel_idx + 1, state)
                    logger.debug(f"Updated brain locator for {sensor_type} channel {channel_idx + 1}")
                except Exception as e:
                    logger.warning(f"Failed to update brain locator: {e}")
            
            # Update enabled channels list
            if sensor_type in self.sensor_checkboxes:
                checkboxes = self.sensor_checkboxes[sensor_type]
                if sensor_type in self.config.enabled_channels:
                    self.config.enabled_channels[sensor_type] = [
                        i for i, checkbox in enumerate(checkboxes) if checkbox.isChecked()
                    ]
                    logger.debug(f"Updated enabled channels for {sensor_type}: {self.config.enabled_channels[sensor_type]}")
            
        except Exception as e:
            logger.error(f"Failed to update sensor channels for {sensor_type}: {e}")
    
    def update_channel_configuration(self, sensor_type: str):
        """Update channel configuration when counts change"""
        try:
            logger.debug(f"Updating channel configuration for {sensor_type}")
            
            # Check if configuration exists
            has_config = False
            if sensor_type in self.sensor_checkboxes:
                has_config = bool(self.sensor_checkboxes[sensor_type])
            elif sensor_type == SensorType.FNIRS.value:
                has_config = bool(self.sensor_checkboxes.get('Source', []))
            
            if has_config:
                self.generate_sensor_configuration(sensor_type)
                logger.info(f"Regenerated configuration for {sensor_type}")
            else:
                logger.debug(f"No existing configuration found for {sensor_type}")
                
        except Exception as e:
            logger.error(f"Failed to update channel configuration for {sensor_type}: {e}")
    
    def _clear_layout(self, layout):
        """Clear all widgets from a layout"""
        try:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            logger.debug("Layout cleared successfully")
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
                'metadata': {
                    'total_channels': {sensor: len(self.config.enabled_channels.get(sensor, [])) 
                                     for sensor in self.enabled_sensor_types},
                    'configuration_timestamp': QtCore.QDateTime.currentDateTime().toString(),
                    'enabled_sensors': list(self.enabled_sensor_types),
                    'version': '2.0',
                    'has_electrode_positions': bool(self.config.enabled_channel_pairs),
                    'has_valid_channels': bool(self.config.enabled_channel_pairs)
                }
            }
            
            # Add electrode positions if available
            if hasattr(self, 'brain_config_right'):
                try:
                    if SensorType.FNIRS.value in self.enabled_sensor_types:
                        if hasattr(self.brain_config_right, 'get_fnirs_pairs'):
                            config_dict['fnirs_pairs'] = self.brain_config_right.get_fnirs_pairs()
                        if hasattr(self.brain_config_right, 'get_sources'):
                            config_dict['sources'] = self.brain_config_right.get_sources()
                        if hasattr(self.brain_config_right, 'get_detectors'):
                            config_dict['detectors'] = self.brain_config_right.get_detectors()
                    
                    if SensorType.EEG.value in self.enabled_sensor_types:
                        if hasattr(self.brain_config_right, 'get_eeg_pairs'):
                            config_dict['eeg_pairs'] = self.brain_config_right.get_eeg_pairs()
                        if hasattr(self.brain_config_right, 'get_eeg_electrodes'):
                            config_dict['eeg_electrodes'] = self.brain_config_right.get_eeg_electrodes()
                    
                    logger.debug("Added electrode position data to configuration")
                except Exception as e:
                    logger.warning(f"Failed to get electrode data: {e}")
            
            logger.info("Configuration dictionary created successfully")
            return config_dict
            
        except Exception as e:
            logger.error(f"Failed to create configuration dictionary: {e}")
            raise
    
    def save_configuration(self):
        """Save current configuration to JSON file"""
        logger.info("Starting configuration save")
        
        try:
            # Get default file path in montage directory
            default_path = get_default_config_path("device_config.json")
            
            # Get save file path with montage directory as starting location
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存配置 Save Configuration", 
                default_path,  # Start in montage directory with default filename
                "JSON files (*.json);;All files (*)")
            if not file_path:
                logger.info("Save cancelled by user")
                return
            
            config_dict = self.get_configuration_dict()
            
            # Validate configuration before saving
            validation_result = self._validate_configuration_for_save(config_dict)
            if not validation_result['valid']:
                response = self._show_warning_message(
                    "Configuration Validation",
                    f"配置验证发现问题：\n{chr(10).join(validation_result['warnings'])}\n\n"
                    f"是否仍然保存？\n\n"
                    f"Configuration validation found issues:\n{chr(10).join(validation_result['warnings'])}\n\n"
                    f"Save anyway?"
                )
                if response != QMessageBox.Yes:
                    logger.info("Save cancelled due to validation issues")
                    return
            
            # Save to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            enabled_sensors_str = ", ".join([s.upper() for s in self.enabled_sensor_types])
            summary = self._get_save_summary(config_dict)
            
            self._show_info_message("Success", 
                f"配置保存成功！\nConfiguration saved successfully for {enabled_sensors_str}\n\n"
                f"Summary:\n{summary}\n\nFile: {file_path}")
            
            logger.info(f"Configuration saved successfully to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            self._show_error_message("Error", 
                f"配置保存失败：{str(e)}\nFailed to save configuration:\n{str(e)}")
    
    def _validate_configuration_for_save(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration before saving"""
        warnings = []
        
        try:
            # Check electrode positions
            if not config_dict.get('electrode_mapping') and SensorType.FNIRS.value in self.enabled_sensor_types:
                warnings.append("No electrode positions defined for fNIRS")
            
            # Check valid channels
            if not config_dict.get('fnirs_pairs') and SensorType.FNIRS.value in self.enabled_sensor_types:
                warnings.append("No valid fNIRS channel pairs found")
            
            # Check sampling rates
            for sensor in self.enabled_sensor_types:
                if sensor not in config_dict.get('sampling_rates', {}):
                    warnings.append(f"No sampling rate defined for {sensor.upper()}")
            
            logger.debug(f"Configuration validation: {len(warnings)} warnings")
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            warnings.append(f"Validation error: {str(e)}")
        
        return {'valid': len(warnings) == 0, 'warnings': warnings}
    
    def _get_save_summary(self, config_dict: Dict[str, Any]) -> str:
        """Get summary of saved configuration"""
        lines = []
        
        try:
            if 'fnirs_pairs' in config_dict:
                lines.append(f"fNIRS Channels: {len(config_dict['fnirs_pairs'])}")
            if 'sources' in config_dict:
                lines.append(f"Sources: {len(config_dict['sources'])}")
            if 'detectors' in config_dict:
                lines.append(f"Detectors: {len(config_dict['detectors'])}")
            if 'eeg_electrodes' in config_dict:
                lines.append(f"EEG Electrodes: {len(config_dict['eeg_electrodes'])}")
            
            # Add sampling rates summary
            if 'sampling_rates' in config_dict:
                for sensor, rate in config_dict['sampling_rates'].items():
                    lines.append(f"{sensor.upper()} Rate: {rate}Hz")
            
        except Exception as e:
            logger.error(f"Failed to generate save summary: {e}")
            lines.append("Summary generation failed")
        
        return '\n'.join(lines) if lines else "Basic configuration saved"
    
    def load_configuration(self):
        """Load configuration from JSON file"""
        logger.info("Starting configuration load")
        
        try:
            # Start file dialog in montage directory
            montage_dir_str = str(self.montage_dir)
            
            # Get load file path
            file_path, _ = QFileDialog.getOpenFileName(
                self, "加载配置 Load Configuration", 
                montage_dir_str,  # Start in montage directory
                "JSON files (*.json);;All files (*)")
            
            if not file_path or not os.path.exists(file_path):
                logger.info("Load cancelled or file not found")
                return
            
            # Load configuration from file
            with open(file_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            logger.info(f"Loaded configuration from {file_path}")
            
            # Validate compatibility
            if not self._validate_loaded_config(config_dict):
                return
            
            # Apply loaded configuration
            self._apply_loaded_configuration(config_dict)
            
            self._show_info_message("Success", 
                f"配置加载成功！\nConfiguration loaded successfully from:\n{file_path}")
            
            logger.info("Configuration loaded and applied successfully")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self._show_error_message("Error", 
                f"配置加载失败：{str(e)}\nFailed to load configuration:\n{str(e)}")
    
    def _validate_loaded_config(self, config_dict: Dict[str, Any]) -> bool:
        """Validate that loaded configuration is compatible"""
        try:
            if 'enabled_sensor_types' not in config_dict:
                self._show_error_message("Error", 
                    "配置文件格式不兼容\nLoaded configuration format is not compatible")
                return False
            
            loaded_sensors = set(config_dict['enabled_sensor_types'])
            current_sensors = self.enabled_sensor_types
            
            # Check compatibility
            incompatible_sensors = loaded_sensors - current_sensors
            if incompatible_sensors:
                incompatible_str = ", ".join([s.upper() for s in incompatible_sensors])
                current_str = ", ".join([s.upper() for s in current_sensors])
                
                response = self._show_warning_message("Sensor Type Mismatch",
                    f"配置文件包含当前未启用的传感器类型：{incompatible_str}\n"
                    f"当前启用的传感器：{current_str}\n\n"
                    f"是否继续加载兼容部分？\n\n"
                    f"Loaded config contains sensors not currently enabled: {incompatible_str}\n"
                    f"Currently enabled sensors: {current_str}\n\n"
                    f"Continue loading compatible parts?"
                )
                
                if response != QMessageBox.Yes:
                    logger.info("Load cancelled due to sensor mismatch")
                    return False
            
            logger.debug("Loaded configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            self._show_error_message("Error", f"Configuration validation failed: {str(e)}")
            return False
    
    def _apply_loaded_configuration(self, config_dict: Dict[str, Any]):
        """Apply loaded configuration to UI"""
        logger.info("Applying loaded configuration")
        
        try:
            # Apply sampling rates
            if 'sampling_rates' in config_dict:
                self._apply_loaded_sampling_rates(config_dict['sampling_rates'])
            
            # Apply channel counts
            if 'channel_counts' in config_dict:
                self._apply_loaded_channel_counts(config_dict['channel_counts'])
            
            # Apply enabled channels
            if 'enabled_channels' in config_dict:
                self._apply_loaded_enabled_channels(config_dict['enabled_channels'])
            
            # Apply electrode positions if available
            self._apply_loaded_electrode_positions(config_dict['enabled_channels'])
            
            logger.info("Loaded configuration applied successfully")
            
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
                        logger.debug(f"Applied {sensor} sampling rate: {sampling_rates[sensor]}")
                    except Exception as e:
                        logger.warning(f"Failed to set {sensor} sampling rate: {e}")
    
    def _apply_loaded_channel_counts(self, channel_counts: Dict[str, int]):
        """Apply loaded channel counts"""
        try:
            # EEG channels
            if (SensorType.EEG.value in self.enabled_sensor_types and 
                SensorType.EEG.value in channel_counts and 
                hasattr(self, 'eegChannelsSpinBox_2')):
                self.eegChannelsSpinBox_2.setValue(channel_counts[SensorType.EEG.value])
                self.config.channel_counts[SensorType.EEG.value] = channel_counts[SensorType.EEG.value]
                logger.debug(f"Applied EEG channel count: {channel_counts[SensorType.EEG.value]}")
            
            # sEMG channels
            if (SensorType.SEMG.value in self.enabled_sensor_types and 
                SensorType.SEMG.value in channel_counts and 
                hasattr(self, 'semgChannelsSpinBox_2')):
                self.semgChannelsSpinBox_2.setValue(channel_counts[SensorType.SEMG.value])
                self.config.channel_counts[SensorType.SEMG.value] = channel_counts[SensorType.SEMG.value]
                logger.debug(f"Applied sEMG channel count: {channel_counts[SensorType.SEMG.value]}")
            
            # fNIRS channels
            if SensorType.FNIRS.value in self.enabled_sensor_types:
                if 'fnirs_sources' in channel_counts and hasattr(self, 'fnirsSourcesSpinBox_2'):
                    self.fnirsSourcesSpinBox_2.setValue(channel_counts['fnirs_sources'])
                    self.config.channel_counts['fnirs_sources'] = channel_counts['fnirs_sources']
                    logger.debug(f"Applied fNIRS sources count: {channel_counts['fnirs_sources']}")
                
                if 'fnirs_detectors' in channel_counts and hasattr(self, 'fnirsDetectorsSpinBox_2'):
                    self.fnirsDetectorsSpinBox_2.setValue(channel_counts['fnirs_detectors'])
                    self.config.channel_counts['fnirs_detectors'] = channel_counts['fnirs_detectors']
                    logger.debug(f"Applied fNIRS detectors count: {channel_counts['fnirs_detectors']}")
                    
        except Exception as e:
            logger.error(f"Failed to apply loaded channel counts: {e}")
            raise
    
    def _apply_loaded_enabled_channels(self, enabled_channels: Dict[str, Any]):
        """Apply loaded enabled channels to checkboxes"""
        try:
            for sensor in self.enabled_sensor_types:
                if sensor in enabled_channels and sensor in self.sensor_checkboxes:
                    sensor_channels = enabled_channels[sensor]
                    checkboxes = self.sensor_checkboxes[sensor]
                    
                    if isinstance(sensor_channels, list):
                        for i in range(len(sensor_channels)):
                            if 0 <= i < len(checkboxes):
                                checkboxes[i].setChecked(True)
                                logger.debug(f"Enabled {sensor} channel {i}")
                    
                elif sensor == SensorType.FNIRS.value:
                    # Handle fNIRS source/detector channels
                    if 'Source' in self.sensor_checkboxes and 'fnirssource' in enabled_channels:
                        for i in range(len(enabled_channels['fnirssource'])):
                            if 0 <= i < len(self.sensor_checkboxes['Source']):
                                self.sensor_checkboxes['Source'][i].setChecked(True)
                                logger.debug(f"Enabled fNIRS source {i:02d}")
                    
                    if 'Detect' in self.sensor_checkboxes and 'fnirsdetect' in enabled_channels:
                        for i in range(len(enabled_channels['fnirsdetect'])):
                            if 0 <= i < len(self.sensor_checkboxes['Detect']):
                                self.sensor_checkboxes['Detect'][i].setChecked(True)
                                logger.debug(f"Enabled fNIRS detector {i:02d}")
            
            logger.debug("Applied loaded enabled channels")
            
        except Exception as e:
            logger.error(f"Failed to apply loaded enabled channels: {e}")
    
    def _apply_loaded_electrode_positions(self, config_dict: Dict[str, Any]):
        """Apply loaded electrode positions to the locator"""
        if not hasattr(self, 'brain_config_right'):
            logger.warning("Brain config widget not available for electrode positions")
            return
        
        try:
            self.brain_config_right.load_pairs_info(config_dict)
            # Reset locator first
            # if hasattr(self.brain_config_right, 'reset_all_electrodes'):
            #     self.brain_config_right.reset_all_electrodes()
            #     logger.debug("Reset electrode locator")
            
            # # Apply sources
            # if 'sources' in config_dict:
            #     for source_num, electrode_name in config_dict['sources'].items():
            #         self._simulate_electrode_assignment(electrode_name, 'Source', int(source_num))
            
            # # Apply detectors
            # if 'detectors' in config_dict:
            #     for detector_num, electrode_name in config_dict['detectors'].items():
            #         self._simulate_electrode_assignment(electrode_name, 'Detect', int(detector_num))
            
            # # Apply EEG electrodes
            # if 'eeg_electrodes' in config_dict:
            #     for eeg_num, electrode_name in config_dict['eeg_electrodes'].items():
            #         self._simulate_electrode_assignment(electrode_name, 'eeg', int(eeg_num))
            
            logger.info("Applied electrode positions from loaded configuration")
            
        except Exception as e:
            logger.error(f"Failed to apply electrode positions: {e}")
            self._show_warning_message("Warning", 
                f"重建电极位置时出错：{str(e)}\n"
                f"Failed to recreate electrode positions: {str(e)}")
    
    def _simulate_electrode_assignment(self, electrode_name: str, electrode_type: str, electrode_number: int):
        """Simulate electrode assignment in the locator"""
        try:
            # Update brain config if possible
            if hasattr(self.brain_config_right, 'set_current_node_info'):
                self.brain_config_right.set_current_node_info(electrode_type, electrode_number, True)
            
            # Store mapping for later use
            if not hasattr(self.config, 'electrode_mapping'):
                self.config.electrode_mapping = {}
            
            self.config.electrode_mapping[electrode_name] = {
                'type': electrode_type,
                'number': electrode_number
            }
            
            # Try to simulate electrode button click if available
            if hasattr(self.brain_config_right, '_on_electrode_left_click'):
                self.brain_config_right._on_electrode_left_click(electrode_name)
                logger.debug(f"Assigned {electrode_name} as {electrode_type} #{electrode_number}")
            else:
                logger.warning(f"Cannot simulate electrode assignment for {electrode_name}")
                
        except Exception as e:
            logger.error(f"Failed to assign electrode {electrode_name}: {e}")
    
    def reset_configuration(self):
        """Reset all configuration to default values"""
        logger.info("Resetting configuration")
        
        try:
            enabled_sensors_str = ", ".join([s.upper() for s in self.enabled_sensor_types])
            response = self._show_warning_message("重置配置 Reset Configuration", 
                f"确定要将所有配置重置为默认值吗？\n传感器类型：{enabled_sensors_str}\n\n"
                f"Are you sure you want to reset all configuration to default values?\n"
                f"Sensor types: {enabled_sensors_str}")
            
            if response == QMessageBox.Yes:
                # Reset configuration
                self.config = DeviceConfiguration(enabled_sensors=self.enabled_sensor_types)
                self._initialize_ui_values()
                
                # Clear generated configurations
                self._clear_all_sensor_layouts()
                
                # Clear checkbox references
                self._clear_checkbox_references()
                
                # Reset brain locator if available
                if hasattr(self, 'brain_config_right') and hasattr(self.brain_config_right, 'reset_all_electrodes'):
                    self.brain_config_right.reset_all_electrodes()
                
                self._show_info_message("Success", 
                    f"配置已重置为默认值！\n传感器类型：{enabled_sensors_str}\n\n"
                    f"Configuration reset to default values!\nSensor types: {enabled_sensors_str}")
                
                logger.info("Configuration reset completed successfully")
            else:
                logger.info("Configuration reset cancelled by user")
                
        except Exception as e:
            logger.error(f"Failed to reset configuration: {e}")
            self._show_error_message("Error", f"重置配置失败：{str(e)}\nFailed to reset configuration: {str(e)}")
    
    def _clear_all_sensor_layouts(self):
        """Clear all sensor layout configurations"""
        layout_mappings = {
            SensorType.EEG.value: 'eegGridLayout',
            SensorType.SEMG.value: 'semgGridLayout',
            SensorType.FNIRS.value: 'fnirsGridLayout'
        }
        
        for sensor, layout_name in layout_mappings.items():
            if sensor in self.enabled_sensor_types and hasattr(self, layout_name):
                try:
                    layout = getattr(self, layout_name)
                    self._clear_layout(layout)
                    logger.debug(f"Cleared {sensor} layout")
                except Exception as e:
                    logger.warning(f"Failed to clear {sensor} layout: {e}")
    
    def _clear_checkbox_references(self):
        """Clear all checkbox references"""
        try:
            for sensor_type in self.sensor_checkboxes:
                if sensor_type in [SensorType.EEG.value, SensorType.SEMG.value]:
                    self.sensor_checkboxes[sensor_type].clear()
                elif sensor_type in ['Source', 'Detect']:
                    self.sensor_checkboxes[sensor_type].clear()
            
            logger.debug("Cleared all checkbox references")
            
        except Exception as e:
            logger.error(f"Failed to clear checkbox references: {e}")
    
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
                    if isinstance(channels, list):
                        summary['total_channels'][sensor] = len(channels)
                    elif isinstance(channels, dict):
                        summary['total_channels'][sensor] = len(channels)
                    else:
                        summary['total_channels'][sensor] = 0
            
            logger.debug("Generated sensor summary")
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
            
            # Add basic sensor info
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
                try:
                    if SensorType.FNIRS.value in self.enabled_sensor_types:
                        if hasattr(self.brain_config_right, 'get_fnirs_pairs'):
                            pairs = self.brain_config_right.get_fnirs_pairs()
                            summary_lines.append(f"fNIRS Valid Pairs: {len(pairs)}")
                    
                    if SensorType.EEG.value in self.enabled_sensor_types:
                        if hasattr(self.brain_config_right, 'get_eeg_electrodes'):
                            electrodes = self.brain_config_right.get_eeg_electrodes()
                            summary_lines.append(f"EEG Positioned Electrodes: {len(electrodes)}")
                            
                except Exception as e:
                    logger.warning(f"Failed to get electrode summary: {e}")
            
            return '\n'.join(summary_lines) if summary_lines else "No configuration available"
            
        except Exception as e:
            logger.error(f"Failed to generate channel summary: {e}")
            return f"Summary generation failed: {str(e)}"


def create_configuration_manager(sensor_types: Union[List[str], int], parent=None) -> ConfigurationManager:
    """Factory function to create configuration manager with specific sensor types
    
    Args:
        sensor_types: Either an integer from SensorTypes class or list of sensor strings
        parent: Parent widget
    
    Returns:
        ConfigurationManager instance
    """
    if isinstance(sensor_types, int):
        logger.info(f"Creating configuration manager with integer sensor type: {sensor_types}")
    else:
        logger.info(f"Creating configuration manager with sensor list: {sensor_types}")
    
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
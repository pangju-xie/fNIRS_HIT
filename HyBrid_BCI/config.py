# -*- coding: utf-8 -*-

"""
Optimized Device Configuration Management System
Handles EEG, sEMG, and fNIRS device configuration with improved error handling and logging
"""

import sys
import json
import os
from typing import List, Dict, Set, Any, Optional, Union, Callable
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import traceback

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QApplication, QWidget, QCheckBox, QMessageBox, QFileDialog, QGroupBox
from PyQt5.QtCore import Qt, pyqtSignal
import numpy as np
from ui_config import Ui_ConfigForm, UIManager
import locate

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
                'fnirs_sources': 8,
                'fnirs_detectors': 8
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
            self.ui_manager = UIManager(self)
            self.ui_manager.setup_ui_for_sensors(self.enabled_sensor_types)
            
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
            self.ui_manager.initialize_ui_values(self.config)
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
            
            self.ui_manager.connect_controls(self.config, self)
            logger.debug("Signal connections established")
        except Exception as e:
            logger.error(f"Failed to setup connections: {e}")
            raise
    
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
    
    def _show_message(self, msg_type: str, title: str, message: str):
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
    
    def _show_warning_message(self, title: str, message: str):
        return self._show_message("warning", title, message)
    
    def apply_channel_config(self):
        """Apply channel configuration"""
        logger.info("Apply channel config called")
        
        try:
            sample_rate_order = self._generate_sample_rate_order()
            config_order = self._generate_config_order()
            return self.sensor_types, sample_rate_order, config_order
        except Exception as e:
            logger.error(f"Failed to apply sampling rates: {e}")
            self._show_error_message("Error", f"无效的采样率值：{str(e)}")
    
    def _generate_sample_rate_order(self):
        """Generate sample rate order for enabled sensor types"""
        return self.ui_manager.process_sensor_configurations(self.enabled_sensor_types, "sampling rate")
    
    def _generate_config_order(self):
        """Generate config order for enabled sensor types"""
        return self._process_config_configurations()
    
    def _process_config_configurations(self):
        """Process configuration configurations with proper error handling"""
        updated_sensors = []
        
        for type_key, channel_data in self.config.enabled_channels.items():
            try:
                if type_key == SensorType.FNIRS.value:
                    self._process_fnirs_configuration(updated_sensors, channel_data)
                elif type_key in [SensorType.EEG.value, SensorType.SEMG.value]:
                    self._process_standard_sensor_configuration(updated_sensors, type_key, channel_data)
                else:
                    logger.debug(f"Skipping unknown sensor type: {type_key}")
                    
            except Exception as e:
                logger.error(f"Error processing {type_key}: {e}")
                continue
        logger.info(f"Configuration processing complete. Length: {len(updated_sensors)}")
        return updated_sensors

    def _process_fnirs_configuration(self, updated_sensors, channel_data):
        """Process fNIRS configuration separately for clarity"""
        if not isinstance(channel_data, dict):
            logger.error("fNIRS channel data must be a dictionary")
            return
        
        source_count = self.config.channel_counts.get('fnirs_sources', 0)
        detect_count = self.config.channel_counts.get('fnirs_detectors', 0)
        
        if source_count <= 0 or detect_count <= 0:
            logger.error(f"Invalid fNIRS counts: sources={source_count}, detectors={detect_count}")
            return
        
        fnirs_buf = [0] * source_count
        updated_sensors.extend([SensorTypes.FNIRS, source_count, detect_count])
        
        # Process channel pairs
        for pair_name in channel_data.keys():
            try:
                if '-' not in pair_name:
                    logger.warning(f"Invalid fNIRS pair format: {pair_name}")
                    continue
                    
                parts = pair_name.split('-')
                if len(parts) != 2:
                    logger.warning(f"Invalid fNIRS pair format: {pair_name}")
                    continue
                
                # Extract source and detector indices
                source_str, detect_str = parts
                if not (source_str.startswith('S') and detect_str.startswith('D')):
                    logger.warning(f"Invalid fNIRS naming: {pair_name}")
                    continue
                
                source = int(source_str[1:]) - 1  # Convert to 0-based
                detect = int(detect_str[1:]) - 1   # Convert to 0-based
                
                # Validate indices
                if not (0 <= source < source_count):
                    logger.error(f"Source index out of range: {source} (max: {source_count-1})")
                    continue
                if not (0 <= detect < detect_count):
                    logger.error(f"Detector index out of range: {detect} (max: {detect_count-1})")
                    continue
                
                # Set bit for this source-detector pair
                fnirs_buf[source] |= (1 << detect)
                
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing fNIRS pair {pair_name}: {e}")
                continue
        
        # Convert to bytes
        d_bytes = (detect_count + 7) // 8  # Ceiling division
        for value in fnirs_buf:
            buf = [(value >> ((d_bytes - i - 1) * 8)) & 0xff for i in range(d_bytes)]
            updated_sensors.extend(buf)

    def _process_standard_sensor_configuration(self, updated_sensors, sensor_type, channel_data):
        """Process EEG/sEMG configuration with proper bit manipulation"""
        if not isinstance(channel_data, (list, dict)):
            logger.error(f"{sensor_type} channel data must be list or dict")
            return
        
        count = self.config.channel_counts.get(sensor_type, 0)
        if count <= 0:
            logger.error(f"Invalid channel count for {sensor_type}: {count}")
            return
        
        # Map sensor type to enum value
        sensor_type_map = {
            SensorType.EEG.value: SensorTypes.EEG,
            SensorType.SEMG.value: SensorTypes.SEMG
        }
        
        sensor_id = sensor_type_map.get(sensor_type)
        if sensor_id is None:
            logger.error(f"Unknown sensor type: {sensor_type}")
            return
        
        updated_sensors.extend([sensor_id, count])
        value = 0
        
        # Process channels
        if isinstance(channel_data, list):
            # List of enabled channel indices
            for channel_idx in channel_data:
                if isinstance(channel_idx, int) and 0 <= channel_idx < count:
                    value |= (1 << channel_idx)  # Fix: Use OR to set bits
                else:
                    logger.warning(f"Invalid channel index: {channel_idx}")
                    
        elif isinstance(channel_data, dict):
            # Dictionary format (channel_name: data)
            for channel_name in channel_data.keys():
                try:
                    if isinstance(channel_name, str) and channel_name.isdigit():
                        channel_idx = int(channel_name) - 1  # Convert to 0-based
                    elif isinstance(channel_name, int):
                        channel_idx = channel_name
                    else:
                        logger.warning(f"Invalid channel name format: {channel_name}")
                        continue
                    
                    if 0 <= channel_idx < count:
                        value |= (1 << channel_idx)  # Fix: Use OR to set bits
                    else:
                        logger.warning(f"Channel index out of range: {channel_idx}")
                        
                except ValueError as e:
                    logger.error(f"Error parsing channel {channel_name}: {e}")
                    continue
        
        # Convert to bytes
        d_bytes = (count + 7) // 8  # Ceiling division
        buf = [(value >> ((d_bytes - i - 1) * 8)) & 0xff for i in range(d_bytes)]
        updated_sensors.extend(buf)
    
    def create_configuration(self):
        """Generate channel configuration based on current settings"""
        logger.info("Creating configuration")
        
        try:
            self.ui_manager.update_channel_counts_from_ui(self.config)
            self.ui_manager.add_control_buttons(self.enabled_sensor_types, self)
            
            for sensor_type in self.enabled_sensor_types:
                self.generate_sensor_configuration(sensor_type)
            
            logger.info("Configuration creation completed successfully")
        except Exception as e:
            logger.error(f"Configuration creation failed: {e}")
            self._show_error_message("Error", f"配置生成失败：{str(e)}")
    
    def generate_sensor_configuration(self, sensor_type: str):
        """Generate configuration for specific sensor type"""
        try:
            if sensor_type == SensorType.FNIRS.value:
                self.ui_manager.generate_fnirs_configuration(self.config, self.sensor_checkboxes, self)
            else:
                self.ui_manager.generate_standard_sensor_config(sensor_type, self.config, self.sensor_checkboxes, self)
        except Exception as e:
            logger.error(f"Failed to generate configuration for {sensor_type}: {e}")
            raise
    
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
        self.ui_manager.modify_sample_rate(self.config, self.enabled_sensor_types)
    
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
                'metadata': self._generate_metadata()
            }
            
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
        }
    
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
                (not config_dict['enabled_channels'].get('fnirs') and SensorType.FNIRS.value in self.enabled_sensor_types,
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
            
            self.ui_manager.apply_loaded_configuration(config_dict, self.config, self.enabled_sensor_types)
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
                self.ui_manager.initialize_ui_values(self.config)
                self.ui_manager.clear_all_configurations(self.sensor_checkboxes)
                
                # Reset brain locator if available
                if (hasattr(self, 'brain_config_right') and 
                    hasattr(self.brain_config_right, 'reset_all_electrodes')):
                    self.brain_config_right.reset_all_electrodes()
                
                self._show_info_message("Success", 
                    f"配置已重置为默认值！\n传感器类型：{enabled_sensors_str}")
                
        except Exception as e:
            logger.error(f"Failed to reset configuration: {e}")
            self._show_error_message("Error", f"重置配置失败：{str(e)}")
    
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
        return ConfigurationManager(sensor_types, parent) # type: ignore
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
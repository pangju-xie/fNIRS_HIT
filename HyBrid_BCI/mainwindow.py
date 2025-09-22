# -*- coding: utf-8 -*-

import sys
import logging
import os
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer, pyqtSignal, QObject, QSettings
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

# Import the UI configuration that matches the XML definition
from ui_mainwindow import Ui_MainWindow
import network
import user
import fNIRS
from config import ConfigurationManager
import qualify


os.environ['NUMEXPR_MAX_THREADS'] = '16'  # Limit numexpr threads to prevent oversubscription

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fnirs_app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class WorkflowStates:
    """Define workflow states and transitions"""
    DISCONNECTED = 0
    CONNECTED = 1
    CONFIGURED = 2
    TESTED = 3
    ACQUIRED = 4
    ANALYZED = 5
    
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


class MainWindow(QMainWindow):
    """
    Main window using the exact UI structure from mainwindow.ui
    """
    
    # Define custom signals for better component communication
    deviceConnectionChanged = pyqtSignal(bool)
    workflowStateChanged = pyqtSignal(int)
    batteryLevelChanged = pyqtSignal(int)
    configurationChanged = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Initialize state variables
        self._init_state_variables()
        
        # Settings for window state persistence
        self.settings = QSettings('fNIRS Solutions', 'fNIRS Data Acquisition System')
        
        # Initialize components in proper order
        self._initialize_components()
        
        logger.info("MainWindow initialized successfully with UI structure from XML")
    
    def _init_state_variables(self):
        """Initialize all state variables"""
        self.current_state = WorkflowStates.DISCONNECTED
        self.is_connecting = False
        self.is_disconnecting = False
        self.is_shutting_down = False
        self.sensor_type = SensorTypes.NotInit
        self.sensors = {}
        self.config_widget = None
        self.connection_timeout_timer = None
        self.battery_query_timer = None
    
    def _initialize_components(self):
        """Initialize all components in proper order"""
        self.initialize_network()
        self.initialize_user_widget()
        # self.initialize_qualify_widget()
        self.setup_ui_connections()
        self.setup_timers()
        self.update_ui_state()
        self.restore_window_state()
        self.ui.tabWidget.setCurrentIndex(0)
        
        logger.info("MainWindow initialized successfully with UI structure from XML")

    def initialize_network(self):
        """Initialize network module with comprehensive error handling"""
        try:
            self.network = network.UdpPort(1227, 2227)
            self.setup_network_connections()
            logger.info("Network module initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize network: {e}")
            QMessageBox.critical(self, "Network Error", f"Failed to initialize network:\n{e}")
            self.network = None
    
    def initialize_user_widget(self):
        """Initialize and integrate user widget into home tab"""
        try:
            self.user_widget = user.UserInfoManager()
            self.ui.homeLayout.addWidget(self.user_widget)
            
            # Connect user widget signals if available
            if hasattr(self.user_widget, 'patientChanged'):
                self.user_widget.patientChanged.connect(self.on_patient_changed)
            
            logger.info("User widget integrated into home tab successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize user widget: {e}")
            self._add_placeholder_to_layout(self.ui.homeLayout, "User widget could not be loaded")

    def initialize_config_widget(self, sensor_types):
        """Initialize and integrate configuration manager into configuration tab"""
        try:
            self.config_widget = ConfigurationManager(sensor_types)
            self.ui.configLayout.addWidget(self.config_widget)
            
            # Connect configuration manager signals
            self.config_widget.OnConfigSet.connect(self.on_config_set)
            self.deviceConnectionChanged.connect(self.update_config_manager_state)
            
        except Exception as e:
            logger.error(f"Failed to initialize configuration manager: {e}")
            self._add_placeholder_to_layout(self.ui.configLayout, "Configuration manager could not be loaded")

    def initialize_qualify_widget(self):
        """Initialize and integrate config widget into home tab"""
        try:
            self.qualify_widget = qualify.QualifyApp()
            self.ui.testLayout.addWidget(self.qualify_widget)
            self.config_widget.OnConfigApplied.connect(self.qualify_widget.initialize_channels) # type: ignore
            logger.info("Qualify widget integrated into home tab successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize config widget: {e}")
            # Add placeholder to home tab if qyalify widget fails
            self._add_placeholder_to_layout(self.ui.testLayout, "Qualify widget could not be loaded")

    def _add_placeholder_to_layout(self, layout, message):
        """Add placeholder label to layout"""
        placeholder = QtWidgets.QLabel(message)
        placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("QLabel { color: #f44336; font-style: italic; }")
        layout.addWidget(placeholder)

    def setup_timers(self):
        """Setup all timers with proper configuration"""
        # Connection timeout timer
        self.connection_timeout_timer = QTimer()
        self.connection_timeout_timer.setSingleShot(True)
        self.connection_timeout_timer.timeout.connect(self.on_connection_timeout)
        
        # Battery monitoring timer
        self.battery_query_timer = QTimer()
        self.battery_query_timer.timeout.connect(self.query_battery)
        self.battery_query_timer.setSingleShot(False)
    
    def setup_network_connections(self):
        """Setup network signal connections"""
        if not self.network:
            return
            
        connections = [
            (self.network.onDeviceConnected, self.on_device_connected),
            (self.network.onDeviceDisconnected, self.on_device_disconnected),
            (self.network.onDeviceSample, self.on_sample_start_stop),
            (self.network.onDataReceived, self.on_data_received),
            (self.network.onDataPatched, self.on_data_patched),
            (self.network.onBatteryUpdated, self.on_battery_updated),
            (self.network.onSampleRateSetDone, self.on_sample_rate_set_done),
            (self.network.onChannelConfigSetDone, self.on_channel_config_set_done),
            (self.network.networkError, self.on_network_error)
        ]
        
        for signal, slot in connections:
            signal.connect(slot)
    
    def setup_ui_connections(self):
        """Setup UI signal-slot connections using the UI structure from XML"""
        # Button connections
        self.ui.connectButton.clicked.connect(self.handle_connection_toggle)
        
        # Tab change handling
        self.ui.tabWidget.currentChanged.connect(self.on_tab_changed)
        
        # Menu actions
        menu_connections = [
            (self.ui.saveAction, self.save_data),
            (self.ui.exportAction, self.export_data),
            (self.ui.exitAction, self.close),
            (self.ui.preferencesAction, self.show_preferences),
            (self.ui.aboutAction, self.show_about)
        ]
        
        for action, slot in menu_connections:
            action.triggered.connect(slot)
        
        # Connect custom signals

        signal_connections = [
            (self.deviceConnectionChanged, self.on_device_connection_changed),
            (self.workflowStateChanged, self.on_workflow_state_changed),
            (self.batteryLevelChanged, self.update_battery_display),
            (self.configurationChanged, self.on_configuration_changed),
            
        ]
        
        for signal, slot in signal_connections:
            signal.connect(slot)
    
    def on_config_set(self, sample_data, channel_config):
        """Handle sample rate configuration from config manager"""
        try:
            logger.info("Config sample rate and channels")
            
            # Send configuration to network if connected
            if self.network and self.current_state >= WorkflowStates.CONNECTED:
                self.network.sendSampleRate(sample_data)
                self.network.sendChannelConfig(channel_config)
            
        except Exception as e:
            logger.error(f"Error handling sample rate configuration: {e}")
    
    def update_config_manager_state(self, connected):
        """Update configuration manager state based on device connection"""
        if not self.config_widget:
            return
            
        try:
            if connected and self.sensor_type != SensorTypes.NotInit:
                logger.info(f"Updating config manager with sensor type: {self.sensor_type}")
                
                # Recreate config manager if sensor types don't match
                if (hasattr(self.config_widget, 'sensor_types') and 
                    self.config_widget.sensor_types != self.sensor_type):
                    self._recreate_config_manager_for_sensor_type()
            
            self.config_widget.setEnabled(connected)
            logger.debug(f"Configuration manager state updated: enabled={connected}")
            
        except Exception as e:
            logger.error(f"Error updating configuration manager state: {e}")
    
    def _recreate_config_manager_for_sensor_type(self):
        """Recreate configuration manager with correct sensor type"""
        try:
            if not hasattr(self.ui, 'configLayout'):
                return
                
            # Remove old config manager
            if self.config_widget:
                self.ui.configLayout.removeWidget(self.config_widget)
                self.config_widget.deleteLater()
            
            # Create new config manager
            self.config_widget = ConfigurationManager(sensor_types=self.sensor_type)
            self.ui.configLayout.addWidget(self.config_widget)
            self.config_widget.setEnabled(self.current_state >= WorkflowStates.CONNECTED)
            
            logger.info(f"Configuration manager recreated for sensor type: {self.sensor_type}")
            
        except Exception as e:
            logger.error(f"Failed to recreate configuration manager: {e}")
    
    def get_current_configuration(self):
        """Get current configuration from config manager"""
        if self.config_widget:
            try:
                return self.config_widget.get_configuration_dict()
            except Exception as e:
                logger.error(f"Failed to get current configuration: {e}")
        return {}
    
    def get_configuration_summary(self):
        """Get configuration summary for display"""
        if self.config_widget:
            try:
                return self.config_widget.get_channel_summary()
            except Exception as e:
                logger.error(f"Failed to get configuration summary: {e}")
                return "Configuration summary not available"
        return "Configuration manager not initialized"
    
    def on_configuration_changed(self):
        """Handle configuration changes"""
        try:
            if self.config_widget:
                summary = self.config_widget.get_sensor_summary()
                enabled_sensors = summary.get('enabled_sensors', [])
                if enabled_sensors:
                    sensors_str = ", ".join([s.upper() for s in enabled_sensors])
                    self.update_status(f"Configuration updated - {sensors_str}", "#2196f3")
            
            logger.debug("Configuration changed event handled")
            
        except Exception as e:
            logger.error(f"Error handling configuration change: {e}")
    
    def on_tab_changed(self, index):
        """Handle tab change events and workflow progression"""
        if self.is_shutting_down:
            return
            
        try:
            tab_names = ['home', 'configuration', 'test', 'acquisition', 'analysis']
            if 0 <= index < len(tab_names):
                current_tab = tab_names[index]
                logger.debug(f"Tab changed to: {current_tab} (index: {index})")
                
                # Special handling for configuration tab
                if current_tab == 'configuration' and self.config_widget:
                    self.config_widget.update_ui_state()
                
                # Trigger workflow progression
                self.handle_workflow_progression(current_tab, index)
                
        except Exception as e:
            logger.error(f"Error handling tab change: {e}")
    
    def handle_workflow_progression(self, tab_name, tab_index):
        """Handle workflow progression when switching tabs"""
        try:
            progression_map = {
                ('configuration', WorkflowStates.CONNECTED): self.complete_configuration,
                ('test', WorkflowStates.CONFIGURED): self.complete_test,
                ('acquisition', WorkflowStates.TESTED): self.complete_acquisition,
                ('analysis', WorkflowStates.ACQUIRED): self.complete_analysis
            }
            
            key = (tab_name, self.current_state)
            if key in progression_map:
                QTimer.singleShot(1500, progression_map[key])
                
        except Exception as e:
            logger.error(f"Error in workflow progression: {e}")
    
    def handle_connection_toggle(self):
        """Handle connection/disconnection button click"""
        if self.is_shutting_down or not self.network:
            if not self.network:
                self.show_error_message("Network module not available")
            return
            
        try:
            if self.current_state == WorkflowStates.DISCONNECTED and not self.is_connecting:
                self.connect_device()
            elif self.current_state >= WorkflowStates.CONNECTED or self.is_connecting:
                self.disconnect_device()
        except Exception as e:
            logger.error(f"Connection toggle failed: {e}")
            self.show_error_message(f"Connection operation failed: {e}")
    
    def connect_device(self):
        """Initiate device connection with improved UI feedback"""
        if self.is_shutting_down or self.is_connecting:
            return
            
        try:
            self._set_connection_ui_state(True, "正在连接...")
            self.update_status("Connecting to devices...", "#ff9800")
            self.update_connection_indicator(False, "正在连接...")
            
            self.stop_battery_monitoring()
            self.network.sendConnect() # type: ignore
            self.connection_timeout_timer.start(10000) # type: ignore
            
        except Exception as e:
            self.reset_connection_ui()
            logger.error(f"Connection initiation failed: {e}")
            self.show_error_message(f"Failed to start connection: {e}")
    
    def disconnect_device(self):
        """Initiate device disconnection with proper cleanup"""
        if self.is_shutting_down or self.is_disconnecting:
            return
            
        try:
            self._set_disconnection_ui_state()
            self.stop_all_timers()
            
            # Send disconnection command if devices are connected
            if self.network and len(self.network.get_connected_devices()) > 0:
                self.network.sendDisconnect()
                QTimer.singleShot(3000, self.force_disconnect)
            else:
                QTimer.singleShot(100, self.on_device_disconnected)
            
        except Exception as e:
            logger.error(f"Disconnection failed: {e}")
            self.show_error_message(f"Failed to disconnect: {e}")
            self.force_disconnect()
    
    def _set_connection_ui_state(self, connecting=False, text="连接设备"):
        """Set UI state for connection operations"""
        self.is_connecting = connecting
        self.ui.connectButton.setEnabled(not connecting)
        self.ui.connectButton.setText(text)
    
    def _set_disconnection_ui_state(self):
        """Set UI state for disconnection operations"""
        self.is_disconnecting = True
        self.ui.connectButton.setEnabled(False)
        self.ui.connectButton.setText("正在断开...")
        self.update_status("Disconnecting devices...", "#ff9800")
        self.update_connection_indicator(False, "正在断开...")
    
    def force_disconnect(self):
        """Force disconnection if normal disconnect fails"""
        if not self.is_shutting_down:
            logger.warning("Forcing disconnection due to timeout")
            self.on_device_disconnected()
    
    def stop_all_timers(self):
        """Stop all active timers safely"""
        timers = [self.connection_timeout_timer, self.battery_query_timer]
        for timer in timers:
            if timer and timer.isActive():
                timer.stop()
    
    def stop_battery_monitoring(self):
        """Stop battery monitoring safely"""
        if self.battery_query_timer and self.battery_query_timer.isActive():
            self.battery_query_timer.stop()
            logger.debug("Battery monitoring stopped")
    
    def on_connection_timeout(self):
        """Handle connection timeout"""
        if self.is_connecting and not self.is_shutting_down:
            self.reset_connection_ui()
            self.update_status("Connection timeout - no devices found", "#f44336")
            self.update_connection_indicator(False, "连接超时")
            logger.warning("Connection attempt timed out")
    
    def reset_connection_ui(self):
        """Reset connection UI to disconnected state"""
        if not self.is_shutting_down:
            self.ui.connectButton.setEnabled(True)
            self.ui.connectButton.setText("连接设备")
        self.is_connecting = False
        self.is_disconnecting = False

    ########   handle device connect/disconnect    ########
    
    def on_device_connected(self, sensor_id, sensor_type):
        """Handle device connected signal with enhanced UI updates"""
        if self.is_shutting_down:
            return
            
        try:
            if self.connection_timeout_timer.isActive(): # type: ignore
                self.connection_timeout_timer.stop() # type: ignore
            
            self.is_connecting = False
            self.current_state = WorkflowStates.CONNECTED
            
            # Update device and sensor info
            self.update_device_info(sensor_id, sensor_type)
            self.init_sensor(sensor_type, self.user_widget.current_patient.to_dict()) # type: ignore
            
            # Update UI
            self._set_connected_ui_state()
            self.start_battery_monitoring()
            
            # Emit signals and initialize config manager
            self.deviceConnectionChanged.emit(True)
            self.workflowStateChanged.emit(self.current_state)
            self.initialize_config_widget(sensor_type)
            
            logger.info(f"Device connected successfully: ID={sensor_id}, Type={sensor_type}")
            
        except Exception as e:
            logger.error(f"Error handling device connection: {e}")
    
    def _set_connected_ui_state(self):
        """Set UI state for connected devices"""
        self.ui.connectButton.setText("断开连接")
        self.ui.connectButton.setEnabled(True)
        
        device_count = len(self.network.get_connected_devices()) if self.network else 1
        self.update_status(f"Connected to {device_count} device(s)", "#4caf50")
        self.update_connection_indicator(True, f"{device_count} 个设备")
    
    def on_device_disconnected(self):
        """Handle device disconnected signal with comprehensive cleanup"""
        if self.is_shutting_down:
            return
            
        try:
            self.stop_all_timers()
            self._reset_to_disconnected_state()
            self._reset_ui_elements()
            
            # Emit signals
            self.deviceConnectionChanged.emit(False)
            self.workflowStateChanged.emit(self.current_state)
            
            logger.info("Device disconnected successfully")
            
        except Exception as e:
            logger.error(f"Error handling device disconnection: {e}")
    
    def _reset_to_disconnected_state(self):
        """Reset internal state to disconnected"""
        self.current_state = WorkflowStates.DISCONNECTED
        self.is_disconnecting = False
        self.sensor_type = SensorTypes.NotInit
    
    def _reset_ui_elements(self):
        """Reset UI elements to disconnected state"""
        self.update_device_info('--', '--')
        self.ui.batteryProgressBar.setValue(0)
        self.ui.batteryProgressBar.setStyleSheet("")
        self.reset_connection_ui()
        self.update_status("Device disconnected", "#2196f3")
        self.update_connection_indicator(False, "已断开")
        self.ui.tabWidget.setCurrentIndex(0)
    
    def update_connection_indicator(self, connected, status_text=""):
        """Update the connection status indicator"""
        try:
            if connected:
                self.ui.connectionStatusLabel.setText("🟢 已连接")
                self.ui.connectionStatusLabel.setStyleSheet("QLabel { color: #4caf50; font-weight: bold; }")
            else:
                status_display = status_text if status_text else "未连接"
                self.ui.connectionStatusLabel.setText(f"⚫ {status_display}")
                self.ui.connectionStatusLabel.setStyleSheet("QLabel { color: #f44336; font-weight: bold; }")
                
            # Update device count
            device_count = 0
            if self.network and connected:
                device_count = len(self.network.get_connected_devices())
            self.ui.deviceCountLabel.setText(f"数量: {device_count}")
                
        except Exception as e:
            logger.error(f"Error updating connection indicator: {e}")

    def on_device_connection_changed(self, connected):
        """Handle device connection state changes"""
        self.update_ui_state()
    
    def on_workflow_state_changed(self, new_state):
        """Handle workflow state changes"""
        self.update_ui_state()
            
    def update_device_info(self, device_id, device_type):
        """Update device information display in status area"""
        if self.is_shutting_down:
            return
            
        try:
            if device_id != "--" and device_type != "--":
                # Format device ID
                if isinstance(device_id, list):
                    id_str = "-".join([f"{x:02X}" for x in device_id])
                else:
                    id_str = str(device_id)
                
                # Map device type to readable name
                type_names = {
                    1: "EEG", 2: "sEMG", 3: "EEG/sEMG", 4: "fNIRS",
                    5: "EEG/fNIRS", 6: "sEMG/fNIRS", 7: "EEG/sEMG/fNIRS"
                }
                type_name = type_names.get(device_type, f"Type-{device_type}")
                
                self.ui.deviceIdLabel.setText(f"设备 ID: {id_str}")
                self.ui.deviceTypeLabel.setText(f"设备类型: {type_name}")
            else:
                self.ui.deviceIdLabel.setText("设备 ID: --")
                self.ui.deviceTypeLabel.setText("设备类型: --")
                
        except Exception as e:
            logger.error(f"Error updating device info: {e}")
    
    ########   handle battery issue    ########
        
    def start_battery_monitoring(self):
        """Start battery level monitoring for connected devices"""
        if (self.is_shutting_down or not self.network or 
            self.current_state < WorkflowStates.CONNECTED or
            len(self.network.get_connected_devices()) == 0):
            return
        
        try:
            self.query_battery()
            if not self.battery_query_timer.isActive(): # type: ignore
                self.battery_query_timer.start(10000) # type: ignore
                logger.debug("Battery monitoring started")
        except Exception as e:
            logger.warning(f"Failed to start battery monitoring: {e}")
    
    def query_battery(self):
        """Query battery status from devices with safety checks"""
        if (self.is_shutting_down or not self.network or 
            self.current_state < WorkflowStates.CONNECTED or
            len(self.network.get_connected_devices()) == 0):
            self.stop_battery_monitoring()
            return
        
        try:
            self.network.sendBatteryQuery()
            logger.debug("Battery query sent")
        except Exception as e:
            logger.warning(f"Battery query failed: {e}")
            self.stop_battery_monitoring()
    
    def on_battery_updated(self, battery_level):
        """Handle battery level update from network"""
        if not self.is_shutting_down:
            self.batteryLevelChanged.emit(battery_level)
    
    def update_battery_display(self, battery_level):
        """Update battery display elements"""
        if self.is_shutting_down:
            return
            
        try:
            self.ui.batteryProgressBar.setValue(battery_level)
            
            # Update color based on battery level
            color_map = {
                (0, 20): "#f44336",    # Red
                (20, 50): "#ff9800",   # Orange
                (50, 101): "#4caf50"   # Green
            }
            
            color = next(color for (low, high), color in color_map.items() 
                        if low <= battery_level < high)
            
            self.ui.batteryProgressBar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {color}; }}"
            )
            
            logger.debug(f"Battery level updated: {battery_level}%")
            
        except Exception as e:
            logger.error(f"Error updating battery display: {e}")
    
    ########   handle configuration    ########
    
    def on_sample_rate_set_done(self, valid: bool):
        """Handle sample rate config done"""
        if self.config_widget and valid:
            self.config_widget.sample_rate_send_done = valid
            sample_rate = self.config_widget.get_sample_rate()
            for sensor, rates in sample_rate.items():
                if sensor in self.sensors.keys() and sensor == 'fnirs':
                    self.sensors[sensor].setSampleRate(rates)
                elif sensor in self.sensors.keys() and sensor == 'eeg':
                    pass
                elif sensor in self.sensors.keys() and sensor == 'semg':
                    pass
                
            self.complete_configuration()
        
    def on_channel_config_set_done(self, valid: bool):
        """Handle channel config done"""
        if self.config_widget and valid:
            self.config_widget.channel_config_send_done = valid
            for sensor in self.sensors.keys():
                if sensor == 'fnirs':
                    self.sensors[sensor].setMontage(self.config_widget.get_fnirs_source_detector())
                elif sensor == 'eeg':
                    pass
                elif sensor == 'semg':
                    pass
                
            self.complete_configuration()
    
    ########   handle data receive    ########
    
    def on_sample_start_stop(self, is_start:bool):
        
        #start data sample
        if is_start:
            pass
        #stop data sample
        else:
            pass
        return 
    
    def on_data_received(self, sensor_type, packet_id, data):
        if sensor_type == SensorTypes.FNIRS:
            self.sensors['fnirs'].updataData(packet_id, data)
        elif sensor_type == SensorTypes.EEG:
            pass
        elif sensor_type == SensorTypes.SEMG:
            pass
            
        return
    
    def on_data_patched(self, sensor_type, packet_id, data):
        return
    
    ########   handle network error    ########
    
    def on_network_error(self, error_message):
        """Handle network errors with appropriate user feedback"""
        if self.is_shutting_down:
            return
            
        logger.error(f"Network error: {error_message}")
        self.update_status(f"Network error: {error_message}", "#f44336")
        
        # If it's a connection error, trigger disconnection
        if "connection" in error_message.lower():
            self.on_device_disconnected()
        
        if not self.is_shutting_down:
            self.show_error_message(f"Network Error: {error_message}")

    def init_sensor(self, sensor_type, subj_dict):
        """Initialize sensor type and related components"""
        if self.is_shutting_down:
            return
            
        try:
            self.sensor_type = sensor_type
            self.sensors.clear()
            
            sensor_map = {
                SensorTypes.EEG: 'eeg',
                SensorTypes.SEMG: 'semg',
                SensorTypes.FNIRS: 'fnirs'
            }
            
            for sensor_bit, sensor_name in sensor_map.items():
                if sensor_type & sensor_bit:
                    if sensor_name == 'fnirs':
                        self.sensors[sensor_name] = fNIRS.fNIRS(subj_dict)
                    else:
                        self.sensors[sensor_name] = True
            
            logger.info(f"Sensor initialized with {len(self.sensors)} types: {list(self.sensors.keys())}")
            
            # Update configuration manager if needed
            if (self.config_widget and 
                getattr(self.config_widget, 'sensor_types', None) != sensor_type):
                logger.info(f"Updating configuration manager sensor type to {sensor_type}")
                self._recreate_config_manager_for_sensor_type()
            
        except Exception as e:
            logger.error(f"Error initializing sensor: {e}")
    

    def update_status(self, message, color="#333333"):
        """Update status label with message and color"""
        if self.is_shutting_down:
            return
            
        try:
            self.ui.statusInfoLabel.setText(f"Status: {message}")
            self.ui.statusInfoLabel.setStyleSheet(f"QLabel {{ color: {color}; font-weight: bold; }}")
        except Exception as e:
            logger.error(f"Error updating status: {e}")
    
    def show_error_message(self, message):
        """Show error message dialog"""
        if not self.is_shutting_down:
            QMessageBox.critical(self, "Error", message)
    
    def _complete_workflow_step(self, required_state, new_state, message):
        """Generic workflow step completion"""
        if self.is_shutting_down or self.current_state != required_state:
            return
            
        self.current_state = new_state
        self.workflowStateChanged.emit(self.current_state)
        self.update_status(message, "#4caf50")
        logger.info(f"Workflow step completed: {message}")
    
    def complete_configuration(self):
        """Complete configuration workflow step"""
        if (self.is_shutting_down or self.current_state != WorkflowStates.CONNECTED or
            not self.config_widget):
            return
            
        try:
            if (self.config_widget.sample_rate_send_done and 
                self.config_widget.channel_config_send_done):
                self.config_widget.sample_rate_send_done = False
                self.config_widget.channel_config_send_done = False
                
                self._complete_workflow_step(
                    WorkflowStates.CONNECTED, 
                    WorkflowStates.CONFIGURED,
                    "Configuration completed"
                )
                self.configurationChanged.emit()
            
        except Exception as e:
            logger.error(f"Error completing configuration: {e}")
            self.update_status(f"Configuration failed: {str(e)}", "#f44336")
    
    def complete_test(self):
        """Complete test workflow step"""
        self._complete_workflow_step(
            WorkflowStates.CONFIGURED, 
            WorkflowStates.TESTED,
            "Test completed"
        )
    
    def complete_acquisition(self):
        """Complete acquisition workflow step"""
        self._complete_workflow_step(
            WorkflowStates.TESTED,
            WorkflowStates.ACQUIRED,
            "Data acquisition completed"
        )
    
    def complete_analysis(self):
        """Complete analysis workflow step"""
        self._complete_workflow_step(
            WorkflowStates.ACQUIRED,
            WorkflowStates.ANALYZED,
            "Data analysis completed"
        )
    
    def update_ui_state(self):
        """Update UI state based on current workflow and connection status"""
        if self.is_shutting_down:
            return
            
        try:
            # Check connection and patient info
            connected = self.current_state >= WorkflowStates.CONNECTED
            has_patient = (hasattr(self, 'user_widget') and 
                          hasattr(self.user_widget, 'current_patient') and
                          getattr(self.user_widget.current_patient, 'initials', '') != '')
            print(getattr(self.user_widget.current_patient, 'initials', ''))
            
            # Tab enabling logic
            tab_states = [
                True,  # Home tab is always enabled
                connected and has_patient,  # Configuration requires connection and patient info
                self.current_state >= WorkflowStates.CONFIGURED,  # Test requires configuration
                self.current_state >= WorkflowStates.TESTED,     # Acquisition requires test
                self.current_state >= WorkflowStates.ACQUIRED    # Analysis requires acquisition
            ]
            
            for index, enabled in enumerate(tab_states):
                self.ui.tabWidget.setTabEnabled(index, enabled)
            
        except Exception as e:
            logger.error(f"Error updating UI state: {e}")
    
    def on_patient_changed(self):
        """Handle patient information changes"""
        self.update_ui_state()
        logger.debug("Patient information changed, UI state updated")
    
    def _handle_tab_save_operation(self, tab_index):
        """Handle save operations based on current tab"""
        operations = {
            0: self._save_patient_data,
            1: self._save_configuration_data
        }
        
        operation = operations.get(tab_index, self._save_generic_data)
        operation()
    
    def _save_patient_data(self):
        """Save patient data from home tab"""
        if hasattr(self, 'user_widget') and hasattr(self.user_widget, 'save_patient_data'):
            self.user_widget.save_patient_data()
            QMessageBox.information(self, "Save", "Patient data saved successfully!")
        else:
            QMessageBox.information(self, "Save", "No patient data to save")
    
    def _save_configuration_data(self):
        """Save configuration data from config tab"""
        if self.config_widget:
            try:
                self.config_widget.save_configuration()
            except Exception as e:
                logger.error(f"Configuration save failed: {e}")
                QMessageBox.critical(self, "Save Error", f"Failed to save configuration: {str(e)}")
        else:
            QMessageBox.information(self, "Save", "No configuration to save")
    
    def _save_generic_data(self):
        """Generic save operation for other tabs"""
        QMessageBox.information(self, "Save", "Data saved successfully!")
    
    def save_data(self):
        """Save current data based on active tab"""
        if self.is_shutting_down:
            return
            
        try:
            current_index = self.ui.tabWidget.currentIndex()
            self._handle_tab_save_operation(current_index)
            logger.info(f"Data saved for tab index: {current_index}")
                
        except Exception as e:
            logger.error(f"Save failed: {e}")
            self.show_error_message(f"Save failed: {e}")
    
    def export_data(self):
        """Export data functionality"""
        if self.is_shutting_down:
            return
            
        try:
            current_index = self.ui.tabWidget.currentIndex()
            
            if current_index == 1 and self.config_widget:
                self._export_configuration()
            elif self.current_state >= WorkflowStates.ACQUIRED:
                QMessageBox.information(self, "Export", "Data export functionality will be implemented here")
            else:
                QMessageBox.information(self, "Export", "No data available for export. Complete data acquisition first.")
                
        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.show_error_message(f"Export failed: {e}")
    
    def _export_configuration(self):
        """Export configuration data"""
        config_dict = self.config_widget.get_configuration_dict() # type: ignore
        summary = self.config_widget.get_sensor_summary() # type: ignore
        
        QMessageBox.information(self, "Export", 
            f"Configuration Export Summary:\n\n{summary}\n\n"
            f"Use 'Save Configuration' to save to file.")
    
    def show_preferences(self):
        """Show preferences dialog"""
        if not self.is_shutting_down:
            QMessageBox.information(self, "Preferences", "Preferences dialog will be implemented here")
    
    def show_about(self):
        """Show about dialog with enhanced information"""
        if self.is_shutting_down:
            return
            
        # Get configuration info if available
        config_info = ""
        if self.config_widget:
            try:
                enabled_sensors = self.config_widget.get_enabled_sensor_types()
                config_info = f"\n• Active sensors: {', '.join([s.upper() for s in enabled_sensors])}"
            except:
                config_info = "\n• Configuration manager: Available"
        
        about_text = (
            "fNIRS Data Acquisition System\n\n"
            "Version: 2.0 (Optimized XML-Based UI with Configuration Manager)\n"
            "A comprehensive system for fNIRS data collection and analysis.\n\n"
            "Features:\n"
            "• Optimized code structure with reduced redundancy\n"
            "• UI structure matching XML definition\n"
            "• Tabbed interface with workflow management\n"
            "• Integrated configuration management system\n"
            "• Real-time device status indicators\n"
            "• Multilingual support (Chinese/English)\n"
            "• Enhanced error handling and logging\n"
            "• Signal-based component communication\n"
            "• Persistent window state\n"
            "• Patient information management\n"
            "• Automatic device discovery\n"
            "• Real-time battery monitoring\n"
            "• Command acknowledgment system\n"
            "• Robust network communication\n"
            f"• Advanced sensor configuration{config_info}"
        )
        QMessageBox.about(self, "About fNIRS System", about_text)
    
    # Utility methods for external access
    def get_user_widget(self):
        """Get reference to the user widget for external access"""
        return getattr(self, 'user_widget', None)
    
    def get_config_manager(self):
        """Get reference to the configuration manager for external access"""
        return getattr(self, 'config_widget', None)
    
    def get_network_statistics(self):
        """Get current network statistics"""
        if self.network and not self.is_shutting_down:
            return self.network.get_statistics()
        return {}
    
    def resizeEvent(self, event): # type: ignore
        """Handle window resize events"""
        super().resizeEvent(event)
        # The tab widget and status area positions are fixed as per XML definition
    
    def _save_window_configuration(self):
        """Save window and configuration state"""
        try:
            # Save window geometry and state
            self.settings.setValue("window/geometry", self.saveGeometry())
            self.settings.setValue("window/state", self.saveState())
            self.settings.setValue("tab/current_index", self.ui.tabWidget.currentIndex())
            
            # Save configuration manager state if available
            if self.config_widget:
                try:
                    config_summary = self.config_widget.get_sensor_summary()
                    self.settings.setValue("config/last_sensors", config_summary.get('enabled_sensors', []))
                except Exception as e:
                    logger.warning(f"Failed to save configuration state: {e}")
            
            self.settings.sync()
            logger.debug("Window state saved")
        except Exception as e:
            logger.error(f"Error saving window state: {e}")
    
    def save_window_state(self):
        """Save current window state to settings"""
        self._save_window_configuration()
    
    def restore_window_state(self):
        """Restore window and tab state from settings"""
        try:
            # Restore window geometry
            geometry = self.settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)
            else:
                self.resize(1200, 852)
                self.center_window()
            
            # Restore window state
            window_state = self.settings.value("window/state")
            if window_state:
                self.restoreState(window_state)
            
            # Restore tab index (default to 4 as per XML - Analysis tab)
            tab_index = self.settings.value("tab/current_index", 4, type=int)
            if 0 <= tab_index < self.ui.tabWidget.count():
                self.ui.tabWidget.setCurrentIndex(tab_index)
            
            # Log restored configuration info
            last_sensors = self.settings.value("config/last_sensors", [], type=list)
            if last_sensors:
                logger.info(f"Last session sensors: {last_sensors}")
            
            logger.debug("Window state restored")
            
        except Exception as e:
            logger.error(f"Error restoring window state: {e}")
            self.resize(1200, 852)
            self.center_window()
    
    def center_window(self):
        """Center the window on the screen"""
        try:
            screen = QApplication.desktop().availableGeometry() # type: ignore
            window_rect = self.frameGeometry()
            center_point = screen.center()
            window_rect.moveCenter(center_point)
            self.move(window_rect.topLeft())
        except Exception as e:
            logger.error(f"Error centering window: {e}")
    
    def _cleanup_components(self):
        """Cleanup individual components during shutdown"""
        cleanup_operations = [
            ("configuration manager", self._cleanup_config_manager),
            ("user widget", self._cleanup_user_widget),
            ("network", self._cleanup_network)
        ]
        
        for component_name, cleanup_func in cleanup_operations:
            try:
                cleanup_func()
                logger.info(f"{component_name.title()} closed successfully")
            except Exception as e:
                logger.warning(f"Error during {component_name} cleanup: {e}")
    
    def _cleanup_config_manager(self):
        """Cleanup configuration manager"""
        if self.config_widget:
            if hasattr(self.config_widget, 'get_sensor_summary'):
                summary = self.config_widget.get_sensor_summary()
                logger.info(f"Final configuration state: {summary}")
            self.config_widget.close()
    
    def _cleanup_user_widget(self):
        """Cleanup user widget"""
        if hasattr(self, 'user_widget') and hasattr(self.user_widget, 'closeEvent'):
            from PyQt5.QtGui import QCloseEvent
            close_event = QCloseEvent()
            self.user_widget.closeEvent(close_event)
    
    def _cleanup_network(self):
        """Cleanup network connections"""
        if self.network:
            if self.current_state >= WorkflowStates.CONNECTED:
                connected_devices = self.network.get_connected_devices()
                if len(connected_devices) > 0:
                    self.network.sendDisconnect()
                    QApplication.processEvents()
                    import time
                    time.sleep(0.5)
            self.network.close()
    
    def shutdown_cleanup(self):
        """Perform comprehensive cleanup during shutdown"""
        logger.info("Starting shutdown cleanup...")
        
        # Set shutdown flag and save state
        self.is_shutting_down = True
        self.save_window_state()
        
        # Stop all timers and cleanup components
        self.stop_all_timers()
        self._cleanup_components()
        
        logger.info("Shutdown cleanup completed")
    
    def closeEvent(self, event): # type: ignore
        """Handle application close event"""
        try:
            self.shutdown_cleanup()
            event.accept()
            logger.info("Application closed successfully")
            
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
            event.accept()  # Force close even if there's an error


def main():
    """Main application entry point"""
    try:
        app = QApplication(sys.argv)
        
        # Set application properties
        app.setApplicationName("fNIRS Data Acquisition System")
        app.setApplicationVersion("2.0")
        app.setOrganizationName("fNIRS Solutions")
        
        # Enable high DPI scaling
        app.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        app.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
        # Create and show main window
        window = MainWindow()
        window.show()
        
        logger.info("Application started successfully with optimized XML-based UI structure and integrated configuration manager")
        
        # Start event loop
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
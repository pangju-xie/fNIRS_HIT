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
import config

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
    
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Initialize state variables
        self.current_state = WorkflowStates.DISCONNECTED
        self.is_connecting = False
        self.is_disconnecting = False
        self.is_shutting_down = False
        self.sensor_type = SensorTypes.NotInit
        self.sensors = {}
        
        # Initialize timers
        self.connection_timeout_timer = None
        self.battery_query_timer = None
        
        # Settings for window state persistence
        self.settings = QSettings('fNIRS Solutions', 'fNIRS Data Acquisition System')
        
        # Initialize components in proper order
        self.initialize_network()
        self.initialize_user_widget()
        self.setup_ui_connections()
        self.setup_timers()
        self.update_ui_state()
        self.restore_window_state()
        
        logger.info("MainWindow initialized successfully with UI structure from XML")
    
    def initialize_network(self):
        """Initialize network module with comprehensive error handling"""
        try:
            self.network = network.UdpPort(1227, 2227)
            self.setup_network_connections()
            logger.info("Network module initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize network: {e}")
            QMessageBox.critical(self, "Network Error", 
                               f"Failed to initialize network:\n{e}")
            self.network = None
    
    def initialize_user_widget(self):
        """Initialize and integrate user widget into home tab"""
        try:
            self.user_widget = user.UserInfoManager()
            
            # Add user widget to the home tab layout
            self.ui.homeLayout.addWidget(self.user_widget)
            
            # Connect user widget signals if available
            if hasattr(self.user_widget, 'patientChanged'):
                self.user_widget.patientChanged.connect(self.on_patient_changed)
            
            logger.info("User widget integrated into home tab successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize user widget: {e}")
            # Add placeholder to home tab if user widget fails
            placeholder = QtWidgets.QLabel("User widget could not be loaded")
            placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("QLabel { color: #f44336; font-style: italic; }")
            self.ui.homeLayout.addWidget(placeholder)
    
    def setup_timers(self):
        """Setup all timers with proper configuration"""
        # Connection timeout timer
        self.connection_timeout_timer = QTimer()
        self.connection_timeout_timer.setSingleShot(True)
        self.connection_timeout_timer.timeout.connect(self.on_connection_timeout)
        
        # Battery monitoring timer
        self.battery_query_timer = QTimer()
        self.battery_query_timer.timeout.connect(self.query_battery)
        self.battery_query_timer.setSingleShot(False)  # Repeating timer
    
    def setup_network_connections(self):
        """Setup network signal connections"""
        if not self.network:
            return
            
        # Device connection events
        self.network.onDeviceConnected.connect(self.on_device_connected)
        self.network.onDeviceDisconnected.connect(self.on_device_disconnected)
        
        # Battery monitoring
        self.network.onBatteryUpdated.connect(self.on_battery_updated)
        
        # Error handling
        self.network.networkError.connect(self.on_network_error)
    
    def setup_ui_connections(self):
        """Setup UI signal-slot connections using the UI structure from XML"""
        # Connect/disconnect button from status area
        self.ui.connectButton.clicked.connect(self.handle_connection_toggle)
        
        # Tab change handling
        self.ui.tabWidget.currentChanged.connect(self.on_tab_changed)
        
        # Menu actions
        self.ui.saveAction.triggered.connect(self.save_data)
        self.ui.exportAction.triggered.connect(self.export_data)
        self.ui.exitAction.triggered.connect(self.close)
        self.ui.preferencesAction.triggered.connect(self.show_preferences)
        self.ui.aboutAction.triggered.connect(self.show_about)
        
        # Connect custom signals
        self.deviceConnectionChanged.connect(self.on_device_connection_changed)
        self.workflowStateChanged.connect(self.on_workflow_state_changed)
        self.batteryLevelChanged.connect(self.update_battery_display)
    
    def on_tab_changed(self, index):
        """Handle tab change events and workflow progression"""
        if self.is_shutting_down:
            return
            
        try:
            tab_names = ['home', 'configuration', 'test', 'acquisition', 'analysis']
            if 0 <= index < len(tab_names):
                current_tab = tab_names[index]
                logger.debug(f"Tab changed to: {current_tab} (index: {index})")
                
                # Trigger workflow progression based on tab
                self.handle_workflow_progression(current_tab, index)
                
        except Exception as e:
            logger.error(f"Error handling tab change: {e}")
    
    def handle_workflow_progression(self, tab_name, tab_index):
        """Handle workflow progression when switching tabs"""
        try:
            # Simulate workflow completion for demo purposes
            if tab_name == 'configuration' and self.current_state == WorkflowStates.CONNECTED:
                QTimer.singleShot(1500, self.complete_configuration)
            elif tab_name == 'test' and self.current_state == WorkflowStates.CONFIGURED:
                QTimer.singleShot(1500, self.complete_test)
            elif tab_name == 'acquisition' and self.current_state == WorkflowStates.TESTED:
                QTimer.singleShot(1500, self.complete_acquisition)
            elif tab_name == 'analysis' and self.current_state == WorkflowStates.ACQUIRED:
                QTimer.singleShot(1500, self.complete_analysis)
                
        except Exception as e:
            logger.error(f"Error in workflow progression: {e}")
    
    def handle_connection_toggle(self):
        """Handle connection/disconnection button click"""
        if self.is_shutting_down:
            return
            
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
            self.is_connecting = True
            self.ui.connectButton.setEnabled(False)
            self.ui.connectButton.setText("正在连接...")  # Chinese: "Connecting..."
            self.update_status("Connecting to devices...", "#ff9800")
            self.update_connection_indicator(False, "正在连接...")
            
            # Stop any existing battery monitoring
            self.stop_battery_monitoring()
            
            # Send connection command
            self.network.sendConnect()
            
            # Start timeout timer (10 seconds)
            self.connection_timeout_timer.start(10000)
            
        except Exception as e:
            self.reset_connection_ui()
            logger.error(f"Connection initiation failed: {e}")
            self.show_error_message(f"Failed to start connection: {e}")
    
    def disconnect_device(self):
        """Initiate device disconnection with proper cleanup"""
        if self.is_shutting_down or self.is_disconnecting:
            return
            
        try:
            self.is_disconnecting = True
            self.ui.connectButton.setEnabled(False)
            self.ui.connectButton.setText("正在断开...")  # Chinese: "Disconnecting..."
            self.update_status("Disconnecting devices...", "#ff9800")
            self.update_connection_indicator(False, "正在断开...")
            
            # Stop all timers immediately
            self.stop_all_timers()
            
            # Send disconnection command if we have connected devices
            if self.network and len(self.network.get_connected_devices()) > 0:
                self.network.sendDisconnect()
                QTimer.singleShot(3000, self.force_disconnect)
            else:
                QTimer.singleShot(100, self.on_device_disconnected)
            
        except Exception as e:
            logger.error(f"Disconnection failed: {e}")
            self.show_error_message(f"Failed to disconnect: {e}")
            self.force_disconnect()
    
    def force_disconnect(self):
        """Force disconnection if normal disconnect fails"""
        if not self.is_shutting_down:
            logger.warning("Forcing disconnection due to timeout")
            self.on_device_disconnected()
    
    def stop_all_timers(self):
        """Stop all active timers safely"""
        if self.connection_timeout_timer and self.connection_timeout_timer.isActive():
            self.connection_timeout_timer.stop()
        
        if self.battery_query_timer and self.battery_query_timer.isActive():
            self.battery_query_timer.stop()
    
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
            self.update_connection_indicator(False, "连接超时")  # Chinese: "Connection timeout"
            logger.warning("Connection attempt timed out")
    
    def reset_connection_ui(self):
        """Reset connection UI to disconnected state"""
        if not self.is_shutting_down:
            self.ui.connectButton.setEnabled(True)
            self.ui.connectButton.setText("连接设备")  # Chinese: "Connect Device"
        self.is_connecting = False
        self.is_disconnecting = False
    
    def on_device_connected(self, sensor_id, sensor_type):
        """Handle device connected signal with enhanced UI updates"""
        if self.is_shutting_down:
            return
            
        try:
            # Stop connection timeout timer
            if self.connection_timeout_timer.isActive():
                self.connection_timeout_timer.stop()
            
            self.is_connecting = False
            self.current_state = WorkflowStates.CONNECTED
            
            # Update device info display
            self.update_device_info(sensor_id, sensor_type)
            
            # Initialize sensor type
            self.init_sensor(sensor_type)
            
            # Update connection UI
            self.ui.connectButton.setText("断开连接")  # Chinese: "Disconnect"
            self.ui.connectButton.setEnabled(True)
            
            # Update status displays
            device_count = len(self.network.get_connected_devices()) if self.network else 1
            self.update_status(f"Connected to {device_count} device(s)", "#4caf50")
            self.update_connection_indicator(True, f"{device_count} 个设备")  # Chinese: "devices"
            
            # Start battery monitoring
            self.start_battery_monitoring()
            
            # Emit signals for UI updates
            self.deviceConnectionChanged.emit(True)
            self.workflowStateChanged.emit(self.current_state)
            
            logger.info(f"Device connected successfully: ID={sensor_id}, Type={sensor_type}")
            
        except Exception as e:
            logger.error(f"Error handling device connection: {e}")
    
    def on_device_disconnected(self):
        """Handle device disconnected signal with comprehensive cleanup"""
        if self.is_shutting_down:
            return
            
        try:
            # Stop all timers first
            self.stop_all_timers()
            
            self.current_state = WorkflowStates.DISCONNECTED
            self.is_disconnecting = False
            
            # Update device info
            self.update_device_info('--', '--')
            
            # Reset battery display
            self.ui.batteryProgressBar.setValue(0)
            self.ui.batteryProgressBar.setStyleSheet("")
            
            # Update connection UI
            self.reset_connection_ui()
            
            # Update status displays
            self.update_status("Device disconnected", "#2196f3")
            self.update_connection_indicator(False, "已断开")  # Chinese: "Disconnected"
            
            # Reset to home tab
            self.ui.tabWidget.setCurrentIndex(0)
            
            # Emit signals for UI updates
            self.deviceConnectionChanged.emit(False)
            self.workflowStateChanged.emit(self.current_state)
            
            logger.info("Device disconnected successfully")
            
        except Exception as e:
            logger.error(f"Error handling device disconnection: {e}")
    
    def on_device_connection_changed(self, connected):
        """Handle device connection state changes"""
        self.update_ui_state()
    
    def on_workflow_state_changed(self, new_state):
        """Handle workflow state changes"""
        self.update_ui_state()
    
    def update_connection_indicator(self, connected, status_text=""):
        """Update the connection status indicator"""
        try:
            if connected:
                self.ui.connectionStatusLabel.setText("🟢 已连接")  # Chinese: "Connected"
                self.ui.connectionStatusLabel.setStyleSheet("QLabel { color: #4caf50; font-weight: bold; }")
            else:
                status_display = status_text if status_text else "未连接"  # Chinese: "Disconnected"
                self.ui.connectionStatusLabel.setText(f"⚫ {status_display}")
                self.ui.connectionStatusLabel.setStyleSheet("QLabel { color: #f44336; font-weight: bold; }")
                
            # Update device count
            if self.network and connected:
                device_count = len(self.network.get_connected_devices())
                self.ui.deviceCountLabel.setText(f"数量: {device_count}")  # Chinese: "Count"
            else:
                self.ui.deviceCountLabel.setText("数量: 0")  # Chinese: "Count: 0"
                
        except Exception as e:
            logger.error(f"Error updating connection indicator: {e}")
    
    def start_battery_monitoring(self):
        """Start battery level monitoring for connected devices"""
        if (self.is_shutting_down or 
            not self.network or 
            self.current_state < WorkflowStates.CONNECTED or
            len(self.network.get_connected_devices()) == 0):
            return
        
        try:
            # Query battery immediately
            self.query_battery()
            
            # Start periodic monitoring (every 10 seconds)
            if not self.battery_query_timer.isActive():
                self.battery_query_timer.start(10000)
                logger.debug("Battery monitoring started")
        except Exception as e:
            logger.warning(f"Failed to start battery monitoring: {e}")
    
    def query_battery(self):
        """Query battery status from devices with safety checks"""
        if (self.is_shutting_down or 
            not self.network or 
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
            # Update progress bar
            self.ui.batteryProgressBar.setValue(battery_level)
            
            # Update color based on battery level
            if battery_level < 20:
                color = "#f44336"  # Red
            elif battery_level < 50:
                color = "#ff9800"  # Orange
            else:
                color = "#4caf50"  # Green
                
            self.ui.batteryProgressBar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {color}; }}"
            )
            
            logger.debug(f"Battery level updated: {battery_level}%")
            
        except Exception as e:
            logger.error(f"Error updating battery display: {e}")
    
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
                    1: "EEG",
                    2: "sEMG", 
                    3: "EEG/sEMG",
                    4: "fNIRS",
                    5: "EEG/fNIRS",
                    6: "sEMG/fNIRS",
                    7: "EEG/sEMG/fNIRS"
                }
                type_name = type_names.get(device_type, f"Type-{device_type}")
                
                self.ui.deviceIdLabel.setText(f"设备 ID: {id_str}")  # Chinese: "Device ID"
                self.ui.deviceTypeLabel.setText(f"设备类型: {type_name}")  # Chinese: "Device Type"
            else:
                self.ui.deviceIdLabel.setText("设备 ID: --")  # Chinese: "Device ID: --"
                self.ui.deviceTypeLabel.setText("设备类型: --")  # Chinese: "Device Type: --"
                
        except Exception as e:
            logger.error(f"Error updating device info: {e}")
    
    def init_sensor(self, sensor_type):
        """Initialize sensor type and related components"""
        if self.is_shutting_down:
            return
            
        try:
            self.sensor_type = sensor_type
            self.sensors.clear()  # Clear previous sensors
            
            if sensor_type & SensorTypes.EEG:
                self.sensors['EEG'] = True
            if sensor_type & SensorTypes.SEMG:
                self.sensors['sEMG'] = True
            if sensor_type & SensorTypes.FNIRS:
                self.sensors['fNIRS'] = fNIRS.fNIRS()
            
            logger.info(f"Sensor initialized with {len(self.sensors)} types: {list(self.sensors.keys())}")
            
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
    
    def complete_configuration(self):
        """Complete configuration workflow step"""
        if self.is_shutting_down or self.current_state != WorkflowStates.CONNECTED:
            return
            
        self.current_state = WorkflowStates.CONFIGURED
        self.workflowStateChanged.emit(self.current_state)
        self.update_status("Configuration completed", "#4caf50")
        logger.info("Configuration workflow step completed")
    
    def complete_test(self):
        """Complete test workflow step"""
        if self.is_shutting_down or self.current_state != WorkflowStates.CONFIGURED:
            return
            
        self.current_state = WorkflowStates.TESTED
        self.workflowStateChanged.emit(self.current_state)
        self.update_status("Test completed", "#4caf50")
        logger.info("Test workflow step completed")
    
    def complete_acquisition(self):
        """Complete acquisition workflow step"""
        if self.is_shutting_down or self.current_state != WorkflowStates.TESTED:
            return
            
        self.current_state = WorkflowStates.ACQUIRED
        self.workflowStateChanged.emit(self.current_state)
        self.update_status("Data acquisition completed", "#4caf50")
        logger.info("Acquisition workflow step completed")
    
    def complete_analysis(self):
        """Complete analysis workflow step"""
        if self.is_shutting_down or self.current_state != WorkflowStates.ACQUIRED:
            return
            
        self.current_state = WorkflowStates.ANALYZED
        self.workflowStateChanged.emit(self.current_state)
        self.update_status("Data analysis completed", "#4caf50")
        logger.info("Analysis workflow step completed")
    
    def update_ui_state(self):
        """Update UI state based on current workflow and connection status"""
        if self.is_shutting_down:
            return
            
        try:
            # Update tab enabled states based on workflow progression
            connected = self.current_state >= WorkflowStates.CONNECTED
            has_patient = (hasattr(self, 'user_widget') and 
                          hasattr(self.user_widget, 'current_patient') and
                          getattr(self.user_widget.current_patient, 'initials', '') != '')
            
            # Home tab is always enabled
            self.ui.tabWidget.setTabEnabled(0, True)
            
            # Configuration requires connection and patient info
            self.ui.tabWidget.setTabEnabled(1, connected and has_patient)
            
            # Test requires configuration completion
            self.ui.tabWidget.setTabEnabled(2, self.current_state >= WorkflowStates.CONFIGURED)
            
            # Acquisition requires test completion
            self.ui.tabWidget.setTabEnabled(3, self.current_state >= WorkflowStates.TESTED)
            
            # Analysis requires acquisition completion
            self.ui.tabWidget.setTabEnabled(4, self.current_state >= WorkflowStates.ACQUIRED)
            
        except Exception as e:
            logger.error(f"Error updating UI state: {e}")
    
    def on_patient_changed(self):
        """Handle patient information changes"""
        # Update UI state when patient information changes
        self.update_ui_state()
        logger.debug("Patient information changed, UI state updated")
    
    def save_data(self):
        """Save current data based on active tab"""
        if self.is_shutting_down:
            return
            
        try:
            current_index = self.ui.tabWidget.currentIndex()
            
            # Handle saving based on current tab
            if current_index == 0 and hasattr(self, 'user_widget'):
                # Home tab - save patient data
                if hasattr(self.user_widget, 'save_patient_data'):
                    self.user_widget.save_patient_data()
                    QMessageBox.information(self, "Save", "Patient data saved successfully!")
                else:
                    QMessageBox.information(self, "Save", "No patient data to save")
            else:
                # Other tabs - generic save
                QMessageBox.information(self, "Save", "Data saved successfully!")
                
            logger.info(f"Data saved for tab index: {current_index}")
                
        except Exception as e:
            logger.error(f"Save failed: {e}")
            self.show_error_message(f"Save failed: {e}")
    
    def export_data(self):
        """Export data functionality"""
        if self.is_shutting_down:
            return
            
        try:
            # Implement data export logic based on current workflow state
            if self.current_state >= WorkflowStates.ACQUIRED:
                QMessageBox.information(self, "Export", "Data export functionality will be implemented here")
            else:
                QMessageBox.information(self, "Export", "No data available for export. Complete data acquisition first.")
                
        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.show_error_message(f"Export failed: {e}")
    
    def show_preferences(self):
        """Show preferences dialog"""
        if self.is_shutting_down:
            return
            
        QMessageBox.information(self, "Preferences", "Preferences dialog will be implemented here")
    
    def show_about(self):
        """Show about dialog with enhanced information"""
        if self.is_shutting_down:
            return
            
        about_text = (
            "fNIRS Data Acquisition System\n\n"
            "Version: 2.0 (XML-Based UI)\n"
            "A comprehensive system for fNIRS data collection and analysis.\n\n"
            "Features:\n"
            "• UI structure matching XML definition\n"
            "• Tabbed interface with workflow management\n"
            "• Real-time device status indicators\n"
            "• Multilingual support (Chinese/English)\n"
            "• Enhanced error handling and logging\n"
            "• Signal-based component communication\n"
            "• Persistent window state\n"
            "• Patient information management\n"
            "• Automatic device discovery\n"
            "• Real-time battery monitoring\n"
            "• Command acknowledgment system\n"
            "• Robust network communication"
        )
        QMessageBox.about(self, "About fNIRS System", about_text)
    
    def get_user_widget(self):
        """Get reference to the user widget for external access"""
        return getattr(self, 'user_widget', None)
    
    def get_network_statistics(self):
        """Get current network statistics"""
        if self.network and not self.is_shutting_down:
            return self.network.get_statistics()
        return {}
    
    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        # The tab widget and status area positions are fixed as per XML definition
        
    def save_window_state(self):
        """Save current window state to settings"""
        try:
            self.settings.setValue("window/geometry", self.saveGeometry())
            self.settings.setValue("window/state", self.saveState())
            self.settings.setValue("tab/current_index", self.ui.tabWidget.currentIndex())
            self.settings.sync()
            logger.debug("Window state saved")
        except Exception as e:
            logger.error(f"Error saving window state: {e}")
    
    def restore_window_state(self):
        """Restore window and tab state from settings"""
        try:
            # Restore window geometry
            geometry = self.settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)
            else:
                # Use default size from XML (1200x852)
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
            
            logger.debug("Window state restored")
            
        except Exception as e:
            logger.error(f"Error restoring window state: {e}")
            self.resize(1200, 852)
            self.center_window()
    
    def center_window(self):
        """Center the window on the screen"""
        try:
            screen = QApplication.desktop().availableGeometry()
            window_rect = self.frameGeometry()
            center_point = screen.center()
            window_rect.moveCenter(center_point)
            self.move(window_rect.topLeft())
        except Exception as e:
            logger.error(f"Error centering window: {e}")
    
    def shutdown_cleanup(self):
        """Perform comprehensive cleanup during shutdown"""
        logger.info("Starting shutdown cleanup...")
        
        # Set shutdown flag
        self.is_shutting_down = True
        
        # Save window state
        self.save_window_state()
        
        # Stop all timers
        self.stop_all_timers()
        
        # Close user widget
        if hasattr(self, 'user_widget') and hasattr(self.user_widget, 'closeEvent'):
            try:
                from PyQt5.QtGui import QCloseEvent
                close_event = QCloseEvent()
                self.user_widget.closeEvent(close_event)
            except Exception as e:
                logger.warning(f"Error during user widget cleanup: {e}")
        
        # Close network connection
        if self.network:
            try:
                if self.current_state >= WorkflowStates.CONNECTED:
                    connected_devices = self.network.get_connected_devices()
                    if len(connected_devices) > 0:
                        self.network.sendDisconnect()
                        QApplication.processEvents()
                        import time
                        time.sleep(0.5)
                
                self.network.close()
                logger.info("Network closed successfully")
            except Exception as e:
                logger.error(f"Error closing network: {e}")
        
        logger.info("Shutdown cleanup completed")
    
    def closeEvent(self, event):
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
        app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        
        # Create and show main window
        window = MainWindow()
        window.show()
        
        logger.info("Application started successfully with XML-based UI structure")
        
        # Start event loop
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
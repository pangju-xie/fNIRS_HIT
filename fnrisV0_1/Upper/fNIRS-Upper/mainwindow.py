# -*- coding: utf-8 -*-
"""
fNIRS Signal Acquisition System - Streamlined Main Application
Restructured with configure/display sub-windows and reserved interfaces
"""

import sys
import logging
from typing import Optional, Dict
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QDateTime
from PyQt5.QtGui import QCloseEvent

import network
import ui

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


class fNIRSMainWindow(QMainWindow):
    """Main application window with configure/display sub-windows"""
    
    def __init__(self):
        super().__init__()
        self.ui = ui.Ui_MainWindow()
        self.ui.setupUi(self)
        self.resize(1600, 1000)
        
        # Device tracking
        self.connected_devices: Dict[tuple, Dict] = {}
        self.device_battery_levels: Dict[tuple, int] = {}
        
        # Initialize components
        self.network: Optional[network.UdpPort] = None
        self.battery_timer: Optional[QTimer] = None
        
        # Connection state
        self.is_connected = False
        self.is_sampling = False
        self.is_configured = False
        
        # Sub-window implementations (to be set externally)
        self.configure_implementation = None
        self.display_implementation = None
        
        self._setup_components()
        self._connect_signals()
        
        logger.info("fNIRS Main Window initialized")
    
    def _setup_components(self):
        """Initialize application components"""
        try:
            # Initialize network
            self.network = network.UdpPort(1227, 2227)
            logger.info("Network component initialized")
            
            # Setup battery polling timer
            self.battery_timer = QTimer()
            self.battery_timer.setInterval(5000)  # 5 seconds
            self.battery_timer.timeout.connect(self._send_battery_query)
            
        except Exception as e:
            logger.error(f"Component setup failed: {e}")
            self._show_error_message(f"Failed to initialize components: {e}")
    
    def _connect_signals(self):
        """Connect button signals and network events to their respective handlers"""
        try:
            # Connect UI buttons
            self.ui.Button_Connection.clicked.connect(self._handle_connection_toggle)
            self.ui.Button_Sampling.clicked.connect(self._handle_sampling_toggle)
            
            # Connect sub-window switching
            self.ui.Button_Configure.clicked.connect(self._handle_configure_switch)
            self.ui.Button_Display.clicked.connect(self._handle_display_switch)
            
            # Connect network signals
            if self.network:
                self.network.onConnectedDevicesChanged.connect(self._on_device_event)
                self.network.networkError.connect(self._on_network_error)
                self.network.connectionStatusChanged.connect(self._on_connection_status_changed)
            
            # Connect menu actions
            self.ui.action_exit.triggered.connect(self.close)
            self.ui.action_save.triggered.connect(self._save_data)
            
            logger.info("Signals connected successfully")
            
        except Exception as e:
            logger.error(f"Signal connection failed: {e}")
    
    # === Main Control Handlers ===
    
    def _handle_connection_toggle(self):
        """Handle connection/disconnection button click"""
        try:
            if not self.is_connected:
                self._connect_devices()
            else:
                self._disconnect_devices()
        except Exception as e:
            logger.error(f"Connection toggle failed: {e}")
            self._show_error_message(f"连接操作失败: {e}")
    
    def _handle_sampling_toggle(self):
        """Handle sampling start/stop button click"""
        try:
            if not self.is_configured:
                self._show_error_message("请先完成设备配置")
                return
                
            if not self.is_sampling:
                self._start_sampling()
            else:
                self._stop_sampling()
        except Exception as e:
            logger.error(f"Sampling toggle failed: {e}")
            self._show_error_message(f"采样操作失败: {e}")
    
    def _handle_configure_switch(self):
        """Handle configure button click"""
        try:
            if self.is_sampling:
                self._show_error_message("采样过程中无法切换到配置界面")
                self.ui.Button_Configure.setChecked(False)
                return
                
            self.ui.switch_to_configure()
            logger.info("Switched to configure view")
        except Exception as e:
            logger.error(f"Configure switch failed: {e}")
    
    def _handle_display_switch(self):
        """Handle display button click"""
        try:
            if not self.is_configured:
                self._show_error_message("请先完成设备配置")
                self.ui.Button_Display.setChecked(False)
                return
                
            self.ui.switch_to_display()
            logger.info("Switched to display view")
        except Exception as e:
            logger.error(f"Display switch failed: {e}")
    
    # === Device Management ===
    
    def _connect_devices(self):
        """Initiate device connection process"""
        try:
            logger.info("Initiating device connection...")
            
            # Clear existing device information
            self.connected_devices.clear()
            self.device_battery_levels.clear()
            
            # Send connection broadcast
            if self.network:
                self.network.sendConnect()
                
            # Update UI to connecting state
            self.is_connected = True
            self.ui.set_connection_state(True)
            
            # Start battery monitoring
            self.battery_timer.start()
            
            logger.info("Connection request sent, waiting for device responses...")
            
        except Exception as e:
            logger.error(f"Device connection failed: {e}")
            self.is_connected = False
            self.ui.set_connection_state(False)
            raise
    
    def _disconnect_devices(self):
        """Disconnect from all devices"""
        try:
            logger.info("Disconnecting from devices...")
            
            # Stop sampling if active
            if self.is_sampling:
                self._stop_sampling()
            
            # Send disconnect command
            if self.network:
                self.network.sendDisconnect()
            
            # Stop battery timer
            if self.battery_timer.isActive():
                self.battery_timer.stop()
            
            # Clear device tracking
            self.connected_devices.clear()
            self.device_battery_levels.clear()
            
            # Update connection state
            self.is_connected = False
            self.ui.set_connection_state(False)
            
            logger.info("Successfully disconnected from all devices")
            
        except Exception as e:
            logger.error(f"Disconnection failed: {e}")
            # Force state reset
            self.is_connected = False
            self.ui.set_connection_state(False)
    
    def _start_sampling(self):
        """Start data sampling from connected devices"""
        try:
            if not self.connected_devices:
                self._show_error_message("没有连接的设备可以开始采样")
                return
            
            logger.info("Starting data sampling...")
            
            # Send start sampling command
            if self.network:
                self.network.sendStartSample()
            
            # Update UI state
            self.is_sampling = True
            self.ui.set_sampling_state(True)
            
            # Notify display implementation if available
            if self.display_implementation and hasattr(self.display_implementation, 'on_sampling_started'):
                self.display_implementation.on_sampling_started()
            
            logger.info("Data sampling started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start sampling: {e}")
            self.is_sampling = False
            self.ui.set_sampling_state(False)
            raise
    
    def _stop_sampling(self):
        """Stop data sampling and save data"""
        try:
            logger.info("Stopping data sampling...")
            
            # Send stop sampling command
            if self.network:
                self.network.sendStopSample()
            
            # Save collected data
            self._save_data()
            
            # Update UI state
            self.is_sampling = False
            self.ui.set_sampling_state(False)
            
            # Notify display implementation if available
            if self.display_implementation and hasattr(self.display_implementation, 'on_sampling_stopped'):
                self.display_implementation.on_sampling_stopped()
            
            logger.info("Data sampling stopped and data saved")
            
        except Exception as e:
            logger.error(f"Failed to stop sampling: {e}")
            # Force state reset
            self.is_sampling = False
            self.ui.set_sampling_state(False)
    
    def _send_battery_query(self):
        """Send battery status query to all connected devices"""
        try:
            if self.network and self.connected_devices:
                self.network.sendBatteryQuery()
                logger.debug(f"Battery query sent to {len(self.connected_devices)} devices")
        except Exception as e:
            logger.error(f"Battery query failed: {e}")
    
    # === Network Event Handlers ===
    
    def _on_device_event(self, sensor_id, sensor_type, operation, params=None):
        """Handle device-related events from network layer"""
        try:
            sensor_id_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            
            if operation == 'a':  # Device added
                self._handle_device_added(sensor_id, sensor_type, params)
                
            elif operation == 'r':  # Device removed
                self._handle_device_removed(sensor_id, sensor_type)
                
            elif operation == 'b':  # Battery update
                self._handle_battery_update(sensor_id, params)
                
            elif operation == 'd':  # Data packet
                self._handle_data_packet(sensor_id, sensor_type, params)
                
            else:
                logger.debug(f"Unknown device operation: {operation}")
                
        except Exception as e:
            logger.error(f"Error handling device event {operation}: {e}")
    
    def _handle_device_added(self, sensor_id, sensor_type, params):
        """Handle new device connection"""
        try:
            sensor_id_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            
            # Store device information
            device_info = {
                'id': sensor_id,
                'type': sensor_type,
                'connected_time': QDateTime.currentDateTime(),
                'last_seen': QDateTime.currentDateTime()
            }
            
            self.connected_devices[sensor_id_key] = device_info
            
            # Update UI with device information
            self._update_device_display()
            
            # Notify configure implementation
            if self.configure_implementation and hasattr(self.configure_implementation, 'on_device_connected'):
                self.configure_implementation.on_device_connected(sensor_id, sensor_type)
            
            # Print device information
            device_info_str = self._format_device_info(sensor_id, sensor_type)
            print(f"设备连接: {device_info_str}")
            logger.info(f"Device connected: {device_info_str}")
            
            self.ui.statusbar.showMessage(f"设备已连接: {device_info_str}")
            
            # Request initial battery status
            if self.network:
                self.network.sendBatteryQuery()
                
        except Exception as e:
            logger.error(f"Failed to handle device added: {e}")
    
    def _handle_device_removed(self, sensor_id, sensor_type):
        """Handle device disconnection"""
        try:
            sensor_id_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            
            # Remove from tracking
            if sensor_id_key in self.connected_devices:
                device_info = self.connected_devices.pop(sensor_id_key)
                device_info_str = self._format_device_info(sensor_id, sensor_type)
                
                print(f"设备断开: {device_info_str}")
                logger.info(f"Device disconnected: {device_info_str}")
            
            # Remove battery tracking
            if sensor_id_key in self.device_battery_levels:
                del self.device_battery_levels[sensor_id_key]
            
            # Update UI
            self._update_device_display()
            
            # Notify configure implementation
            if self.configure_implementation and hasattr(self.configure_implementation, 'on_device_disconnected'):
                self.configure_implementation.on_device_disconnected(sensor_id, sensor_type)
                
        except Exception as e:
            logger.error(f"Failed to handle device removed: {e}")
    
    def _handle_battery_update(self, sensor_id, params):
        """Handle battery level update from device"""
        try:
            if not params or len(params) == 0:
                return
                
            sensor_id_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            battery_level = params[0]
            
            # Update battery tracking
            self.device_battery_levels[sensor_id_key] = battery_level
            
            # Update device last seen time
            if sensor_id_key in self.connected_devices:
                self.connected_devices[sensor_id_key]['last_seen'] = QDateTime.currentDateTime()
            
            # Update UI display
            self._update_battery_display()
            
            # Notify implementations
            if self.configure_implementation and hasattr(self.configure_implementation, 'on_battery_update'):
                self.configure_implementation.on_battery_update(sensor_id, battery_level)
            if self.display_implementation and hasattr(self.display_implementation, 'on_battery_update'):
                self.display_implementation.on_battery_update(sensor_id, battery_level)
            
            # Print battery status
            device_info_str = self._format_device_info(sensor_id, None)
            print(f"电池状态更新: {device_info_str} - {battery_level}%")
            logger.info(f"Battery status updated: {device_info_str} - {battery_level}%")
            
        except Exception as e:
            logger.error(f"Failed to handle battery update: {e}")
    
    def _handle_data_packet(self, sensor_id, sensor_type, params):
        """Handle incoming data packet"""
        try:
            sensor_id_key = tuple(sensor_id) if isinstance(sensor_id, list) else sensor_id
            
            # Update device last seen
            if sensor_id_key in self.connected_devices:
                self.connected_devices[sensor_id_key]['last_seen'] = QDateTime.currentDateTime()
            
            # Forward to display implementation if sampling
            if self.is_sampling and self.display_implementation and hasattr(self.display_implementation, 'on_data_received'):
                self.display_implementation.on_data_received(sensor_id, sensor_type, params)
            
        except Exception as e:
            logger.error(f"Failed to handle data packet: {e}")
    
    def _on_network_error(self, error_message):
        """Handle network errors"""
        logger.error(f"Network error: {error_message}")
        self._show_error_message(f"网络错误: {error_message}")
    
    def _on_connection_status_changed(self, connected):
        """Handle connection status changes from network layer"""
        logger.info(f"Network connection status changed: {connected}")
    
    # === Helper Methods ===
    
    def _format_device_info(self, sensor_id, sensor_type=None):
        """Format device information for display"""
        try:
            # Format sensor ID
            if isinstance(sensor_id, list):
                id_str = "-".join([f"{x:02X}" for x in sensor_id])
            else:
                id_str = str(sensor_id)
            
            # Add type information if provided
            if sensor_type is not None:
                type_names = {
                    1: "EEG",
                    2: "sEMG", 
                    3: "EEG/sEMG",
                    4: "fNIRS",
                    5: "EEG/fNIRS",
                    6: "sEMG/fNIRS",
                    7: "EEG/sEMG/fNIRS"
                }
                type_name = type_names.get(sensor_type, f"类型{sensor_type}")
                return f"ID:{id_str} ({type_name})"
            else:
                return f"ID:{id_str}"
                
        except Exception as e:
            logger.error(f"Failed to format device info: {e}")
            return f"ID:{sensor_id}"
    
    def _update_device_display(self):
        """Update UI with current device information"""
        try:
            device_count = len(self.connected_devices)
            self.ui.update_device_count(device_count)
            
            # Update detailed device info for the first/primary device
            if self.connected_devices:
                first_device = next(iter(self.connected_devices.values()))
                self.ui.update_device_info(first_device['id'], first_device['type'])
            else:
                self.ui.update_device_info("--", "")
                
        except Exception as e:
            logger.error(f"Failed to update device display: {e}")
    
    def _update_battery_display(self):
        """Update UI with current battery information"""
        try:
            if self.device_battery_levels:
                # Show battery for the first device, or average if multiple
                if len(self.device_battery_levels) == 1:
                    battery_level = next(iter(self.device_battery_levels.values()))
                else:
                    # Show average battery level for multiple devices
                    battery_level = sum(self.device_battery_levels.values()) // len(self.device_battery_levels)
                
                self.ui.update_battery_status(battery_level)
            else:
                self.ui.update_battery_status(-1)
                
        except Exception as e:
            logger.error(f"Failed to update battery display: {e}")
    
    def _save_data(self):
        """Save collected data"""
        try:
            # Delegate to display implementation if available
            if self.display_implementation and hasattr(self.display_implementation, 'save_data'):
                self.display_implementation.save_data()
                self.ui.statusbar.showMessage("数据已保存")
            else:
                self.ui.statusbar.showMessage("无数据需要保存")
            
            logger.info("Data save operation completed")
            
        except Exception as e:
            logger.error(f"Failed to save data: {e}")
    
    def _show_error_message(self, message):
        """Show error message to user"""
        logger.error(message)
        if hasattr(self.ui, 'statusbar'):
            self.ui.statusbar.showMessage(f"错误: {message}")
    
    # === Public Interface Methods for Sub-window Implementations ===
    
    def set_configure_implementation(self, configure_widget):
        """Set the configure implementation widget"""
        self.configure_implementation = configure_widget
        self.ui.set_configure_implementation(configure_widget)
        
        # Connect configure signals if available
        if hasattr(configure_widget, 'configuration_completed'):
            configure_widget.configuration_completed.connect(self._on_configuration_completed)
        if hasattr(configure_widget, 'send_network_command'):
            configure_widget.send_network_command.connect(self._forward_network_command)
            
        logger.info("Configure implementation set")
    
    def set_display_implementation(self, display_widget):
        """Set the display implementation widget"""
        self.display_implementation = display_widget
        self.ui.set_display_implementation(display_widget)
        
        logger.info("Display implementation set")
    
    def _on_configuration_completed(self, configured):
        """Handle configuration completion from configure implementation"""
        self.is_configured = configured
        self.ui.set_configured_state(configured)
        
        if configured:
            logger.info("Device configuration completed")
        else:
            logger.info("Device configuration reset")
    
    def _forward_network_command(self, command, *args):
        """Forward network commands from sub-window implementations"""
        try:
            if self.network and hasattr(self.network, command):
                method = getattr(self.network, command)
                method(*args)
                logger.debug(f"Forwarded network command: {command}")
            else:
                logger.warning(f"Unknown network command: {command}")
        except Exception as e:
            logger.error(f"Failed to forward network command {command}: {e}")
    
    def get_connected_devices(self):
        """Get list of connected devices for sub-window implementations"""
        return dict(self.connected_devices)
    
    def get_device_status(self):
        """Get current device status information"""
        return {
            'connected_devices': len(self.connected_devices),
            'is_connected': self.is_connected,
            'is_sampling': self.is_sampling,
            'is_configured': self.is_configured,
            'devices': [
                {
                    'id': info['id'],
                    'type': info['type'],
                    'battery': self.device_battery_levels.get(key, -1),
                    'connected_time': info['connected_time'],
                    'last_seen': info['last_seen']
                }
                for key, info in self.connected_devices.items()
            ]
        }
    
    def closeEvent(self, event: QCloseEvent):
        """Handle application close event with proper cleanup"""
        logger.info("Closing application...")
        
        try:
            # Stop battery timer
            if self.battery_timer and self.battery_timer.isActive():
                self.battery_timer.stop()
            
            # Cleanup sub-window implementations
            if self.configure_implementation and hasattr(self.configure_implementation, 'cleanup'):
                self.configure_implementation.cleanup()
            if self.display_implementation and hasattr(self.display_implementation, 'cleanup'):
                self.display_implementation.cleanup()
            
            # Disconnect network
            if self.network:
                logger.info("Disconnecting network...")
                try:
                    if self.is_connected:
                        self.network.sendDisconnect()
                except Exception as e:
                    logger.error(f"Network disconnect error: {e}")
                
                try:
                    self.network.close()
                except Exception as e:
                    logger.error(f"Network close error: {e}")
            
            # Save any remaining data
            self._save_data()
            
            logger.info("Application closed successfully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        finally:
            event.accept()
            QApplication.quit()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    try:
        # Create and show main window
        main_window = fNIRSMainWindow()
        main_window.show()
        
        # Setup cleanup on app quit
        app.aboutToQuit.connect(lambda: logger.info("Application about to quit"))
        
        # Run application
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
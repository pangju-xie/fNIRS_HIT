import sys
from PyQt5.QtWidgets import QWidget, QSizePolicy, QCheckBox
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
import pyqtgraph as pg
import numpy as np

# Import the UI layout
from ui_sensorwidget import Ui_SensorWidget



# Constants
TIME_WINDOW = 500
PLOT_UPDATE_INTERVAL = 50  # milliseconds
PLOT_COLUMNS = 1  # Force single column layout (n rows x 1 column)

class SensorWidget(QWidget):
    """
    Streamlined SensorWidget focused on UI interaction and visualization.
    Data processing and saving functions have been moved to sensor.py.
    """
    
    # Signals for sensor configuration
    onSampleRateSet = pyqtSignal(list, int, int)  # id, type, sampleRate index
    onChannelsSet = pyqtSignal(list, int, int, int, list)  # id, type, lights, detectors, channels
    
    # Enhanced signals for better functionality
    sampleRateChanged = pyqtSignal(int)  # actual rate value
    channelConfigChanged = pyqtSignal(int, int, list)  # lights, detectors, channel_pairs
    networkError = pyqtSignal(str)

    def __init__(self, sensor_id=[0, 0, 0], sensor_type=4, parent=None):
        super().__init__(parent)
        
        # Sensor identification
        self.sensor_id = sensor_id if isinstance(sensor_id, list) else [0, 0, 0]
        self.type = sensor_type
        self.sensor_id_str = self._format_sensor_id(sensor_id)
        self.type_string = self._get_type_string(sensor_type)
        
        # UI setup
        self.ui = Ui_SensorWidget()
        self.ui.setupUi(self)
        
        # Channel management
        self.current_channels = []
        
        # Plotting components
        self.plots = []
        self.hb_curves = []
        self.hbo2_curves = []
        
        # Plot update timer for better performance
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self._update_plots_batch)
        self.plot_timer.setInterval(PLOT_UPDATE_INTERVAL)
        self.pending_data = None
        
        # Widget sizing
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Initialize functionality
        self._connect_signals()
        
    def _format_sensor_id(self, sensor_id):
        """Format sensor ID for display"""
        if isinstance(sensor_id, list) and len(sensor_id) >= 3:
            return f"{sensor_id[0]:02X}-{sensor_id[1]:02X}-{sensor_id[2]:02X}"
        return str(sensor_id)
    
    def _get_type_string(self, type_code):
        """Convert type code to string"""
        type_map = {
            1: "EEG",
            2: "sEMG", 
            3: "EEG/sEMG",
            4: "fNIRS",
            5: "EEG/fNIRS",
            6: "sEMG/fNIRS",
            7: "EEG/sEMG/fNIRS"
        }
        return type_map.get(type_code, "Undefined")
    
    def _connect_signals(self):
        """Connect UI signals to handlers"""
        try:
            # Sample rate signals
            self.ui.Button_SampleRate.clicked.connect(self._on_sample_rate_clicked)
            
            # Channel configuration signals
            self.ui.Button_Channels.clicked.connect(self._on_channels_clicked)
            self.ui.SpinBox_Lights.valueChanged.connect(self._on_hardware_changed)
            self.ui.SpinBox_Detectors.valueChanged.connect(self._on_hardware_changed)
            
            print(f"SensorWidget {self.sensor_id_str}: Signal connections established")
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error connecting signals - {e}")
    
    def _on_hardware_changed(self):
        """Handle hardware configuration changes with debounce"""
        if hasattr(self, '_update_timer'):
            self._update_timer.stop()
        
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._update_channel_matrix)
        self._update_timer.start(100)  # 100ms delay
    
    def _update_channel_matrix(self):
        """Update the channel matrix when hardware configuration changes"""
        try:
            lights = self.ui.SpinBox_Lights.value()
            detectors = self.ui.SpinBox_Detectors.value()
            
            print(f"SensorWidget {self.sensor_id_str}: Updating channel matrix - {lights}x{detectors}")
            
            # Update the UI matrix display (this handles the checkboxes creation)
            self.ui.update_channel_matrix(lights, detectors)
            
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error updating channel matrix - {e}")
            self.networkError.emit(f"Channel matrix update error: {str(e)}")
    
    def _get_channel_checkboxes(self):
        """Get all checkbox widgets from the current channel matrix"""
        checkboxes = {}
        
        try:
            # Find all QCheckBox widgets in the channel grid layout
            for i in range(self.ui.GridLayout_Channels.count()):
                item = self.ui.GridLayout_Channels.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if isinstance(widget, QCheckBox):
                        object_name = widget.objectName()
                        if object_name.startswith("checkbox_S") and "D" in object_name:
                            # Parse S{s}D{d} from object name
                            try:
                                parts = object_name.replace("checkbox_S", "").split("D")
                                if len(parts) == 2:
                                    s = int(parts[0])
                                    d = int(parts[1])
                                    checkboxes[(s, d)] = widget
                            except ValueError:
                                continue
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error getting checkboxes - {e}")
        
        return checkboxes
    
    def _on_sample_rate_clicked(self):
        """Handle sample rate button click"""
        try:
            rate_text = self.ui.ComboBox_SampleRate.currentText().strip()
            if not rate_text:
                self.networkError.emit("Please select a valid sample rate")
                return
            
            rate = int(rate_text)
            print(f"SensorWidget {self.sensor_id_str}: Setting sample rate to {rate}")
            
            # Emit signals
            self.sampleRateChanged.emit(rate)
            
            # Emit original signal format for compatibility
            rate_options = [10, 20, 50, 100]
            try:
                rate_index = rate_options.index(rate)
            except ValueError:
                rate_index = len(rate_options)
            
            self.onSampleRateSet.emit(self.sensor_id, self.type, rate_index)
            
            # Visual feedback
            self._flash_button_success(self.ui.Button_SampleRate)
            
        except ValueError:
            error_msg = f"Invalid sample rate: {self.ui.ComboBox_SampleRate.currentText()}"
            print(f"SensorWidget {self.sensor_id_str}: {error_msg}")
            self.networkError.emit(error_msg)
        except Exception as e:
            error_msg = f"Sample rate setting error: {str(e)}"
            print(f"SensorWidget {self.sensor_id_str}: {error_msg}")
            self.networkError.emit(error_msg)
    
    def _on_channels_clicked(self):
        """Handle channel configuration button click"""
        try:
            lights = self.ui.SpinBox_Lights.value()
            detectors = self.ui.SpinBox_Detectors.value()
            
            # Get selected channels
            selected_channels = []
            channel_checkboxes = self._get_channel_checkboxes()
            
            for (light, detector), checkbox in channel_checkboxes.items():
                try:
                    if checkbox.isChecked():
                        selected_channels.append((light, detector))
                except:
                    continue
            
            if not selected_channels:
                self.networkError.emit("No channels selected")
                return
            
            print(f"SensorWidget {self.sensor_id_str}: Selected channels - {selected_channels}")
            
            # Store current channels
            self.current_channels = selected_channels
            
            # Emit signals
            self.channelConfigChanged.emit(lights, detectors, selected_channels)
            
            # Emit original signal format for compatibility
            channel_list = [[light, detector] for light, detector in selected_channels]
            self.onChannelsSet.emit(self.sensor_id, self.type, lights, detectors, channel_list)
            
            # Update plot widgets
            self.initializePlots(channel_list)
            
            # Visual feedback
            self._flash_button_success(self.ui.Button_Channels)
            
        except Exception as e:
            error_msg = f"Channel configuration error: {str(e)}"
            print(f"SensorWidget {self.sensor_id_str}: {error_msg}")
            self.networkError.emit(error_msg)
    
    def _flash_button_success(self, button):
        """Flash button green briefly to indicate success"""
        try:
            original_style = button.styleSheet()
            success_style = original_style.replace(
                "background-color: #2196F3", "background-color: #4CAF50"
            ).replace(
                "background-color: #FF9800", "background-color: #4CAF50"
            )
            
            button.setStyleSheet(success_style)
            QTimer.singleShot(1500, lambda: button.setStyleSheet(original_style))
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Button flash error - {e}")
    
    def initializePlots(self, channels):
        """Initialize plot widgets for visualization"""
        try:
            print(f"SensorWidget {self.sensor_id_str}: Initializing {len(channels)} plots")
            
            # Clear existing plots
            self._clear_plots()
            
            # Reset plot components
            self.plots = []
            self.hb_curves = []
            self.hbo2_curves = []
            
            if not channels:
                return
            
            # Create plots for each channel
            for i, ch in enumerate(channels):
                plot = self._create_plot_widget(ch, i)
                if plot:
                    self.plots.append(plot)
                    self.ui.VBoxLayout_Plot.addWidget(plot)
                    
                    # Create curves for HbO2 (blue) and Hb (red)
                    hb_curve = plot.plot(
                        np.array([0]), np.array([0]), 
                        pen=pg.mkPen("#0000FF", width=2), 
                        name='HbO2'
                    )
                    hbo2_curve = plot.plot(
                        np.array([0]), np.array([0]), 
                        pen=pg.mkPen("#FF0000", width=2), 
                        name='Hb'
                    )
                    
                    self.hb_curves.append(hb_curve)
                    self.hbo2_curves.append(hbo2_curve)
            
            # Update container size
            plot_height = len(channels) * 280 + 50
            self.ui.Widget_Plot.setMinimumSize(800, plot_height)
            
            # Start plot update timer
            if not self.plot_timer.isActive():
                self.plot_timer.start()
            
            print(f"SensorWidget {self.sensor_id_str}: Plots initialized successfully")
            
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Plot initialization error - {e}")
            self.networkError.emit(f"Plot initialization error: {str(e)}")
    
    def _create_plot_widget(self, channel, index):
        """Create a single plot widget for a channel"""
        try:
            plot = pg.PlotWidget()
            plot.setBackground('w')
            plot.setMinimumSize(750, 250)
            plot.setMaximumSize(900, 270)
            
            # Configure plot appearance
            # plot.showGrid(x=True, y=True, alpha=0.3)
            plot.setLabel('left', f"S{channel[0]}-D{channel[1]} (Ch{index+1})")
            plot.setLabel('bottom', 'Time (samples)')
            plot.setDownsampling(mode='peak')
            plot.setClipToView(True)
            
            # Add legend
            plot.addLegend(offset=(10, 10))
            
            return plot
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error creating plot widget - {e}")
            return None
    
    def _clear_plots(self):
        """Clear all existing plot widgets"""
        try:
            # Stop update timer
            if self.plot_timer.isActive():
                self.plot_timer.stop()
            
            # Remove widgets from vertical layout
            while self.ui.VBoxLayout_Plot.count():
                item = self.ui.VBoxLayout_Plot.takeAt(0)
                if item.widget():
                    widget = item.widget()
                    widget.setParent(None)
                    widget.deleteLater()
            
            # Clear references
            self.plots.clear()
            self.hb_curves.clear()
            self.hbo2_curves.clear()
            self.pending_data = None
            
            # Process pending deletions
            QTimer.singleShot(10, lambda: self.repaint())
            
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error clearing plots - {e}")
    
    def updatePlots(self, time, resolved_data):
        """Update plots with new data (optimized for performance)"""
        try:
            if resolved_data.shape[0] == 0 or time.shape[0] == 0:
                return
            
            # Store data for batch update
            self.pending_data = {
                'time': time,
                'resolved': resolved_data
            }
            
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Plot data error - {e}")
    
    def _update_plots_batch(self):
        """Batch update plots for better performance"""
        if not self.pending_data or len(self.plots) == 0:
            return
        
        try:
            time = self.pending_data['time']
            resolved = self.pending_data['resolved']
            
            if len(time) == 0 or resolved.shape[0] == 0:
                return
            
            # Update each plot with windowed data for performance
            for i in range(min(len(self.plots), resolved.shape[2])):
                if i < len(self.hb_curves) and i < len(self.hbo2_curves):
                    # Use time window for performance
                    start_idx = max(0, len(time) - TIME_WINDOW)
                    time_window = time[start_idx:]
                    hb_data = resolved[start_idx:, 1, i]    # HbO2 (blue)
                    hbo2_data = resolved[start_idx:, 0, i]  # Hb (red)
                    
                    # Update curves
                    self.hb_curves[i].setData(time_window, hb_data)
                    self.hbo2_curves[i].setData(time_window, hbo2_data)
            
            # Clear pending data
            self.pending_data = None
            
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Plot update error - {e}")
            self.pending_data = None
    
    # === UI State Management ===
    
    def setButtonAlarmState(self, button_type, is_alarm=True):
        """Set button alarm state for visual feedback
        
        Args:
            button_type: 'sample_rate' or 'channels'
            is_alarm: True for alarm state, False for normal state
        """
        try:
            if button_type == 'sample_rate':
                self._set_sample_rate_button_alarm(is_alarm)
            elif button_type == 'channels':
                self._set_channel_button_alarm(is_alarm)
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error setting button alarm - {e}")
    
    def _set_sample_rate_button_alarm(self, is_alarm=True):
        """Set sample rate button alarm state"""
        try:
            if is_alarm:
                self.ui.Button_SampleRate.setStyleSheet("""
                    QPushButton {
                        background-color: #F44336;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 6px;
                    }
                    QPushButton:hover {
                        background-color: #D32F2F;
                    }
                """)
            else:
                self.ui.Button_SampleRate.setStyleSheet("""
                    QPushButton {
                        background-color: #2196F3;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 6px;
                    }
                    QPushButton:hover {
                        background-color: #1976D2;
                    }
                    QPushButton:disabled {
                        background-color: #cccccc;
                        color: #666666;
                    }
                """)
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error setting sample rate button alarm - {e}")
    
    def _set_channel_button_alarm(self, is_alarm=True):
        """Set channel button alarm state"""
        try:
            if is_alarm:
                self.ui.Button_Channels.setStyleSheet("""
                    QPushButton {
                        background-color: #F44336;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-weight: bold;
                        font-size: 10px;
                        padding: 6px 8px;
                    }
                    QPushButton:hover {
                        background-color: #D32F2F;
                    }
                """)
            else:
                self.ui.Button_Channels.setStyleSheet("""
                    QPushButton {
                        background-color: #FF9800;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-weight: bold;
                        font-size: 10px;
                        padding: 6px 8px;
                    }
                    QPushButton:hover {
                        background-color: #F57C00;
                    }
                    QPushButton:disabled {
                        background-color: #cccccc;
                        color: #666666;
                    }
                """)
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error setting channel button alarm - {e}")
    
    # === Utility Methods ===
    
    def getSelectedChannels(self):
        """Get currently selected channel pairs"""
        try:
            selected = []
            channel_checkboxes = self._get_channel_checkboxes()
            
            for (light, detector), checkbox in channel_checkboxes.items():
                try:
                    if checkbox.isChecked():
                        selected.append([light, detector])  # Return as list format for compatibility
                except:
                    continue
            return selected
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error getting selected channels - {e}")
            return []
    
    def getHardwareConfig(self):
        """Get current hardware configuration"""
        try:
            return {
                'lights': self.ui.SpinBox_Lights.value(),
                'detectors': self.ui.SpinBox_Detectors.value(),
                'sample_rate': self.ui.ComboBox_SampleRate.currentText(),
                'channels': self.getSelectedChannels()
            }
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error getting hardware config - {e}")
            return {'lights': 8, 'detectors': 8, 'sample_rate': '100', 'channels': []}
    
    def resetWidget(self):
        """Reset widget to default state"""
        try:
            print(f"SensorWidget {self.sensor_id_str}: Resetting widget")
            
            # Stop timers
            if self.plot_timer.isActive():
                self.plot_timer.stop()
            
            # Clear plots
            self._clear_plots()
            
            # Reset channel configuration
            self.ui.SpinBox_Lights.setValue(8)
            self.ui.SpinBox_Detectors.setValue(8)
            
            # Reset sample rate
            self.ui.ComboBox_SampleRate.setCurrentIndex(3)  # Default to 100Hz
            
            # Clear current channels
            self.current_channels = []
            
            # Reset button states
            self.setButtonAlarmState('sample_rate', False)
            self.setButtonAlarmState('channels', False)
            
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error resetting widget - {e}")
    
    def getWidgetInfo(self):
        """Get widget information for debugging"""
        try:
            channel_checkboxes = self._get_channel_checkboxes()
            return {
                'sensor_id': self.sensor_id_str,
                'sensor_type': self.type_string,
                'current_channels': len(self.current_channels),
                'active_plots': len(self.plots),
                'timer_active': self.plot_timer.isActive(),
                'checkboxes': len(channel_checkboxes),
                'hardware_config': self.getHardwareConfig()
            }
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error getting widget info - {e}")
            return {}
    
    # === Legacy Compatibility Methods ===
    
    def PlotWidgetInit(self, channels):
        """Legacy method - use initializePlots instead"""
        self.initializePlots(channels)
    
    def Plot(self, time, resolved):
        """Legacy method - use updatePlots instead"""
        self.updatePlots(time, resolved)
    
    def getChannels(self):
        """Legacy method for compatibility"""
        try:
            lights = self.ui.SpinBox_Lights.value()
            detectors = self.ui.SpinBox_Detectors.value()
            channels = self.getSelectedChannels()
            return lights, detectors, channels
        except Exception as e:
            print(f"SensorWidget {self.sensor_id_str}: Error in getChannels - {e}")
            return 8, 8, []
    
    def UpdateSampleRate(self):
        """Legacy method for compatibility"""
        self._on_sample_rate_clicked()
    
    def UpdateChannels(self):
        """Legacy method for compatibility"""
        self._on_channels_clicked()
    
    def SetSampleRateButtonAlarm(self, is_alarm=True):
        """Legacy method for compatibility"""
        self.setButtonAlarmState('sample_rate', is_alarm)
    
    def SetChannelButtonAlarm(self, is_alarm=True):
        """Legacy method for compatibility"""
        self.setButtonAlarmState('channels', is_alarm)
    
    def reset_widget(self):
        """Legacy method for compatibility"""
        self.resetWidget()
    
    def get_widget_info(self):
        """Legacy method for compatibility"""
        return self.getWidgetInfo()
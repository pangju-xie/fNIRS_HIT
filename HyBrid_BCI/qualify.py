# -*- coding: utf-8 -*-
"""
fNIRS Channel Quality Assessment Application
============================================

This application provides real-time assessment of fNIRS channel quality
using either photoelectric signal strength or scalp-coupling index (SCI).

Features:
- Real-time signal monitoring at 750nm and 850nm wavelengths
- Dynamic channel configuration
- Signal quality assessment with visual indicators
- One-second update frequency
"""

import sys
import random
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel
from ui_qualify import Ui_Form


class ChannelData:
    """Data structure to hold channel information"""
    def __init__(self, channel_name):
        self.name = channel_name
        self.signal_750nm = 0.0
        self.signal_850nm = 0.0
        self.quality_status = "Unknown"
        self.last_update = None


class SignalGenerator:
    """Simulates fNIRS signal data for demonstration purposes"""
    
    @staticmethod
    def generate_signal_strength():
        """Generate realistic signal strength values (0-5000 mV range)"""
        base_signal = random.uniform(1000, 4000)
        noise = random.uniform(-200, 200)
        return max(0, base_signal + noise)
    
    @staticmethod
    def calculate_sci(signal_750, signal_850):
        """Calculate Scalp Coupling Index (SCI) based on signal values"""
        if signal_750 == 0 or signal_850 == 0:
            return 0.0
        return abs(signal_750 - signal_850) / (signal_750 + signal_850)
    
    @staticmethod
    def get_quality_status(value, assessment_method):
        """Determine quality status based on signal value and method"""
        if assessment_method == 0:  # Signal strength
            if value > 3000:
                return "Excellent", "#4CAF50"
            elif value > 2000:
                return "Good", "#8BC34A"
            elif value > 1000:
                return "Fair", "#FF9800"
            else:
                return "Poor", "#F44336"
        else:  # SCI
            if value < 0.1:
                return "Excellent", "#4CAF50"
            elif value < 0.2:
                return "Good", "#8BC34A"
            elif value < 0.3:
                return "Fair", "#FF9800"
            else:
                return "Poor", "#F44336"


class ChannelWidget(QWidget):
    """Custom widget for displaying individual channel data"""
    
    def __init__(self, channel_data, assessment_method=0):
        super().__init__()
        self.channel_data = channel_data
        self.assessment_method = assessment_method
        self.setupUI()
    
    def setupUI(self):
        """Setup the UI components for the channel widget"""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Channel name label
        self.name_label = QLabel(self.channel_data.name)
        self.name_label.setFixedWidth(80)
        self.name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("border: 1px solid #ddd; padding: 5px; background-color: #f9f9f9;")
        layout.addWidget(self.name_label)
        
        # 750nm signal display
        self.signal_750_edit = QLineEdit()
        self.signal_750_edit.setFixedWidth(120)
        self.signal_750_edit.setReadOnly(True)
        self.signal_750_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.signal_750_edit)
        
        # 850nm signal display
        self.signal_850_edit = QLineEdit()
        self.signal_850_edit.setFixedWidth(120)
        self.signal_850_edit.setReadOnly(True)
        self.signal_850_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.signal_850_edit)
        
        # Quality status display
        self.quality_label = QLabel("Unknown")
        self.quality_label.setFixedWidth(100)
        self.quality_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.quality_label.setStyleSheet("border: 1px solid #ddd; padding: 5px; background-color: white;")
        layout.addWidget(self.quality_label)
        
        # Unit label
        unit_text = "mV" if self.assessment_method == 0 else "SCI"
        self.unit_label = QLabel(unit_text)
        self.unit_label.setFixedWidth(50)
        self.unit_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.unit_label.setStyleSheet("border: 1px solid #ddd; padding: 5px; background-color: #f9f9f9;")
        layout.addWidget(self.unit_label)
        
        self.setLayout(layout)
    
    def update_data(self, signal_750, signal_850, assessment_method):
        """Update the displayed data"""
        self.assessment_method = assessment_method
        
        # Update signal displays
        self.signal_750_edit.setText(f"{signal_750:.1f}")
        self.signal_850_edit.setText(f"{signal_850:.1f}")
        
        # Calculate and display quality
        if assessment_method == 0:  # Signal strength
            avg_signal = (signal_750 + signal_850) / 2
            status, color = SignalGenerator.get_quality_status(avg_signal, assessment_method)
            self.unit_label.setText("mV")
        else:  # SCI
            sci_value = SignalGenerator.calculate_sci(signal_750, signal_850)
            status, color = SignalGenerator.get_quality_status(sci_value, assessment_method)
            self.unit_label.setText("SCI")
        
        self.quality_label.setText(status)
        self.quality_label.setStyleSheet(f"border: 1px solid #ddd; padding: 5px; background-color: {color}; color: white; font-weight: bold;")


class QualifyApp(QWidget):
    """Main application class for fNIRS channel quality assessment"""
    
    def __init__(self):
        super().__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # Initialize application state
        self.channels = []
        self.channel_widgets = []
        self.is_running = False
        self.assessment_method = 0
        
        # Setup timer for 1-second updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_signals)
        
        # Setup UI connections
        self.setup_connections()
        
        # Initialize channels (default 16 channels for demonstration)
        self.initialize_channels(16)
    
    def setup_connections(self):
        """Setup signal-slot connections"""
        self.ui.startButton.clicked.connect(self.start_assessment)
        self.ui.stopButton.clicked.connect(self.stop_assessment)
        self.ui.resetButton.clicked.connect(self.reset_channels)
        self.ui.completeButton.clicked.connect(self.complete_assessment)
        self.ui.methodComboBox.currentIndexChanged.connect(self.change_assessment_method)
    
    def initialize_channels(self, num_channels):
        """Initialize channel data and widgets"""
        # Clear existing channels
        self.channels.clear()
        self.clear_channel_widgets()
        
        # Create channel data
        for i in range(1, num_channels + 1):
            channel_name = f"S{i}-D{i}"
            self.channels.append(ChannelData(channel_name))
        
        # Create channel widgets
        self.create_channel_widgets()
    
    def clear_channel_widgets(self):
        """Clear all channel widgets from the scroll area"""
        for widget in self.channel_widgets:
            widget.deleteLater()
        self.channel_widgets.clear()
    
    def create_channel_widgets(self):
        """Create and layout channel widgets in the scroll area"""
        # Create main layout for scroll area content
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(2)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create widgets for each channel
        for channel in self.channels:
            channel_widget = ChannelWidget(channel, self.assessment_method)
            self.channel_widgets.append(channel_widget)
            scroll_layout.addWidget(channel_widget)
        
        # Add stretch to push widgets to top
        scroll_layout.addStretch()
        
        # Set layout to scroll area content
        self.ui.scrollAreaWidgetContents.setLayout(scroll_layout)
    
    def start_assessment(self):
        """Start real-time signal assessment"""
        if not self.is_running:
            self.is_running = True
            self.ui.startButton.setEnabled(False)
            self.ui.stopButton.setEnabled(True)
            self.ui.statusLabel.setText("更新状态：运行中")
            self.ui.statusLabel.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            # Start 1-second timer
            self.update_timer.start(1000)
            
            print("fNIRS channel quality assessment started")
    
    def stop_assessment(self):
        """Stop real-time signal assessment"""
        if self.is_running:
            self.is_running = False
            self.ui.startButton.setEnabled(True)
            self.ui.stopButton.setEnabled(False)
            self.ui.statusLabel.setText("更新状态：已停止")
            self.ui.statusLabel.setStyleSheet("color: #f44336; font-weight: bold;")
            
            # Stop timer
            self.update_timer.stop()
            
            print("fNIRS channel quality assessment stopped")
    
    def reset_channels(self):
        """Reset all channel data"""
        self.stop_assessment()
        
        # Reset channel data
        for channel in self.channels:
            channel.signal_750nm = 0.0
            channel.signal_850nm = 0.0
            channel.quality_status = "Unknown"
        
        # Update display
        for widget in self.channel_widgets:
            widget.update_data(0.0, 0.0, self.assessment_method)
        
        self.ui.statusLabel.setText("更新状态：已重置")
        self.ui.statusLabel.setStyleSheet("color: #666;")
        
        print("Channel data reset")
    
    def complete_assessment(self):
        """Complete assessment and show summary"""
        self.stop_assessment()
        
        # Calculate summary statistics
        total_channels = len(self.channels)
        excellent_count = 0
        good_count = 0
        fair_count = 0
        poor_count = 0
        
        for i, channel in enumerate(self.channels):
            if i < len(self.channel_widgets):
                widget = self.channel_widgets[i]
                status_text = widget.quality_label.text()
                
                if status_text == "Excellent":
                    excellent_count += 1
                elif status_text == "Good":
                    good_count += 1
                elif status_text == "Fair":
                    fair_count += 1
                elif status_text == "Poor":
                    poor_count += 1
        
        # Show summary message
        method_name = "光电信号强度" if self.assessment_method == 0 else "头皮耦合指数(SCI)"
        summary_msg = f"""
        评估完成！
        
        评估方法：{method_name}
        总通道数：{total_channels}
        
        质量统计：
        • 优秀：{excellent_count} 个通道
        • 良好：{good_count} 个通道  
        • 一般：{fair_count} 个通道
        • 差：{poor_count} 个通道
        
        优秀率：{(excellent_count/total_channels*100):.1f}%
        """
        
        msg_box = QtWidgets.QMessageBox()
        msg_box.setWindowTitle("评估完成")
        msg_box.setText(summary_msg)
        msg_box.setIcon(QtWidgets.QMessageBox.Information)
        msg_box.exec_()
        
        print("Assessment completed")
        print(summary_msg)
    
    def change_assessment_method(self, index):
        """Change assessment method"""
        self.assessment_method = index
        method_name = "光电信号强度" if index == 0 else "头皮耦合指数(SCI)"
        
        # Update all channel widgets
        for widget in self.channel_widgets:
            widget.assessment_method = index
            # Update unit labels
            unit_text = "mV" if index == 0 else "SCI"
            widget.unit_label.setText(unit_text)
        
        print(f"Assessment method changed to: {method_name}")
    
    def update_signals(self):
        """Update signal values for all channels (called every second)"""
        if not self.is_running:
            return
        
        for i, channel in enumerate(self.channels):
            # Generate new signal values
            signal_750 = SignalGenerator.generate_signal_strength()
            signal_850 = SignalGenerator.generate_signal_strength()
            
            # Update channel data
            channel.signal_750nm = signal_750
            channel.signal_850nm = signal_850
            
            # Update corresponding widget
            if i < len(self.channel_widgets):
                self.channel_widgets[i].update_data(signal_750, signal_850, self.assessment_method)
        
        # Update status to show last update time
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        self.ui.statusLabel.setText(f"更新状态：运行中 ({current_time})")
    
    def set_channel_count(self, count):
        """Set the number of channels dynamically"""
        self.stop_assessment()
        self.initialize_channels(count)
        print(f"Channel count set to: {count}")
    
    def get_channel_data(self):
        """Get current channel data for external use"""
        return self.channels
    
    def closeEvent(self, event):
        """Handle application close event"""
        self.stop_assessment()
        event.accept()


def main():
    """Main function to run the application"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("fNIRS Channel Quality Assessment")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("fNIRS Research Lab")
    
    # Create and show main window
    window = QualifyApp()
    window.show()
    
    # Example: Set custom channel count (uncomment to use)
    # window.set_channel_count(24)  # Set 24 channels instead of default 16
    
    print("fNIRS Channel Quality Assessment Application Started")
    print("Features:")
    print("- Real-time signal monitoring at 750nm and 850nm")
    print("- Signal strength and SCI assessment methods")
    print("- 1-second update frequency")
    print("- Dynamic channel configuration")
    print("- Visual quality indicators")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
Integration Example
Shows how to integrate the configure and display implementations with the main window
"""

import sys
from PyQt5.QtWidgets import QApplication

# Import the main window and implementation widgets
from mainwindow import fNIRSMainWindow
from configure import ConfigureWidget
from display import DisplayWidget


def main():
    """Main application entry point with sub-window integration"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    try:
        # Create main window
        main_window = fNIRSMainWindow()
        
        # Create implementation widgets
        configure_widget = ConfigureWidget()
        display_widget = DisplayWidget()
        
        # Integrate implementations with main window
        main_window.set_configure_implementation(configure_widget)
        main_window.set_display_implementation(display_widget)
        
        # Connect cross-widget signals if needed
        # For example, pass device info from configure to display
        configure_widget.configuration_completed.connect(
            lambda configured: display_widget.log_message(f"配置状态更新: {configured}")
        )
        
        # Show main window
        main_window.show()
        
        # Run application
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
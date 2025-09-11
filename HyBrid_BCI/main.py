# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import QApplication

import mainwindow
import user
import config
import qualify
import display
import network
import fNIRS

def main():
    """Main application entry point with sub-window integration"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("fNIRS Data Acquisition System")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("fNIRS Solutions")
    app.setStyle('Fusion')
    try:
        main_window = mainwindow.MainWindow()
        main_window.show()
        
        # 网络模块
        Network = network.UdpPort(1227, 2227)
        sys.exit(app.exec_())
    
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
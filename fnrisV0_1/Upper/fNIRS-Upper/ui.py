# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QSizePolicy, QHBoxLayout, QVBoxLayout, QGridLayout, QStackedWidget
from PyQt5.QtCore import Qt, pyqtSignal

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1600, 1000)
        MainWindow.setMinimumSize(QtCore.QSize(1200, 800))
        
        # Set window icon and title
        MainWindow.setWindowTitle("fNIRS信号采集系统")
        
        # Central widget
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        
        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)
        
        # === TOP CONTROL PANEL ===
        self.control_frame = QtWidgets.QFrame(self.centralwidget)
        self.control_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.control_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.control_frame.setMaximumHeight(70)
        self.control_frame.setMinimumHeight(70)
        self.control_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.control_layout = QtWidgets.QHBoxLayout(self.control_frame)
        self.control_layout.setContentsMargins(10, 5, 10, 5)
        self.control_layout.setSpacing(12)
        
        # Connection control group
        self.connection_group = QtWidgets.QGroupBox("连接控制")
        self.connection_group.setMaximumWidth(140)
        self.connection_group.setMaximumHeight(60)
        self.connection_layout = QtWidgets.QHBoxLayout(self.connection_group)
        self.connection_layout.setContentsMargins(5, 5, 5, 5)
        self.connection_layout.setSpacing(5)
        
        # Connection toggle button
        self.Button_Connection = QtWidgets.QPushButton("连接")
        self.Button_Connection.setMinimumSize(QtCore.QSize(70, 30))
        self.Button_Connection.setMaximumSize(QtCore.QSize(70, 30))
        self.Button_Connection.setObjectName("Button_Connection")
        self.Button_Connection.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        self.connection_layout.addWidget(self.Button_Connection)
        
        # Sampling control group
        self.sampling_group = QtWidgets.QGroupBox("采样控制")
        self.sampling_group.setMaximumWidth(140)
        self.sampling_group.setMaximumHeight(60)
        self.sampling_layout = QtWidgets.QHBoxLayout(self.sampling_group)
        self.sampling_layout.setContentsMargins(5, 5, 5, 5)
        self.sampling_layout.setSpacing(5)
        
        # Start sampling button
        self.Button_Sampling = QtWidgets.QPushButton("开始")
        self.Button_Sampling.setMinimumSize(QtCore.QSize(70, 30))
        self.Button_Sampling.setMaximumSize(QtCore.QSize(70, 30))
        self.Button_Sampling.setObjectName("Button_Sampling")
        self.Button_Sampling.setEnabled(False)
        self.Button_Sampling.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        self.sampling_layout.addWidget(self.Button_Sampling)
        
        # System Status group
        self.status_group = QtWidgets.QGroupBox("系统状态")
        self.status_group.setMaximumHeight(60)
        self.status_group.setMinimumWidth(450)
        self.status_layout = QtWidgets.QHBoxLayout(self.status_group)
        self.status_layout.setContentsMargins(5, 5, 5, 5)
        self.status_layout.setSpacing(15)
        
        # Connection status label
        self.status_label = QtWidgets.QLabel("状态: 未连接")
        self.status_label.setStyleSheet("color: #666666; font-weight: bold; font-size: 11px;")
        self.status_label.setMinimumWidth(80)
        
        # Device count label
        self.device_count_label = QtWidgets.QLabel("设备: 0台")
        self.device_count_label.setStyleSheet("color: #666666; font-size: 11px;")
        self.device_count_label.setMinimumWidth(60)
        
        # Device info label
        self.device_info_label = QtWidgets.QLabel("设备信息: --")
        self.device_info_label.setStyleSheet("color: #666666; font-size: 11px;")
        self.device_info_label.setMinimumWidth(120)
        
        # Battery status label
        self.battery_label = QtWidgets.QLabel("电量: --%")
        self.battery_label.setStyleSheet("color: #666666; font-size: 11px;")
        self.battery_label.setMinimumWidth(70)
        
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addWidget(self.device_count_label)
        self.status_layout.addWidget(self.device_info_label)
        self.status_layout.addWidget(self.battery_label)
        self.status_layout.addStretch()
        
        # Add groups to control layout
        self.control_layout.addWidget(self.connection_group)
        self.control_layout.addWidget(self.sampling_group)
        self.control_layout.addWidget(self.status_group)
        self.control_layout.addStretch()
        
        # Add control frame to main layout
        self.main_layout.addWidget(self.control_frame)
        
        # === SUB-WINDOW SWITCHING AREA ===
        self.switch_frame = QtWidgets.QFrame(self.centralwidget)
        self.switch_frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.switch_frame.setMaximumHeight(50)
        self.switch_frame.setMinimumHeight(50)
        self.switch_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.switch_layout = QtWidgets.QHBoxLayout(self.switch_frame)
        self.switch_layout.setContentsMargins(10, 5, 10, 5)
        self.switch_layout.setSpacing(5)
        
        # Configure button
        self.Button_Configure = QtWidgets.QPushButton("配置 (Configure)")
        self.Button_Configure.setMinimumSize(QtCore.QSize(150, 35))
        self.Button_Configure.setObjectName("Button_Configure")
        self.Button_Configure.setCheckable(True)
        self.Button_Configure.setChecked(True)  # Default to configure view
        self.Button_Configure.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:checked {
                background-color: #E65100;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        # Display button
        self.Button_Display = QtWidgets.QPushButton("显示 (Display)")
        self.Button_Display.setMinimumSize(QtCore.QSize(150, 35))
        self.Button_Display.setObjectName("Button_Display")
        self.Button_Display.setCheckable(True)
        self.Button_Display.setEnabled(False)  # Disabled until configure is done
        self.Button_Display.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:checked {
                background-color: #4A148C;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        self.switch_layout.addWidget(self.Button_Configure)
        self.switch_layout.addWidget(self.Button_Display)
        self.switch_layout.addStretch()
        
        # Add switch frame to main layout
        self.main_layout.addWidget(self.switch_frame)
        
        # === STACKED WIDGET FOR SUB-WINDOWS ===
        self.stacked_widget = QStackedWidget(self.centralwidget)
        self.stacked_widget.setObjectName("stacked_widget")
        self.stacked_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Configure sub-window (placeholder)
        self.configure_widget = QtWidgets.QWidget()
        self.configure_widget.setObjectName("configure_widget")
        self.configure_layout = QtWidgets.QVBoxLayout(self.configure_widget)
        self.configure_layout.setContentsMargins(10, 10, 10, 10)
        
        # Configure title
        self.configure_title = QtWidgets.QLabel("设备配置界面")
        self.configure_title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333333;
                padding: 10px;
                border-bottom: 2px solid #FF9800;
                margin-bottom: 10px;
            }
        """)
        self.configure_layout.addWidget(self.configure_title)
        
        # Configure content area (to be implemented in separate file)
        self.configure_content = QtWidgets.QFrame()
        self.configure_content.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.configure_content.setStyleSheet("background-color: #f9f9f9; border: 1px solid #cccccc; border-radius: 5px;")
        self.configure_content_layout = QtWidgets.QVBoxLayout(self.configure_content)
        
        # Placeholder for configure interface
        self.configure_placeholder = QtWidgets.QLabel("配置界面将在单独的文件中实现")
        self.configure_placeholder.setAlignment(Qt.AlignCenter)
        self.configure_placeholder.setStyleSheet("color: #666666; font-size: 14px; padding: 50px;")
        self.configure_content_layout.addWidget(self.configure_placeholder)
        
        self.configure_layout.addWidget(self.configure_content)
        
        # Display sub-window (placeholder)
        self.display_widget = QtWidgets.QWidget()
        self.display_widget.setObjectName("display_widget")
        self.display_layout = QtWidgets.QVBoxLayout(self.display_widget)
        self.display_layout.setContentsMargins(10, 10, 10, 10)
        
        # Display title
        self.display_title = QtWidgets.QLabel("数据显示界面")
        self.display_title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333333;
                padding: 10px;
                border-bottom: 2px solid #9C27B0;
                margin-bottom: 10px;
            }
        """)
        self.display_layout.addWidget(self.display_title)
        
        # Display content area (to be implemented in separate file)
        self.display_content = QtWidgets.QFrame()
        self.display_content.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.display_content.setStyleSheet("background-color: #f9f9f9; border: 1px solid #cccccc; border-radius: 5px;")
        self.display_content_layout = QtWidgets.QVBoxLayout(self.display_content)
        
        # Placeholder for display interface
        self.display_placeholder = QtWidgets.QLabel("显示界面将在单独的文件中实现")
        self.display_placeholder.setAlignment(Qt.AlignCenter)
        self.display_placeholder.setStyleSheet("color: #666666; font-size: 14px; padding: 50px;")
        self.display_content_layout.addWidget(self.display_placeholder)
        
        self.display_layout.addWidget(self.display_content)
        
        # Add widgets to stacked widget
        self.stacked_widget.addWidget(self.configure_widget)
        self.stacked_widget.addWidget(self.display_widget)
        self.stacked_widget.setCurrentIndex(0)  # Default to configure view
        
        # Add stacked widget to main layout
        self.main_layout.addWidget(self.stacked_widget, 1)
        
        # Set central widget
        MainWindow.setCentralWidget(self.centralwidget)
        
        # === MENU BAR ===
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1600, 25))
        self.menubar.setObjectName("menubar")
        
        # File menu
        self.menu_file = self.menubar.addMenu("文件(&F)")
        self.action_save = QtWidgets.QAction("保存数据(&S)", MainWindow)
        self.action_save.setShortcut("Ctrl+S")
        self.action_exit = QtWidgets.QAction("退出(&X)", MainWindow)
        self.action_exit.setShortcut("Ctrl+Q")
        self.menu_file.addAction(self.action_save)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.action_exit)
        
        # Settings menu
        self.menu_settings = self.menubar.addMenu("设置(&S)")
        self.action_preferences = QtWidgets.QAction("首选项(&P)", MainWindow)
        self.menu_settings.addAction(self.action_preferences)
        
        # Help menu
        self.menu_help = self.menubar.addMenu("帮助(&H)")
        self.action_about = QtWidgets.QAction("关于(&A)", MainWindow)
        self.menu_help.addAction(self.action_about)
        
        MainWindow.setMenuBar(self.menubar)
        
        # === STATUS BAR ===
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        self.statusbar.setMinimumHeight(25)
        self.statusbar.showMessage("就绪")
        MainWindow.setStatusBar(self.statusbar)
        
        # UI State tracking variables
        self.is_connected = False
        self.is_sampling = False
        self.is_configured = False
        
        # Connect basic UI signals
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "fNIRS 信号采集系统"))
    
    # === UI Update Methods ===
    
    def set_connection_state(self, connected):
        """Update UI elements based on connection state"""
        self.is_connected = connected
        
        if connected:
            self.Button_Connection.setText("断开")
            self.Button_Connection.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
            
            self.status_label.setText("状态: 已连接")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 11px;")
            self.statusbar.showMessage("设备连接成功")
            
        else:
            self.Button_Connection.setText("连接")
            self.Button_Connection.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            
            # Reset states
            self.set_sampling_state(False)
            self.set_configured_state(False)
            
            self.status_label.setText("状态: 已断开")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold; font-size: 11px;")
            self.statusbar.showMessage("设备已断开连接")
            
            # Reset device information
            self.update_device_count(0)
            self.update_device_info("--", "")
            self.update_battery_status(-1)
    
    def set_sampling_state(self, sampling):
        """Update UI elements based on sampling state"""
        self.is_sampling = sampling
        
        if sampling:
            self.Button_Sampling.setText("停止")
            self.Button_Sampling.setStyleSheet("""
                QPushButton {
                    background-color: #FF5722;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #D84315;
                }
            """)
            
            self.status_label.setText("状态: 采样中")
            self.status_label.setStyleSheet("color: #2196F3; font-weight: bold; font-size: 12px;")
            self.statusbar.showMessage("开始采样...")
            
        else:
            self.Button_Sampling.setText("开始")
            self.Button_Sampling.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            
            # Update sampling button state based on configuration
            self.Button_Sampling.setEnabled(self.is_connected and self.is_configured)
            
            if self.is_connected:
                self.status_label.setText("状态: 已连接")
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
                self.statusbar.showMessage("采样已停止")
    
    def set_configured_state(self, configured):
        """Update UI elements based on configuration state"""
        self.is_configured = configured
        
        if configured:
            # Enable display button and sampling when connected
            self.Button_Display.setEnabled(True)
            self.Button_Sampling.setEnabled(self.is_connected)
            self.statusbar.showMessage("设备配置完成")
        else:
            # Disable display button and sampling
            self.Button_Display.setEnabled(False)
            self.Button_Display.setChecked(False)
            self.Button_Sampling.setEnabled(False)
            # Switch back to configure view
            self.switch_to_configure()
    
    def switch_to_configure(self):
        """Switch to configure sub-window"""
        self.stacked_widget.setCurrentIndex(0)
        self.Button_Configure.setChecked(True)
        self.Button_Display.setChecked(False)
    
    def switch_to_display(self):
        """Switch to display sub-window"""
        if self.is_configured:
            self.stacked_widget.setCurrentIndex(1)
            self.Button_Configure.setChecked(False)
            self.Button_Display.setChecked(True)
    
    def update_device_count(self, count):
        """Update device count display"""
        if count > 0:
            self.device_count_label.setText(f"设备: {count}台")
            self.device_count_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        else:
            self.device_count_label.setText("设备: 0台")
            self.device_count_label.setStyleSheet("color: #666666; font-size: 11px;")
    
    def update_device_info(self, device_id, device_type):
        """Update detailed device information"""
        if device_id != "--" and device_type:
            # Format device ID as string if it's a list
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
            type_name = type_names.get(device_type, f"类型{device_type}")
            
            self.device_info_label.setText(f"设备信息: {id_str} ({type_name})")
            self.device_info_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        else:
            self.device_info_label.setText("设备信息: --")
            self.device_info_label.setStyleSheet("color: #666666; font-size: 11px;")
    
    def update_battery_status(self, level):
        """Update battery level display with color coding"""
        if level >= 0:
            self.battery_label.setText(f"电量: {level}%")
            if level > 50:
                color = "#4CAF50"  # Green
            elif level > 20:
                color = "#FF9800"  # Orange
            else:
                color = "#f44336"  # Red
            self.battery_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
        else:
            self.battery_label.setText("电量: --%")
            self.battery_label.setStyleSheet("color: #666666; font-size: 11px;")

    # === Interface Methods for Sub-windows ===
    
    def get_configure_content_widget(self):
        """Get the configure content widget for external implementation"""
        return self.configure_content
    
    def get_display_content_widget(self):
        """Get the display content widget for external implementation"""
        return self.display_content
    
    def set_configure_implementation(self, configure_widget):
        """Set the configure implementation widget"""
        # Clear existing content
        for i in reversed(range(self.configure_content_layout.count())): 
            self.configure_content_layout.itemAt(i).widget().setParent(None)
        
        # Add new implementation
        self.configure_content_layout.addWidget(configure_widget)
    
    def set_display_implementation(self, display_widget):
        """Set the display implementation widget"""
        # Clear existing content
        for i in reversed(range(self.display_content_layout.count())): 
            self.display_content_layout.itemAt(i).widget().setParent(None)
        
        # Add new implementation
        self.display_content_layout.addWidget(display_widget)


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Set application-wide stylesheet
    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            font-size: 11px;
            border: 1px solid #cccccc;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 3px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 3px 0 3px;
        }
        QFrame {
            background-color: #ffffff;
        }
        QMainWindow {
            background-color: #f0f0f0;
        }
        QStatusBar {
            border-top: 1px solid #cccccc;
            background-color: #f8f8f8;
        }
        QStatusBar::item {
            border: none;
        }
        QStackedWidget {
            border: 1px solid #cccccc;
            border-radius: 5px;
            background-color: white;
        }
    """)
    
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
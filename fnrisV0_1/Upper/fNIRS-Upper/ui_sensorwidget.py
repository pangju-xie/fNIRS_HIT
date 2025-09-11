# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QSizePolicy, QHBoxLayout, QVBoxLayout, QGridLayout
from PyQt5.QtCore import Qt

class Ui_SensorWidget(object):
    def setupUi(self, SensorWidget):
        SensorWidget.setObjectName("SensorWidget")
        SensorWidget.resize(1500, 800)
        SensorWidget.setMinimumSize(QtCore.QSize(800, 400))
        
        # Main horizontal layout with 3:1 ratio
        self.main_layout = QHBoxLayout(SensorWidget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(8)
        
        # === LEFT SIDE: PLOT AREA (3 parts) ===
        self.plot_frame = QtWidgets.QFrame(SensorWidget)
        self.plot_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plot_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.plot_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
        """)
        
        # Plot layout
        self.plot_layout = QVBoxLayout(self.plot_frame)
        self.plot_layout.setContentsMargins(3, 3, 3, 3)
        self.plot_layout.setSpacing(3)
        
        # Scroll area for plots
        self.ScrollArea_Plot = QtWidgets.QScrollArea(self.plot_frame)
        self.ScrollArea_Plot.setWidgetResizable(True)
        self.ScrollArea_Plot.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ScrollArea_Plot.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ScrollArea_Plot.setObjectName("ScrollArea_Plot")
        self.ScrollArea_Plot.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #fafafa;
            }
        """)
        
        # Plot widget container
        self.Widget_Plot = QtWidgets.QWidget()
        self.Widget_Plot.setObjectName("Widget_Plot")
        self.Widget_Plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Plot layout - VBox layout for n rows x 1 column arrangement
        self.VBoxLayout_Plot = QVBoxLayout(self.Widget_Plot)
        self.VBoxLayout_Plot.setContentsMargins(5, 5, 5, 5)
        self.VBoxLayout_Plot.setSpacing(5)
        self.VBoxLayout_Plot.setObjectName("VBoxLayout_Plot")
        
        self.ScrollArea_Plot.setWidget(self.Widget_Plot)
        self.plot_layout.addWidget(self.ScrollArea_Plot)
        
        # Add plot frame to main layout (3 parts)
        self.main_layout.addWidget(self.plot_frame, 3)
        
        # === RIGHT SIDE: CONFIGURATION PANEL (1 part) ===
        self.config_frame = QtWidgets.QFrame(SensorWidget)
        self.config_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.config_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.config_frame.setMinimumWidth(200)
        self.config_frame.setMaximumWidth(280)
        self.config_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.config_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
        """)
        
        # Configuration layout
        # Configuration layout
        self.config_layout = QVBoxLayout(self.config_frame)
        self.config_layout.setContentsMargins(2, 2, 2, 2)
        self.config_layout.setSpacing(8)
        
        # === SAMPLE RATE SECTION ===
        self.sample_rate_group = QtWidgets.QGroupBox("采样率")
        # Remove fixed height constraints - let it size to content
        self.sample_rate_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.sample_rate_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #aaaaaa;
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px 0 3px;
            }
        """)
        
        self.sample_rate_layout = QVBoxLayout(self.sample_rate_group)
        self.sample_rate_layout.setContentsMargins(2, 2, 2, 2)
        self.sample_rate_layout.setSpacing(8)
        
        # Sample rate controls in horizontal layout
        sample_rate_horizontal = QHBoxLayout()
        sample_rate_horizontal.setSpacing(6)
        
        self.Label_SampleRateText = QtWidgets.QLabel("频率:")
        self.Label_SampleRateText.setStyleSheet("color: #666666; font-size: 11px; font-weight: bold;")
        self.Label_SampleRateText.setMinimumWidth(50)
        
        self.ComboBox_SampleRate = QtWidgets.QComboBox()
        self.ComboBox_SampleRate.setEditable(True)
        self.ComboBox_SampleRate.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.ComboBox_SampleRate.setObjectName("ComboBox_SampleRate")
        self.ComboBox_SampleRate.addItem("10")
        self.ComboBox_SampleRate.addItem("20")
        self.ComboBox_SampleRate.addItem("50")
        self.ComboBox_SampleRate.addItem("100")
        self.ComboBox_SampleRate.setMinimumHeight(30)
        self.ComboBox_SampleRate.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.Button_SampleRate = QtWidgets.QPushButton("设置")
        self.Button_SampleRate.setObjectName("Button_SampleRate")
        self.Button_SampleRate.setMinimumHeight(30)
        self.Button_SampleRate.setMinimumWidth(50)
        self.Button_SampleRate.setStyleSheet("""
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
        
        sample_rate_horizontal.addWidget(self.Label_SampleRateText)
        sample_rate_horizontal.addWidget(self.ComboBox_SampleRate)
        sample_rate_horizontal.addWidget(self.Button_SampleRate)
        
        self.sample_rate_layout.addLayout(sample_rate_horizontal)
        self.config_layout.addWidget(self.sample_rate_group, 0)  # Changed stretch factor from 1 to 0
        
        # === CHANNEL CONFIGURATION SECTION ===
        self.channel_group = QtWidgets.QGroupBox("通道配置")
        # Remove fixed height constraints - let it size to content naturally
        self.channel_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.channel_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #aaaaaa;
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px 0 3px;
            }
        """)
        
        self.channel_layout = QVBoxLayout(self.channel_group)
        self.channel_layout.setContentsMargins(8, 12, 8, 8)
        self.channel_layout.setSpacing(8)
        
        # Hardware settings in horizontal layout
        hardware_horizontal = QHBoxLayout()
        hardware_horizontal.setSpacing(6)
        
        self.Label_LightsText = QtWidgets.QLabel("光源:")
        self.Label_LightsText.setStyleSheet("color: #666666; font-size: 11px; font-weight: bold;")
        self.Label_LightsText.setMinimumWidth(35)
        
        self.SpinBox_Lights = QtWidgets.QSpinBox()
        self.SpinBox_Lights.setMinimum(1)
        self.SpinBox_Lights.setMaximum(16)
        self.SpinBox_Lights.setProperty("value", 8)
        self.SpinBox_Lights.setObjectName("SpinBox_Lights")
        self.SpinBox_Lights.setMinimumHeight(30)
        self.SpinBox_Lights.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.Label_DetectorsText = QtWidgets.QLabel("探测器:")
        self.Label_DetectorsText.setStyleSheet("color: #666666; font-size: 11px; font-weight: bold;")
        self.Label_DetectorsText.setMinimumWidth(50)
        
        self.SpinBox_Detectors = QtWidgets.QSpinBox()
        self.SpinBox_Detectors.setMinimum(1)
        self.SpinBox_Detectors.setMaximum(16)
        self.SpinBox_Detectors.setProperty("value", 8)
        self.SpinBox_Detectors.setObjectName("SpinBox_Detectors")
        self.SpinBox_Detectors.setMinimumHeight(30)
        self.SpinBox_Detectors.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        hardware_horizontal.addWidget(self.Label_LightsText)
        hardware_horizontal.addWidget(self.SpinBox_Lights)
        hardware_horizontal.addWidget(self.Label_DetectorsText)
        hardware_horizontal.addWidget(self.SpinBox_Detectors)
        
        self.channel_layout.addLayout(hardware_horizontal)
        
        # Channel configuration button at top of channel matrix section
        self.Button_Channels = QtWidgets.QPushButton("设置")
        self.Button_Channels.setObjectName("Button_Channels")
        self.Button_Channels.setMinimumHeight(30)
        self.Button_Channels.setMaximumHeight(32)
        self.Button_Channels.setStyleSheet("""
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
        
        self.channel_layout.addWidget(self.Button_Channels)
        
        # Channel matrix label
        self.Label_Channel = QtWidgets.QLabel("配置矩阵")
        self.Label_Channel.setStyleSheet("color: #666666; font-size: 11px; font-weight: bold;")
        self.channel_layout.addWidget(self.Label_Channel)
        
        # Scroll area for channel matrix with adaptive sizing
        self.ScrollArea_Channels = QtWidgets.QScrollArea()
        self.ScrollArea_Channels.setWidgetResizable(True)
        # Set preferred size but allow it to be flexible
        self.ScrollArea_Channels.setMinimumSize(200, 150)
        self.ScrollArea_Channels.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Enable both scroll bars
        self.ScrollArea_Channels.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.ScrollArea_Channels.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.ScrollArea_Channels.setObjectName("ScrollArea_Channels")
        self.ScrollArea_Channels.setStyleSheet("""
            QScrollArea {
                border: 1px solid #cccccc;
                border-radius: 2px;
                background-color: #ffffff;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
            QScrollBar:horizontal {
                background: #f0f0f0;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #c0c0c0;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #a0a0a0;
            }
        """)
        
        self.Widget_Channels = QtWidgets.QWidget()
        self.Widget_Channels.setObjectName("Widget_Channels")
        # Set a larger minimum size for the grid widget to ensure scrolling
        self.Widget_Channels.setMinimumSize(400, 400)
        
        # Grid layout for channel matrix with fixed spacing
        self.GridLayout_Channels = QGridLayout(self.Widget_Channels)
        self.GridLayout_Channels.setContentsMargins(4, 4, 4, 4)
        self.GridLayout_Channels.setSpacing(2)
        self.GridLayout_Channels.setObjectName("GridLayout_Channels")
        
        # Initialize default channel matrix
        self._populate_channel_matrix()
        
        self.ScrollArea_Channels.setWidget(self.Widget_Channels)
        self.channel_layout.addWidget(self.ScrollArea_Channels)
        
        self.config_layout.addWidget(self.channel_group, 1)  # Higher stretch factor to take more space
        
        # Add configuration frame to main layout (1 part)
        self.main_layout.addWidget(self.config_frame, 1)
        
        self.retranslateUi(SensorWidget)
        QtCore.QMetaObject.connectSlotsByName(SensorWidget)
    
    def _populate_channel_matrix(self):
        """Populate the channel matrix with checkboxes and headers"""
        # Clear any existing widgets first
        self._clear_channel_matrix()
        
        # Create default 8x8 matrix with headers
        sources = 8
        detectors = 8
        
        self._create_channel_matrix(sources, detectors)
    
    def _clear_channel_matrix(self):
        """Properly clear all widgets from the channel matrix"""
        # Process all pending events first
        QtCore.QCoreApplication.processEvents()
        
        # Remove all items from layout
        while self.GridLayout_Channels.count():
            child = self.GridLayout_Channels.takeAt(0)
            if child.widget():
                widget = child.widget()
                widget.setParent(None)
                widget.deleteLater()
        
        # Force layout update
        self.GridLayout_Channels.update()
        
        # Process pending deletions immediately
        QtCore.QCoreApplication.processEvents()
        
        # Reset widget size to allow for new content
        self.Widget_Channels.setMinimumSize(0, 0)
    
    def update_channel_matrix(self, sources, detectors):
        """Update the channel matrix based on new source and detector counts"""
        # Clear existing widgets properly
        self._clear_channel_matrix()
        
        # Small delay to ensure cleanup is complete
        QtCore.QTimer.singleShot(10, lambda: self._create_channel_matrix(sources, detectors))
    
    def _create_channel_matrix(self, sources, detectors):
        """Create channel matrix with headers and checkboxes"""
        # Create corner label (top-left)
        corner_label = QtWidgets.QLabel("")
        corner_label.setStyleSheet("""
            QLabel {
                background-color: #eeeeee;
                border: 1px solid #999999;
                border-radius: 2px;
                min-height: 25px;
                min-width: 35px;
                max-height: 25px;
                max-width: 35px;
            }
        """)
        self.GridLayout_Channels.addWidget(corner_label, 0, 0)
        
        # Create detector headers (first row)
        for d in range(1, detectors + 1):
            detector_header = QtWidgets.QLabel(f"D{d}")
            detector_header.setStyleSheet("""
                QLabel {
                    background-color: #f5f5f5;
                    border: 1px solid #999999;
                    border-radius: 2px;
                    padding: 2px;
                    font-size: 9px;
                    font-weight: bold;
                    color: #333333;
                    min-height: 25px;
                    min-width: 35px;
                    max-height: 25px;
                    max-width: 35px;
                    qproperty-alignment: AlignCenter;
                }
            """)
            self.GridLayout_Channels.addWidget(detector_header, 0, d)
        
        # Create source headers (first column)
        for s in range(1, sources + 1):
            source_header = QtWidgets.QLabel(f"S{s}")
            source_header.setStyleSheet("""
                QLabel {
                    background-color: #f5f5f5;
                    border: 1px solid #999999;
                    border-radius: 2px;
                    padding: 2px;
                    font-size: 9px;
                    font-weight: bold;
                    color: #333333;
                    min-height: 25px;
                    min-width: 35px;
                    max-height: 25px;
                    max-width: 35px;
                    qproperty-alignment: AlignCenter;
                }
            """)
            self.GridLayout_Channels.addWidget(source_header, s, 0)
        
        # Create channel checkboxes in the matrix (starting from row 1, col 1)
        for s in range(1, sources + 1):
            for d in range(1, detectors + 1):
                checkbox = QtWidgets.QCheckBox()
                checkbox.setObjectName(f"checkbox_S{s}D{d}")
                checkbox.setToolTip(f"Channel S{s}D{d}")
                checkbox.setStyleSheet("""
                    QCheckBox {
                        background-color: #ffffff;
                        border: 1px solid #2196f3;
                        border-radius: 2px;
                        padding: 2px;
                        min-height: 23px;
                        min-width: 33px;
                        max-height: 23px;
                        max-width: 33px;
                    }
                    QCheckBox::indicator {
                        width: 16px;
                        height: 16px;
                        border: 1px solid #2196f3;
                        border-radius: 2px;
                        background-color: #ffffff;
                    }
                    QCheckBox::indicator:checked {
                        background-color: #2196f3;
                        border-color: #1976d2;
                    }
                    QCheckBox::indicator:unchecked:hover {
                        background-color: #e3f2fd;
                    }
                """)
                
                # Default selection pattern - diagonal and adjacent channels
                if abs(s - d) <= 1:
                    checkbox.setChecked(True)
                
                # Position: row = s (source), col = d (detector)
                self.GridLayout_Channels.addWidget(checkbox, s, d)
        
        # Calculate and set the widget size based on the matrix dimensions
        # Fixed cell size for consistent layout
        cell_width = 37
        cell_height = 27
        
        # Calculate total size including margins
        total_width = (detectors + 1) * cell_width + 20
        total_height = (sources + 1) * cell_height + 20
        
        # Set the widget size to ensure proper scrolling
        self.Widget_Channels.setFixedSize(total_width, total_height)
        
        # Force widget updates
        self.Widget_Channels.adjustSize()
        self.ScrollArea_Channels.update()
        self.Widget_Channels.update()
        
        # Process all events
        QtCore.QCoreApplication.processEvents()

    def retranslateUi(self, SensorWidget):
        _translate = QtCore.QCoreApplication.translate
        SensorWidget.setWindowTitle(_translate("SensorWidget", "传感器"))
        self.sample_rate_group.setTitle(_translate("SensorWidget", "采样率"))
        self.Label_SampleRateText.setText(_translate("SensorWidget", "频率:"))
        self.ComboBox_SampleRate.setItemText(0, _translate("SensorWidget", "10"))
        self.ComboBox_SampleRate.setItemText(1, _translate("SensorWidget", "20"))
        if self.ComboBox_SampleRate.count() > 2:
            self.ComboBox_SampleRate.setItemText(2, _translate("SensorWidget", "50"))
        if self.ComboBox_SampleRate.count() > 3:
            self.ComboBox_SampleRate.setItemText(3, _translate("SensorWidget", "100"))
        self.Button_SampleRate.setText(_translate("SensorWidget", "设置"))
        self.channel_group.setTitle(_translate("SensorWidget", "通道配置"))
        self.Label_LightsText.setText(_translate("SensorWidget", "光源:"))
        self.Label_DetectorsText.setText(_translate("SensorWidget", "探测器:"))
        self.Label_Channel.setText(_translate("SensorWidget", "通道矩阵"))
        self.Button_Channels.setText(_translate("SensorWidget", "设置通道"))
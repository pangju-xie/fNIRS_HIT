# ui/views/display_view.py
from PyQt5 import QtCore, QtGui, QtWidgets

class DisplayViewWidget(object):
    """实时波形采集与展示界面 (纯 UI 布局 - PyQt5 适配版)"""
    def setupUi(self, Form):
        Form.setObjectName("DisplayForm")
        self.mainLayout = QtWidgets.QVBoxLayout(Form)
        self.mainLayout.setContentsMargins(5, 5, 5, 5)
        self.mainLayout.setSpacing(5)

        # ==========================================
        # 1. 顶部全局控制台 
        # ==========================================
        self.controlFrame = QtWidgets.QFrame()
        self.controlFrame.setObjectName("bottomControlBar")
        self.controlLayout = QtWidgets.QHBoxLayout(self.controlFrame)
        
        self.btnStart = QtWidgets.QPushButton("开始")
        self.btnStart.setObjectName("btnStart")
        
        self.btnStop = QtWidgets.QPushButton("停止")
        self.btnStop.setObjectName("btnStop")
        self.btnStop.setEnabled(False)
        
        self.btnRecord = QtWidgets.QPushButton("记录")
        self.btnRecord.setObjectName("btnRecord")
        self.btnRecord.setEnabled(False)
        
        self.btnReset = QtWidgets.QPushButton("重置")
        self.btnReset.setObjectName("btnReset")
        
        self.btnComplete = QtWidgets.QPushButton("完成 >>")
        self.btnComplete.setObjectName("btnComplete")
        
        self.controlLayout.addWidget(self.btnStart)
        self.controlLayout.addWidget(self.btnStop)
        self.controlLayout.addWidget(self.btnRecord)
        self.controlLayout.addWidget(self.btnReset)
        self.controlLayout.addWidget(self.btnComplete)
        self.controlLayout.addStretch() 
    
        # ==========================================
        # 2. 左右波形分栏 (Splitter)
        # ==========================================
        self.mainSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # --- 左侧: fNIRS 面板 ---
        self.fnirsPanel = self._create_signal_panel("fNIRS", "fnirs", "mV", has_signal_type=True)
        self.mainSplitter.addWidget(self.fnirsPanel)
        
        # --- 右侧: EEG & sEMG 面板 (垂直分割) ---
        self.rightSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.eegPanel = self._create_signal_panel("EEG", "eeg", "µV", has_signal_type=False)
        self.semgPanel = self._create_signal_panel("sEMG", "semg", "mV", has_signal_type=False)
        
        self.rightSplitter.addWidget(self.eegPanel)
        self.rightSplitter.addWidget(self.semgPanel)
        
        self.mainSplitter.addWidget(self.rightSplitter)
        self.mainSplitter.setSizes([600, 600]) 
        
        self.mainLayout.addWidget(self.mainSplitter, stretch=1)
        self.mainLayout.addWidget(self.controlFrame)
        
    def _create_signal_panel(self, title, prefix, unit, has_signal_type=False):
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 1. 顶部参数头
        headerLayout = QtWidgets.QHBoxLayout()
        headerLayout.addWidget(QtWidgets.QLabel(f"<b>{title}</b>", styleSheet="font-size: 14px; color: #2c3e50;")) # type: ignore
        headerLayout.addStretch()
        
        chkEnable = QtWidgets.QCheckBox("开启滤波")
        setattr(self, f"chkEnable_{prefix}", chkEnable)
        headerLayout.addWidget(chkEnable)
        headerLayout.addSpacing(10)
        
        if has_signal_type:
            headerLayout.addWidget(QtWidgets.QLabel("信号源:"))
            comboType = QtWidgets.QComboBox()
            comboType.addItems(["Heamo", "Raw"])
            setattr(self, f"comboSigType_{prefix}", comboType)
            headerLayout.addWidget(comboType)
            headerLayout.addSpacing(10)

        headerLayout.addWidget(QtWidgets.QLabel(f"Y轴缩放 ({unit}):"))
        spinYLim = QtWidgets.QDoubleSpinBox()
        
        spinYLim.setRange(1, 100000.0)
        spinYLim.setValue(10.0 if prefix == 'fnirs' else 100.0)
        spinYLim.setSingleStep(5.0)
        setattr(self, f"spinYLim_{prefix}", spinYLim)
        headerLayout.addWidget(spinYLim)

        layout.addLayout(headerLayout)

        # 2. 动态滤波工具条
        filterBar = self._create_filter_bar(prefix)
        setattr(self, f"filterBar_{prefix}", filterBar)
        filterBar.setVisible(False)
        layout.addWidget(filterBar)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setFrameShape(QtWidgets.QFrame.NoFrame)
        scrollArea.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        plotContainer = QtWidgets.QWidget()
        plotContainer.setStyleSheet("background-color: transparent;")
        plotLayout = QtWidgets.QVBoxLayout(plotContainer)
        plotLayout.setContentsMargins(0, 0, 0, 0)
        setattr(self, f"plotLayout_{prefix}", plotLayout)
        
        scrollArea.setWidget(plotContainer)
        layout.addWidget(scrollArea, stretch=1)
        
        return panel
        
    def _create_filter_bar(self, prefix):
        frame = QtWidgets.QFrame()
        frame.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 4px; }")
        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        
        comboType = QtWidgets.QComboBox()
        comboType.addItems(["带通滤波", "低通滤波", "高通滤波", "平滑滤波(S-G)"])
        setattr(self, f"comboType_{prefix}", comboType)
        layout.addWidget(comboType)
        
        lblFreq1 = QtWidgets.QLabel("下限:")
        spinFreq1 = QtWidgets.QDoubleSpinBox()
        spinFreq1.setSuffix(" Hz")
        setattr(self, f"lblFreq1_{prefix}", lblFreq1)
        setattr(self, f"spinFreq1_{prefix}", spinFreq1)
        layout.addWidget(lblFreq1)
        layout.addWidget(spinFreq1)
        
        lblFreq2 = QtWidgets.QLabel("上限:")
        spinFreq2 = QtWidgets.QDoubleSpinBox()
        spinFreq2.setSuffix(" Hz")
        setattr(self, f"lblFreq2_{prefix}", lblFreq2)
        setattr(self, f"spinFreq2_{prefix}", spinFreq2)
        layout.addWidget(lblFreq2)
        layout.addWidget(spinFreq2)
        
        lblOrder = QtWidgets.QLabel("阶数:")
        spinOrder = QtWidgets.QSpinBox()
        spinOrder.setRange(1, 101)
        setattr(self, f"lblOrder_{prefix}", lblOrder)
        setattr(self, f"spinOrder_{prefix}", spinOrder)
        layout.addWidget(lblOrder)
        layout.addWidget(spinOrder)
        
        btnApply = QtWidgets.QPushButton("应用")
        btnApply.setStyleSheet("background-color: #7f8c8d; color: white; border-radius: 3px; padding: 2px 10px;")
        setattr(self, f"btnApply_{prefix}", btnApply)
        layout.addWidget(btnApply)
        
        layout.addStretch()
        return frame
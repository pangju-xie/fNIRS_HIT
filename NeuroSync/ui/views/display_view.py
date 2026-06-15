from PyQt5 import QtCore, QtWidgets


class TrimmedDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def textFromValue(self, value):
        text = f"{value:.12f}".rstrip("0").rstrip(".")
        return text or "0"


class DisplayViewWidget(object):
    """Realtime acquisition and display UI."""

    def setupUi(self, Form):
        Form.setObjectName("DisplayForm")
        self.mainLayout = QtWidgets.QVBoxLayout(Form)
        self.mainLayout.setContentsMargins(5, 5, 5, 5)
        self.mainLayout.setSpacing(5)

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

        self.mainSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        self.fnirsPanel = self._create_signal_panel("近红外", "fnirs", "mV", has_signal_type=True)
        self.mainSplitter.addWidget(self.fnirsPanel)

        self.rightSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.eegPanel = self._create_signal_panel("脑电", "eeg", "uV", has_signal_type=False)
        self.semgPanel = self._create_signal_panel("肌电", "semg", "mV", has_signal_type=False)

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

        headerLayout = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("font-size: 14px; color: #2c3e50;")
        headerLayout.addWidget(title_label)
        headerLayout.addStretch()

        chkEnable = QtWidgets.QCheckBox("启用滤波")
        setattr(self, f"chkEnable_{prefix}", chkEnable)
        headerLayout.addWidget(chkEnable)
        headerLayout.addSpacing(10)

        if has_signal_type:
            headerLayout.addWidget(QtWidgets.QLabel("信号"))
            comboType = QtWidgets.QComboBox()
            comboType.addItems(["血氧", "原始"])
            setattr(self, f"comboSigType_{prefix}", comboType)
            headerLayout.addWidget(comboType)
            headerLayout.addSpacing(10)

        lblYLim = QtWidgets.QLabel(f"纵轴范围 ({unit})：")
        setattr(self, f"lblYLim_{prefix}", lblYLim)
        headerLayout.addWidget(lblYLim)

        spinYLim = TrimmedDoubleSpinBox()
        spinYLim.setDecimals(3)
        spinYLim.setRange(0.001, 1000000.0)
        setattr(self, f"spinYLim_{prefix}", spinYLim)
        headerLayout.addWidget(spinYLim)

        layout.addLayout(headerLayout)

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
        frame.setStyleSheet(
            "QFrame { background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 4px; }"
        )
        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)

        comboType = QtWidgets.QComboBox()
        comboType.addItems(["带通", "低通", "高通", "平滑 (S-G)"])
        setattr(self, f"comboType_{prefix}", comboType)
        layout.addWidget(comboType)

        lblFreq1 = QtWidgets.QLabel("低频：")
        spinFreq1 = QtWidgets.QDoubleSpinBox()
        spinFreq1.setSuffix(" Hz")
        spinFreq1.setRange(0.0, 100000.0)
        setattr(self, f"lblFreq1_{prefix}", lblFreq1)
        setattr(self, f"spinFreq1_{prefix}", spinFreq1)
        layout.addWidget(lblFreq1)
        layout.addWidget(spinFreq1)

        lblFreq2 = QtWidgets.QLabel("高频：")
        spinFreq2 = QtWidgets.QDoubleSpinBox()
        spinFreq2.setSuffix(" Hz")
        spinFreq2.setRange(0.0, 100000.0)
        setattr(self, f"lblFreq2_{prefix}", lblFreq2)
        setattr(self, f"spinFreq2_{prefix}", spinFreq2)
        layout.addWidget(lblFreq2)
        layout.addWidget(spinFreq2)

        lblOrder = QtWidgets.QLabel("阶数：")
        spinOrder = QtWidgets.QSpinBox()
        spinOrder.setRange(1, 101)
        setattr(self, f"lblOrder_{prefix}", lblOrder)
        setattr(self, f"spinOrder_{prefix}", spinOrder)
        layout.addWidget(lblOrder)
        layout.addWidget(spinOrder)

        btnApply = QtWidgets.QPushButton("应用")
        btnApply.setStyleSheet(
            "background-color: #7f8c8d; color: white; border-radius: 3px; padding: 2px 10px;"
        )
        setattr(self, f"btnApply_{prefix}", btnApply)
        layout.addWidget(btnApply)

        layout.addStretch()
        return frame

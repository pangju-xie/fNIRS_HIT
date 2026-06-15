from PyQt5 import QtCore, QtWidgets


class QualityViewWidget(object):
    """阻抗与信号质量评估纯 UI 布局"""

    def setupUi(self, Form):
        Form.setObjectName("QualityView")
        self.main_layout = QtWidgets.QVBoxLayout(Form)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        self.top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        self.left_widget = QtWidgets.QWidget()
        self.left_layout = QtWidgets.QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 0, 0, 0)

        self.brain_container = QtWidgets.QGroupBox()
        self.brain_layout = QtWidgets.QVBoxLayout(self.brain_container)
        self.left_layout.addWidget(self.brain_container, stretch=1)

        self.right_widget = QtWidgets.QWidget()
        self.right_layout = QtWidgets.QHBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)

        self.fnirs_group = QtWidgets.QGroupBox("fNIRS质量检测")
        self.fnirs_layout = QtWidgets.QVBoxLayout(self.fnirs_group)
        self.fnirs_layout.setContentsMargins(8, 8, 8, 8)
        self.fnirs_layout.setSpacing(6)
        self.fnirs_header = self._build_header(("通道", 110), ("强度", 96))
        self.fnirs_scroll = self._build_scroll_area()
        self.fnirs_layout.addLayout(self.fnirs_header)
        self.fnirs_layout.addWidget(self.fnirs_scroll)

        self.eeg_group = QtWidgets.QGroupBox("EEG阻抗检测")
        self.eeg_layout = QtWidgets.QVBoxLayout(self.eeg_group)
        self.eeg_layout.setContentsMargins(8, 8, 8, 8)
        self.eeg_layout.setSpacing(6)
        self.eeg_header = self._build_header(("通道", 110), ("阻抗", 96))
        self.eeg_scroll = self._build_scroll_area()
        self.eeg_layout.addLayout(self.eeg_header)
        self.eeg_layout.addWidget(self.eeg_scroll)

        self.right_layout.addWidget(self.fnirs_group, stretch=1)
        self.right_layout.addWidget(self.eeg_group, stretch=1)

        self.top_splitter.addWidget(self.left_widget)
        self.top_splitter.addWidget(self.right_widget)
        self.top_splitter.setSizes([620, 420])
        self.main_layout.addWidget(self.top_splitter, stretch=1)

        self.bottom_frame = QtWidgets.QFrame()
        self.bottom_frame.setObjectName("bottomControlBar")
        self.bottom_layout = QtWidgets.QHBoxLayout(self.bottom_frame)
        self.bottom_layout.setContentsMargins(8, 6, 8, 6)

        self.btn_start = QtWidgets.QPushButton("开始")
        self.btn_stop = QtWidgets.QPushButton("停止")
        self.btn_complete = QtWidgets.QPushButton("完成 >>")

        self.btn_start.setObjectName("btn_start")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_complete.setObjectName("btn_complete")
        self.btn_stop.setEnabled(False)

        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.btn_start)
        self.bottom_layout.addWidget(self.btn_stop)
        self.bottom_layout.addWidget(self.btn_complete)
        self.main_layout.addWidget(self.bottom_frame)

    def _build_header(self, *columns):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(10)
        for text, width in columns:
            lbl = QtWidgets.QLabel(text)
            lbl.setFixedWidth(width)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
        return layout

    def _build_scroll_area(self):
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        contents = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(contents)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(contents)
        scroll_area.content_widget = contents
        scroll_area.content_layout = layout
        return scroll_area

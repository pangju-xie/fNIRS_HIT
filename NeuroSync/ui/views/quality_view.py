from PyQt5 import QtCore, QtWidgets

class QualityViewWidget(object):
    """阻抗与信号质量评估纯 UI 布局"""
    def setupUi(self, Form):
        Form.setObjectName("QualityView")
        self.main_layout = QtWidgets.QVBoxLayout(Form)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # ==========================================
        # 上半部分：核心测试区 (左右分割)
        # ==========================================
        self.top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # --- 左侧：脑电拓扑图与 Color Bar ---
        self.left_widget = QtWidgets.QWidget()
        self.left_layout = QtWidgets.QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.brain_container = QtWidgets.QGroupBox()
        self.brain_layout = QtWidgets.QVBoxLayout(self.brain_container)
        self.left_layout.addWidget(self.brain_container, stretch=1)
        
        # # Color Bar 渐变色条
        # self.colorbar_layout = QtWidgets.QVBoxLayout()
        # self.colorbar_label = QtWidgets.QLabel()
        # self.colorbar_label.setFixedHeight(15)
        # self.colorbar_label.setStyleSheet("""
        #     background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
        #     stop:0 #F44336, stop:0.5 #FFC107, stop:1 #4CAF50);
        #     border-radius: 7px;
        # """)
        
        # self.scale_layout = QtWidgets.QHBoxLayout()
        # self.lbl_scale_min = QtWidgets.QLabel("Poor (0)")
        # self.lbl_scale_mid = QtWidgets.QLabel("Fair")
        # self.lbl_scale_max = QtWidgets.QLabel("Excellent")
        # self.lbl_scale_mid.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        # self.lbl_scale_max.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter) # type: ignore
        
        # self.scale_layout.addWidget(self.lbl_scale_min)
        # self.scale_layout.addWidget(self.lbl_scale_mid)
        # self.scale_layout.addWidget(self.lbl_scale_max)
        
        # self.colorbar_layout.addWidget(self.colorbar_label)
        # self.colorbar_layout.addLayout(self.scale_layout)
        # self.left_layout.addLayout(self.colorbar_layout)
        
        # --- 右侧：通道列表 ---
        self.right_widget = QtWidgets.QWidget()
        self.right_layout = QtWidgets.QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.list_container = QtWidgets.QGroupBox("阻抗强度")
        self.list_main_layout = QtWidgets.QVBoxLayout(self.list_container)
        
        self.header_layout = QtWidgets.QHBoxLayout()
        for text, width in [("模态", 60), ("通道", 80), ("强度", 80), ("质量", 80)]:
            lbl = QtWidgets.QLabel(text)
            lbl.setFixedWidth(width)
            self.header_layout.addWidget(lbl)
        self.header_layout.addStretch()
        
        self.scrollArea = QtWidgets.QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaLayout = QtWidgets.QVBoxLayout(self.scrollAreaWidgetContents)
        self.scrollAreaLayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        
        self.list_main_layout.addLayout(self.header_layout)
        self.list_main_layout.addWidget(self.scrollArea)
        self.right_layout.addWidget(self.list_container)
        
        self.top_splitter.addWidget(self.left_widget)
        self.top_splitter.addWidget(self.right_widget)
        self.top_splitter.setSizes([600, 400])
        self.main_layout.addWidget(self.top_splitter, stretch=1)

        # ==========================================
        # 下半部分：长条形控制工具条
        # ==========================================
        self.bottom_frame = QtWidgets.QFrame()
        self.bottom_frame.setObjectName("bottomControlBar")
        self.bottom_layout = QtWidgets.QHBoxLayout(self.bottom_frame)
        
        # self.combo_method = QtWidgets.QComboBox()
        # self.combo_method.addItems(["光电信号强度 (mV)", "头皮耦合指数 (SCI)"])
        # self.combo_method.setFixedWidth(200)
        
        # self.lbl_status = QtWidgets.QLabel("状态: 等待开始")
        # self.lbl_status.setStyleSheet("color: #666; font-weight: bold; border: none;")
        
        self.btn_start = QtWidgets.QPushButton("开始")
        self.btn_stop = QtWidgets.QPushButton("停止")
        self.btn_complete = QtWidgets.QPushButton("完成 >>")
        
        self.btn_start.setObjectName("btn_start")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_complete.setObjectName("btn_complete")

        self.btn_stop.setEnabled(False)

        # self.bottom_layout.addWidget(QtWidgets.QLabel(" fNIRS 评估标准:"))
        # self.bottom_layout.addWidget(self.combo_method)
        self.bottom_layout.addSpacing(20)
        # self.bottom_layout.addWidget(self.lbl_status)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.btn_start)
        self.bottom_layout.addWidget(self.btn_stop)
        self.bottom_layout.addWidget(self.btn_complete)
        
        self.main_layout.addWidget(self.bottom_frame)
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QFrame,
                             QGroupBox, QLabel, QLineEdit, QComboBox, QSpinBox,
                             QTextEdit, QPushButton, QListWidget, QSplitter, QListWidgetItem)
from PyQt5.QtCore import Qt, pyqtSignal, QTextStream
import logging

logger = logging.getLogger(__name__)

class UserViewWidget(QWidget):
    signal_save_clicked = pyqtSignal(dict)
    signal_clear_clicked = pyqtSignal()
    signal_search_changed = pyqtSignal(str)
    signal_patient_selected = pyqtSignal(str) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._wire_internal_signals()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ==========================================
        # 左侧：历史记录 (近10条)
        # ==========================================
        left_group = QGroupBox("最近就诊记录")
        left_layout = QVBoxLayout(left_group)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索姓名...")
        self.patient_list = QListWidget()
        left_layout.addWidget(self.search_input)
        left_layout.addWidget(self.patient_list)

        # ==========================================
        # 右侧：患者详细表单 (高紧凑度 & 防拉伸版)
        # ==========================================
        right_group = QGroupBox("用户信息登记")
        right_layout = QVBoxLayout(right_group)
        
        # 【1. 防拉伸容器】：限制最大宽度，防止高分辨率下无限拉宽
        form_container = QWidget()
        form_container.setMaximumWidth(800) 
        
        # 【2. 精准网格】：共 8 列，水平间距缩小，标签与输入框紧贴
        form_layout = QGridLayout(form_container)
        form_layout.setHorizontalSpacing(12) 
        form_layout.setVerticalSpacing(20)

        # --- 【第一行】：姓名、性别、年龄 ---
        lbl_name = QLabel("姓 名 <font color='red'>*</font>：")
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # type: ignore
        form_layout.addWidget(lbl_name, 0, 0)
        
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("至少2个字符")
        # 魔法跨列：让姓名输入框横跨 3 列，其右边缘将与第二行的“患病时间”完美对齐！
        form_layout.addWidget(self.input_name, 0, 1, 1, 3) 

        lbl_gender = QLabel("性 别：")
        lbl_gender.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # type: ignore
        form_layout.addWidget(lbl_gender, 0, 4)
        
        self.input_gender = QComboBox()
        self.input_gender.addItems(["男", "女"])
        form_layout.addWidget(self.input_gender, 0, 5)

        lbl_age = QLabel("年 龄 <font color='red'>*</font>：")
        lbl_age.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # type: ignore
        form_layout.addWidget(lbl_age, 0, 6)
        
        self.input_age = QSpinBox()
        self.input_age.setRange(0, 120)
        self.input_age.setSuffix(" 岁")
        form_layout.addWidget(self.input_age, 0, 7)

        # --- 【第二行】：疾病类型、患病时间、偏瘫侧、惯用手 ---
        lbl_stroke = QLabel("疾病类型：")
        lbl_stroke.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # type: ignore
        form_layout.addWidget(lbl_stroke, 1, 0)
        
        self.input_stroke = QComboBox()
        self.input_stroke.addItems(["健康", "缺血卒中", "出血卒中", "阿兹海默", "帕金森", "老年痴呆", "老年病", "其他"])
        form_layout.addWidget(self.input_stroke, 1, 1)

        lbl_duration = QLabel("患病时间：")
        lbl_duration.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # type: ignore
        form_layout.addWidget(lbl_duration, 1, 2)
        
        self.input_duration = QSpinBox()
        self.input_duration.setRange(0, 999)
        self.input_duration.setSuffix(" 个月")
        form_layout.addWidget(self.input_duration, 1, 3)

        lbl_paralysis = QLabel("偏瘫侧：")
        lbl_paralysis.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # type: ignore
        form_layout.addWidget(lbl_paralysis, 1, 4)
        
        self.input_paralysis = QComboBox()
        self.input_paralysis.addItems(["无", "左偏瘫", "右偏瘫"])
        form_layout.addWidget(self.input_paralysis, 1, 5)

        lbl_dominant = QLabel("惯用手：")
        lbl_dominant.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # type: ignore
        form_layout.addWidget(lbl_dominant, 1, 6)
        
        self.input_dominant = QComboBox()
        self.input_dominant.addItems(["右手", "左手", "双利手"])
        form_layout.addWidget(self.input_dominant, 1, 7)

        # --- 【第三行】：备注 (多行文本域) ---
        lbl_notes = QLabel("备 注：")
        lbl_notes.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop) # type: ignore # 顶对齐
        form_layout.addWidget(lbl_notes, 2, 0)
        
        self.input_notes = QTextEdit()
        self.input_notes.setPlaceholderText("选填：相关病史、禁忌症或备注说明...")
        self.input_notes.setMinimumHeight(65) # 强制显示为一块多行高度的文本域
        # self.input_notes.setMaximumHeight(90)
        form_layout.addWidget(self.input_notes, 2, 1, 1, 7)

        # 锁定列宽比例：偶数列(标签)不拉伸，奇数列(输入框)均匀拉伸
        for i in range(8):
            form_layout.setColumnStretch(i, 0 if i % 2 == 0 else 1)

        # 【3. 整体居中布局】：左右加弹簧，实现水平绝对居中
        center_form_layout = QHBoxLayout()
        center_form_layout.addStretch()
        center_form_layout.addWidget(form_container)
        center_form_layout.addStretch()

        right_layout.addStretch(1)
        right_layout.addLayout(center_form_layout)
        right_layout.addStretch(2)

        # ==========================================
        # 底部按钮区 (恢复早期的居中 + 包装框形式)
        # ==========================================
        self.bottom_frame = QFrame() 
        self.bottom_frame.setObjectName("bottomControlBar")
        btn_layout = QHBoxLayout(self.bottom_frame)
        btn_layout.setContentsMargins(15, 5, 15, 5)
        
        self.btn_save = QPushButton("确定 >>")
        self.btn_save.setObjectName("btnSave")
        self.btn_save.setEnabled(False) 

        self.btn_clear = QPushButton("取消")
        self.btn_clear.setObjectName("btnClear")

        # 按钮左右加弹簧，实现居中靠拢
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addStretch()
        
        right_layout.addWidget(self.bottom_frame)
        
        # 整体左右比例分割 (左边窄，右边宽)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_group)
        splitter.addWidget(right_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)

    def _wire_internal_signals(self):
        self.search_input.textChanged.connect(self.signal_search_changed.emit)
        self.btn_clear.clicked.connect(self.signal_clear_clicked.emit)
        self.patient_list.itemClicked.connect(lambda item: self.signal_patient_selected.emit(item.data(Qt.ItemDataRole.UserRole)))
        
        self.input_name.textChanged.connect(self._validate_form)
        self.input_age.valueChanged.connect(self._validate_form)
        self.btn_save.clicked.connect(self._on_save_clicked)

    def _validate_form(self):
        is_valid = len(self.input_name.text().strip()) >= 2 and self.input_age.value() > 0
        self.btn_save.setEnabled(is_valid)

    def _on_save_clicked(self):
        data = {
            "name": self.input_name.text().strip(),
            "gender": self.input_gender.currentText(),
            "age": self.input_age.value(),
            "stroke_type": self.input_stroke.currentText(),
            "duration": self.input_duration.value(),
            "paralysis": self.input_paralysis.currentText(),
            "dominant_hand": self.input_dominant.currentText(),
            "notes": self.input_notes.toPlainText().strip()
        }
        self.signal_save_clicked.emit(data)

    def update_patient_list(self, patient_info_list):
        self.patient_list.clear()
        for display_text, pid in patient_info_list:
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, pid) 
            self.patient_list.addItem(item)

    def set_form_data(self, data: dict):
        self.input_name.setText(data.get("name", ""))
        self.input_gender.setCurrentText(data.get("gender", "男"))
        self.input_age.setValue(int(data.get("age", 0)))
        self.input_stroke.setCurrentText(data.get("stroke_type", "无卒中"))
        self.input_duration.setValue(int(data.get("duration", 0)))
        self.input_paralysis.setCurrentText(data.get("paralysis", "无"))
        self.input_dominant.setCurrentText(data.get("dominant_hand", "右手"))
        self.input_notes.setText(data.get("notes", ""))
        self._validate_form()

    def clear_form(self):
        self.input_name.clear()
        self.input_gender.setCurrentIndex(0)
        self.input_age.setValue(0)
        self.input_stroke.setCurrentIndex(0)
        self.input_duration.setValue(0)
        self.input_paralysis.setCurrentIndex(0)
        self.input_dominant.setCurrentIndex(0)
        self.input_notes.clear()
        self.patient_list.clearSelection()
        self._validate_form()
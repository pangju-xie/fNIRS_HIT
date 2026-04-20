# core/widget_manager/user.py
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import pyqtSignal
import logging
import os, sys
from pathlib import Path
from datetime import datetime

from ui.views.user_view import UserViewWidget
from utils.subjects import PatientData, PatientDatabase
from utils.paths import DB_DIR

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

logger = logging.getLogger(__name__)

class UserInfoManager(UserViewWidget):
    # 【核心改变】：现在直接把 PatientData 对象发射给 Controller
    onUserSet = pyqtSignal(object)     
    patientChanged = pyqtSignal()   

    def __init__(self):
        super().__init__()
        data_directory = Path(DB_DIR)
        self.db = PatientDatabase(os.path.join(os.path.abspath(data_directory), "患者信息列表.csv"))
        
        self.current_editing_pid = None # 用于追踪当前表单是在编辑谁
        
        self._wire_signals()
        self._refresh_list() 

    # def _get_template_directory(self) -> Path:
    #     project_root = Path(__file__).resolve().parent.parent.parent
    #     template_dir = project_root / "template" / "用户信息"
    #     template_dir.mkdir(parents=True, exist_ok=True)
    #     return template_dir
    
    def _wire_signals(self):
        self.signal_save_clicked.connect(self._handle_save)
        self.signal_clear_clicked.connect(self._handle_clear)
        self.signal_search_changed.connect(self._refresh_list)
        self.signal_patient_selected.connect(self._load_patient)

    def _refresh_list(self, keyword=""):
        patients = self.db.search(keyword)
        # 【性能优化】：切片操作，无论库里多少人，UI永远只渲染最近的 10 个！
        recent_10 = patients[:10]
        display_list = [(f"{p.name} | {p.gender} | {p.age}岁", p.pid) for p in recent_10]
        self.update_patient_list(display_list)

    def _handle_clear(self):
        self.current_editing_pid = None
        self.clear_form()

    def _load_patient(self, pid: str):
        p = self.db.patients.get(pid)
        if p:
            self.current_editing_pid = p.pid # 锁定当前编辑的 PID
            self.set_form_data({
                "name": p.name, "gender": p.gender, "age": p.age,
                "stroke_type": p.stroke_type, "duration": p.duration,
                "paralysis": p.paralysis, "dominant_hand": p.dominant_hand, "notes": p.notes
            })

    def _handle_save(self, data: dict):
        patient_to_save = None
        
        # 1. 如果是从左侧列表点过来的复诊患者，直接更新，不查重
        if self.current_editing_pid and self.current_editing_pid in self.db.patients:
            patient_to_save = self.db.patients[self.current_editing_pid]
            # 更新可变的临床信息
            patient_to_save.stroke_type = data["stroke_type"]
            patient_to_save.duration = data["duration"]
            patient_to_save.paralysis = data["paralysis"]
            patient_to_save.dominant_hand = data["dominant_hand"]
            patient_to_save.notes = data["notes"]
            patient_to_save.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        else:
            # 2. 如果是纯手动输入的新患者，进行【智能防撞查重】
            existing = [p for p in self.db.patients.values() 
                        if p.name == data["name"] and p.gender == data["gender"] and p.age == data["age"]]
            
            if existing:
                reply = QMessageBox.question(
                    self, "发现相似档案", 
                    f"库中已有【{data['name']} ({data['gender']}, {data['age']}岁)】。\n"
                    "是否作为复诊直接【更新原档案】？\n(选 No 则创建同名同龄的全新档案)",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    patient_to_save = existing[0] # 使用老的 PID
                    patient_to_save.stroke_type = data["stroke_type"]
                    patient_to_save.duration = data["duration"]
                    patient_to_save.paralysis = data["paralysis"]
                    patient_to_save.dominant_hand = data["dominant_hand"]
                    patient_to_save.notes = data["notes"]
                    patient_to_save.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    patient_to_save = PatientData(**data) # 生成全新 PID
            else:
                patient_to_save = PatientData(**data) # 完全的新人，生成全新 PID

        # 3. 落盘数据库
        self.db.add_or_update(patient_to_save)
        self.current_editing_pid = patient_to_save.pid
        self._refresh_list(self.search_input.text())
        
        # 4. 通知上层系统，传递整个 PatientData 实体
        self.onUserSet.emit(patient_to_save)
        self.patientChanged.emit()
        
        # 锁定界面防止手抖修改
        self.input_name.setEnabled(False)
        self.input_gender.setEnabled(False)
        self.input_age.setEnabled(False)
        self.btn_save.setText("已锁定")
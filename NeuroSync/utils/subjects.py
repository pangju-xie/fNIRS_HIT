# models/subjects.py
import os
import csv
import uuid
import logging
from datetime import datetime
from pypinyin import pinyin, Style

logger = logging.getLogger(__name__)

class PatientData:
    def __init__(self, pid="", name="", gender="男", age=0, stroke_type="无卒中", 
                 duration=0, paralysis="无", dominant_hand="右手", notes="", updated_at=""):
        # 如果没有传入 pid，则自动生成一个 6 位的简短唯一码 (如 PID-A8F2B1)
        self.pid = pid if pid else f"PID-{uuid.uuid4().hex[:6].upper()}"
        self.name = name
        self.gender = gender
        self.age = int(age)
        self.stroke_type = stroke_type
        self.duration = int(duration)
        self.paralysis = paralysis
        self.dominant_hand = dominant_hand
        self.notes = notes
        self.updated_at = updated_at if updated_at else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_dir_prefix(self) -> str:
        """目录名称：姓名缩写 + PID (例如: ZS_PID-A8F2B1)，保证不同人绝对不混淆"""
        initials = ''.join([i[0].upper() for i in pinyin(self.name, style=Style.FIRST_LETTER) if i])
        return f"{initials}_{self.pid}"

    def get_file_prefix_base(self) -> str:
        """文件名称基础：仅姓名缩写 (例如: ZS)，Controller 会在后面加时间戳"""
        initials = ''.join([i[0].upper() for i in pinyin(self.name, style=Style.FIRST_LETTER) if i])
        return initials

    def to_dict(self):
        return {
            "PID": self.pid, "姓名": self.name, "性别": self.gender, "年龄": self.age,
            "疾病类型": self.stroke_type, "患病时间(月)": self.duration,
            "偏瘫侧": self.paralysis, "惯用手": self.dominant_hand, 
            "备注": self.notes, "最后访问": self.updated_at
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            pid=d.get("PID", ""), name=d.get("姓名", ""), gender=d.get("性别", "男"), 
            age=d.get("年龄", 0), stroke_type=d.get("疾病类型", "无卒中"), 
            duration=d.get("患病时间(月)", 0), paralysis=d.get("偏瘫侧", "无"), 
            dominant_hand=d.get("惯用手", "右手"), notes=d.get("备注", ""), 
            updated_at=d.get("最后访问", "")
        )

class PatientDatabase:
    """专职 CSV 读写管家"""
    def __init__(self, filepath):
        self.filepath = filepath
        self.patients = {} # pid -> PatientData
        self._ensure_file()
        self.load_all()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["PID", "姓名", "性别", "年龄", "疾病类型", "患病时间(月)", "偏瘫侧", "惯用手", "备注", "最后访问"])

    def load_all(self):
        self.patients.clear()
        if not os.path.exists(self.filepath): return
        with open(self.filepath, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                p = PatientData.from_dict(row)
                self.patients[p.pid] = p

    def save_all(self):
        with open(self.filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=["PID", "姓名", "性别", "年龄", "疾病类型", "患病时间(月)", "偏瘫侧", "惯用手", "备注", "最后访问"])
            writer.writeheader()
            for p in self.patients.values():
                writer.writerow(p.to_dict())

    def add_or_update(self, patient: PatientData):
        self.patients[patient.pid] = patient
        self.save_all()

    def search(self, keyword=""):
        results = []
        kw = keyword.lower()
        for p in self.patients.values():
            if kw in p.name.lower() or kw in p.pid.lower():
                results.append(p)
        # 按最后访问时间降序排序
        results.sort(key=lambda x: x.updated_at, reverse=True)
        return results
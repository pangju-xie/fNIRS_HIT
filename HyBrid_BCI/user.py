# -*- coding: utf-8 -*-

"""
Patient Information Management System
Main application file with business logic and data handling

Features:
- Patient data collection and validation
- CSV file storage with user existence checking
- Form validation and error handling
- User-friendly interface with proper feedback
- Data export capabilities
- Duplicate user detection and handling

Author: Generated for PyQt5 Patient Management System
Date: 2025
"""

import sys
import csv
import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, List
from pypinyin import pinyin, Style
from PyQt5 import QtWidgets, QtCore, QtGui
from ui_user import Ui_UserInfoForm
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PatientData:
    """Data class for patient information"""
    
    def __init__(self):
        self.name: str = ""
        self.gender: str = "男"
        self.age: int = 0
        self.stroke_type: str = "无卒中"
        self.duration_months: int = 0
        self.paralysis_side: str = "无"
        self.additional_notes: str = ""
        self.updated_at: str = ""
        self.initials: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert patient data to dictionary"""
        return {
            "姓名": self.name,
            "性别": self.gender,
            "年龄": self.age,
            "卒中类型": self.stroke_type,
            "卒中时长": self.duration_months,
            "瘫痪侧": self.paralysis_side,
            "其他信息": self.additional_notes,
            "修改时间": self.updated_at,
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """Load patient data from dictionary"""
        self.name = data.get("姓名", "")
        self.gender = data.get("性别", "男")
        self.age = data.get("年龄", 0)
        self.stroke_type = data.get("卒中类型", "无卒中")
        self.duration_months = data.get("卒中时长", 0)
        self.paralysis_side = data.get("瘫痪侧", "无")
        self.additional_notes = data.get("其他信息", "")
        self.updated_at = data.get("修改时间", "")
    
    def to_csv_row(self) -> List[str]:
        """Convert patient data to CSV row"""
        return [
            self.name,
            self.gender,
            str(self.age),
            self.stroke_type,
            str(self.duration_months),
            self.paralysis_side,
            self.additional_notes,
            self.updated_at
        ]
    
    def getNameInitials(self) -> str:
        """Get initials from name"""
         # 获取每个字的拼音首字母（小写）
        initials_list = pinyin(self.name, style=Style.FIRST_LETTER)
        # 将每个首字母大写并连接成一个字符串
        self.initials = ''.join([i[0].upper() for i in initials_list if i]) + '_' + str(self.age) # 确保列表不为空
        logger.info(f"Generated initials for {self.name}: {self.initials}")
        return self.initials
    
    @staticmethod
    def get_csv_headers() -> List[str]:
        """Get CSV headers"""
        return [
            "姓名", "性别", "年龄", "卒中类型", "卒中时长",
            "瘫痪侧", "其他信息", "修改时间"
        ]


class CSVManager:
    """Manager class for CSV operations"""
    
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path
        self.ensure_csv_file()
    
    def ensure_csv_file(self):
        """Ensure CSV file exists with proper headers"""
        if not os.path.exists(self.csv_file_path):
            try:
                with open(self.csv_file_path, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(PatientData.get_csv_headers())
                print(f"Created new CSV file: {self.csv_file_path}")
            except Exception as e:
                print(f"Error creating CSV file: {e}")
                raise
    
    def user_exists(self, name: str) -> bool:
        """Check if user exists in CSV file"""
        try:
            if not os.path.exists(self.csv_file_path):
                return False
            
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['姓名'].strip().lower() == name.strip().lower():
                        return True
            return False
        except Exception as e:
            print(f"Error checking user existence: {e}")
            return False
    
    def get_user_data(self, name: str) -> Optional[PatientData]:
        """Get existing user data from CSV"""
        try:
            if not os.path.exists(self.csv_file_path):
                return None
            
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['姓名'].strip().lower() == name.strip().lower():
                        patient = PatientData()
                        # Convert age and duration to int
                        row['年龄'] = int(row['年龄']) if row['年龄'] else 0
                        row['卒中时长'] = int(row['卒中时长']) if row['卒中时长'] else 0
                        patient.from_dict(row)
                        return patient
            return None
        except Exception as e:
            print(f"Error getting user data: {e}")
            return None
    
    def add_patient(self, patient: PatientData) -> bool:
        """Add new patient to CSV file"""
        try:
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(patient.to_csv_row())
            return True
        except Exception as e:
            print(f"Error adding patient: {e}")
            return False
    
    def update_patient(self, patient: PatientData) -> bool:
        """Update existing patient in CSV file"""
        try:
            # Read all data
            rows = []
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                headers = reader.fieldnames
                for row in reader:
                    if row['姓名'].strip().lower() == patient.name.strip().lower():
                        # Update the row
                        updated_row = patient.to_dict()
                        rows.append(updated_row)
                    else:
                        rows.append(row)
            
            # Write back all data
            with open(self.csv_file_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
            
            return True
        except Exception as e:
            print(f"Error updating patient: {e}")
            return False
    
    def get_all_patients(self) -> List[PatientData]:
        """Get all patients from CSV file"""
        patients = []
        try:
            if not os.path.exists(self.csv_file_path):
                return patients
            
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    patient = PatientData()
                    # Convert numeric fields
                    row['年龄'] = int(row['年龄']) if row['年龄'] else 0
                    row['卒中时长'] = int(row['卒中时长']) if row['卒中时长'] else 0
                    patient.from_dict(row)
                    patients.append(patient)
        except Exception as e:
            print(f"Error getting all patients: {e}")
        
        return patients


class UserInfoManager(QtWidgets.QWidget):
    """Main application class for patient information management"""
    onUserSet = QtCore.pyqtSignal(str)  # Signal emitted when a user is set with initials
    
    def __init__(self, data_directory: str = "./用户信息"):
        super().__init__()
        self.ui = Ui_UserInfoForm()
        self.ui.setupUi(self)
        
        # Initialize data directory
        self.data_directory = os.path.abspath(data_directory)
        self.ensure_data_directory()
        
        # Initialize CSV manager
        csv_file_path = os.path.join(self.data_directory, "患者信息.csv")
        self.csv_manager = CSVManager(csv_file_path)
        
        # Current patient data
        self.current_patient = PatientData()
        
        # Setup UI connections
        self.setup_connections()
        
        # Initialize form
        self.clear_form()
        
        # Set window properties
        self.center_window()
    
    def ensure_data_directory(self):
        """Ensure the data directory exists"""
        try:
            os.makedirs(self.data_directory, exist_ok=True)
            print(f"Data directory: {self.data_directory}")
        except OSError as e:
            QtWidgets.QMessageBox.critical(
                self, "错误", f"无法创建数据目录：{str(e)}"
            )
    
    def setup_connections(self):
        """Connect UI signals to slots"""
        # Button connections
        self.ui.saveButton.clicked.connect(self.save_patient_data)
        self.ui.clearButton.clicked.connect(self.clear_form)
        self.ui.cancelButton.clicked.connect(self.close)
        
        # Form validation connections
        self.ui.nameLineEdit.textChanged.connect(lambda: self.validate_form())
        self.ui.ageSpinBox.valueChanged.connect(lambda: self.validate_form())
        
        # Auto-update timestamp when form changes
        self.ui.nameLineEdit.textChanged.connect(self.mark_form_modified)
        self.ui.genderComboBox.currentTextChanged.connect(self.mark_form_modified)
        self.ui.ageSpinBox.valueChanged.connect(self.mark_form_modified)
        self.ui.strokeTypeComboBox.currentTextChanged.connect(self.mark_form_modified)
        self.ui.durationSpinBox.valueChanged.connect(self.mark_form_modified)
        self.ui.paralysisSideComboBox.currentTextChanged.connect(self.mark_form_modified)
        self.ui.notesTextEdit.textChanged.connect(self.mark_form_modified)
        
        # Add name field change event for user checking
        self.ui.nameLineEdit.editingFinished.connect(self.check_existing_user)
    
    def center_window(self):
        """Center the window on screen"""
        screen = QtWidgets.QApplication.desktop().screenGeometry()
        window = self.geometry()
        self.move(
            (screen.width() - window.width()) // 2,
            (screen.height() - window.height()) // 2
        )
    
    def validate_form(self) -> None:
        """Validate form input and enable/disable save button"""
        try:
            name = self.ui.nameLineEdit.text().strip()
            age = self.ui.ageSpinBox.value()
            
            is_valid = len(name) >= 2 and age > 0
            
            self.ui.saveButton.setEnabled(is_valid)
            
            # Visual feedback for name field
            if len(name) < 2 and len(name) > 0:
                self.ui.nameLineEdit.setStyleSheet("border: 2px solid #e74c3c;")
            else:
                self.ui.nameLineEdit.setStyleSheet("")
                
        except AttributeError as e:
            print(f"UI element not found during validation: {e}")
    
    def is_form_valid(self) -> bool:
        """Check if form is valid"""
        try:
            name = self.ui.nameLineEdit.text().strip()
            age = self.ui.ageSpinBox.value()
            return len(name) >= 2 and age > 0
        except AttributeError:
            return False
    
    def mark_form_modified(self) -> None:
        """Mark form as modified"""
        self.current_patient.updated_at = datetime.now().isoformat()
    
    def check_existing_user(self) -> None:
        """Check if user exists and load data if found"""
        name = self.ui.nameLineEdit.text().strip()
        if len(name) < 2:
            return
        
        if self.csv_manager.user_exists(name):
            # User exists, ask what to do
            existing_patient = self.csv_manager.get_user_data(name)
            if existing_patient:
                reply = QtWidgets.QMessageBox.question(
                    self, "用户已存在", 
                    f"用户 '{name}' 已存在。\n\n"
                    f"现有信息：\n"
                    f"性别: {existing_patient.gender}\n"
                    f"年龄: {existing_patient.age}\n"
                    f"卒中类型: {existing_patient.stroke_type}\n\n"
                    f"是否要加载现有用户信息进行编辑？",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes
                )
                
                if reply == QtWidgets.QMessageBox.Yes:
                    self.populate_form(existing_patient)
                    # Change save button text to indicate update
                    self.ui.saveButton.setText("设置")
                else:
                    # Clear other fields but keep the name
                    current_name = self.ui.nameLineEdit.text()
                    self.clear_form()
                    self.ui.nameLineEdit.setText(current_name)
                    self.ui.saveButton.setText("设置")
        else:
            # New user
            self.ui.saveButton.setText("设置")
            onUserSet.emit(self.current_patient.initials)
    
    def collect_form_data(self) -> PatientData:
        """Collect data from form fields"""
        patient = PatientData()
        
        try:
            patient.name = self.ui.nameLineEdit.text().strip()
            patient.gender = self.ui.genderComboBox.currentText()
            patient.age = self.ui.ageSpinBox.value()
            patient.stroke_type = self.ui.strokeTypeComboBox.currentText()
            patient.duration_months = self.ui.durationSpinBox.value()
            patient.paralysis_side = self.ui.paralysisSideComboBox.currentText()
            patient.additional_notes = self.ui.notesTextEdit.toPlainText().strip()
            
            # Set timestamps
            current_time = datetime.now().isoformat()
            patient.updated_at = current_time
                
        except AttributeError as e:
            print(f"Error collecting form data: {e}")
            QtWidgets.QMessageBox.warning(
                self, "错误", f"读取表单数据时发生错误：{str(e)}"
            )
        
        return patient
    
    def populate_form(self, patient: PatientData) -> None:
        """Populate form with patient data"""
        self.ui.nameLineEdit.setText(patient.name)
        
        # Set gender
        gender_index = self.ui.genderComboBox.findText(patient.gender)
        if gender_index >= 0:
            self.ui.genderComboBox.setCurrentIndex(gender_index)
        
        self.ui.ageSpinBox.setValue(patient.age)
        
        # Set stroke type
        stroke_index = self.ui.strokeTypeComboBox.findText(patient.stroke_type)
        if stroke_index >= 0:
            self.ui.strokeTypeComboBox.setCurrentIndex(stroke_index)
        
        self.ui.durationSpinBox.setValue(patient.duration_months)
        
        # Set paralysis side
        paralysis_index = self.ui.paralysisSideComboBox.findText(patient.paralysis_side)
        if paralysis_index >= 0:
            self.ui.paralysisSideComboBox.setCurrentIndex(paralysis_index)
        
        self.ui.notesTextEdit.setPlainText(patient.additional_notes)
        
        self.current_patient = patient
    
    def clear_form(self) -> None:
        """Clear all form fields"""
        self.ui.nameLineEdit.clear()
        self.ui.genderComboBox.setCurrentIndex(0)
        self.ui.ageSpinBox.setValue(0)
        self.ui.strokeTypeComboBox.setCurrentIndex(2)  # Default to "无卒中"
        self.ui.durationSpinBox.setValue(0)
        self.ui.paralysisSideComboBox.setCurrentIndex(2)  # Default to "无"
        self.ui.notesTextEdit.clear()
        
        # Reset styling
        self.ui.nameLineEdit.setStyleSheet("")
        
        # Reset current patient
        self.current_patient = PatientData()
        
        # Reset button text
        self.ui.saveButton.setText("设置")
        
        # Validate form
        self.validate_form()
    
    def save_patient_data(self) -> None:
        """Save patient data to CSV file"""
        if not self.is_form_valid():
            QtWidgets.QMessageBox.warning(
                self, "验证失败", "请检查输入的信息是否完整和正确。"
            )
            return
        
        try:
            # Collect form data
            patient = self.collect_form_data()
            
            # Check if user exists
            user_exists = self.csv_manager.user_exists(patient.name)
            
            if user_exists:
                # Ask user if they want to update or abandon
                reply = QtWidgets.QMessageBox.question(
                    self, "用户已存在", 
                    f"用户 '{patient.name}' 已存在。\n\n"
                    f"选择操作：\n"
                    f"是 - 更新现有用户信息\n"
                    f"否 - 放弃保存",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes
                )
                
                if reply == QtWidgets.QMessageBox.Yes:
                    # Update existing user
                    # Preserve created_at from existing record
                    existing_patient = self.csv_manager.get_user_data(patient.name)
                    
                    success = self.csv_manager.update_patient(patient)
                    if success:
                        QtWidgets.QMessageBox.information(
                            self, "更新成功", 
                            f"用户 '{patient.name}' 的信息已成功更新！"
                        )
                        print(f"Updated patient: {patient.name}")
                    else:
                        QtWidgets.QMessageBox.critical(
                            self, "更新失败", "更新用户信息时发生错误！"
                        )
                        return
                else:
                    # User chose to abandon
                    QtWidgets.QMessageBox.information(
                        self, "操作取消", "保存操作已取消。"
                    )
                    return
            else:
                # Add new user
                success = self.csv_manager.add_patient(patient)
                if success:
                    QtWidgets.QMessageBox.information(
                        self, "保存成功", 
                        f"新用户 '{patient.name}' 的信息已成功保存！"
                    )
                    print(f"Added new patient: {patient.name}")
                else:
                    QtWidgets.QMessageBox.critical(
                        self, "保存失败", "保存用户信息时发生错误！"
                    )
                    return
            
            # offer a file name to save data
            self.current_patient.getNameInitials()
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "操作失败", f"保存患者信息时发生错误：\n{str(e)}"
            )
            print(f"Error saving patient data: {str(e)}")
    
    def closeEvent(self, event) -> None:
        """Handle window close event"""
        # Check if form has unsaved changes
        current_data = self.collect_form_data()
        if (current_data.name.strip() or current_data.age > 0 or 
            current_data.additional_notes.strip()):
            
            reply = QtWidgets.QMessageBox.question(
                self, "确认退出", 
                "表单中有未保存的数据，确定要退出吗？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.No:
                event.ignore()
                return
        
        event.accept()


def main():
    """Main function to run the application"""
    # Create application
    app = QtWidgets.QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("患者信息管理系统")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Medical Information Systems")
    
    # Create and show main window
    window = UserInfoManager()
    window.show()
    
    # Run application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
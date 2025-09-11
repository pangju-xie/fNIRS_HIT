# -*- coding: utf-8 -*-

"""
Optimized UI file for Patient Information Management System
Generated from user.ui using PyQt5 UI code generator

Improvements:
- Better layout management using QGridLayout and QVBoxLayout
- Improved styling with CSS-like properties
- Better widget organization and naming conventions
- Enhanced user experience with placeholders and proper sizing
- Responsive design with proper spacing and margins
"""

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_UserInfoForm(object):
    def setupUi(self, UserInfoForm):
        UserInfoForm.setObjectName("UserInfoForm")
        UserInfoForm.resize(800, 500)
        UserInfoForm.setWindowTitle("患者信息管理系统")
        UserInfoForm.setMinimumSize(QtCore.QSize(800, 500))
        
        # Main layout
        self.mainLayout = QtWidgets.QVBoxLayout(UserInfoForm)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setObjectName("mainLayout")
        
        # Title label
        self.titleLabel = QtWidgets.QLabel(UserInfoForm)
        self.titleLabel.setObjectName("titleLabel")
        self.titleLabel.setText("用户信息")
        self.titleLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setStyleSheet(
            "QLabel { font-size: 18px; font-weight: bold; color: #2c3e50; padding: 10px; }"
        )
        self.mainLayout.addWidget(self.titleLabel)
        
        # Patient info group box
        self.patientInfoGroup = QtWidgets.QGroupBox(UserInfoForm)
        self.patientInfoGroup.setObjectName("patientInfoGroup")
        self.patientInfoGroup.setTitle("基本信息")
        self.patientInfoGroup.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 14px; }"
        )
        
        # Grid layout for form fields
        self.infoGridLayout = QtWidgets.QGridLayout(self.patientInfoGroup)
        self.infoGridLayout.setHorizontalSpacing(20)
        self.infoGridLayout.setVerticalSpacing(15)
        self.infoGridLayout.setObjectName("infoGridLayout")
        
        # Row 1: Name and Gender
        self.nameLabel = QtWidgets.QLabel(self.patientInfoGroup)
        self.nameLabel.setObjectName("nameLabel")
        self.nameLabel.setText("姓名：")
        self.nameLabel.setMinimumWidth(80)
        self.infoGridLayout.addWidget(self.nameLabel, 0, 0)
        
        self.nameLineEdit = QtWidgets.QLineEdit(self.patientInfoGroup)
        self.nameLineEdit.setObjectName("nameLineEdit")
        self.nameLineEdit.setPlaceholderText("请输入患者姓名")
        self.nameLineEdit.setMinimumWidth(150)
        self.infoGridLayout.addWidget(self.nameLineEdit, 0, 1)
        
        self.genderLabel = QtWidgets.QLabel(self.patientInfoGroup)
        self.genderLabel.setObjectName("genderLabel")
        self.genderLabel.setText("性别：")
        self.genderLabel.setMinimumWidth(80)
        self.infoGridLayout.addWidget(self.genderLabel, 0, 2)
        
        self.genderComboBox = QtWidgets.QComboBox(self.patientInfoGroup)
        self.genderComboBox.setObjectName("genderComboBox")
        self.genderComboBox.setMinimumWidth(100)
        self.genderComboBox.addItem("男")
        self.genderComboBox.addItem("女")
        self.infoGridLayout.addWidget(self.genderComboBox, 0, 3)
        
        # Row 2: Age and Stroke Type
        self.ageLabel = QtWidgets.QLabel(self.patientInfoGroup)
        self.ageLabel.setObjectName("ageLabel")
        self.ageLabel.setText("年龄：")
        self.infoGridLayout.addWidget(self.ageLabel, 1, 0)
        
        self.ageSpinBox = QtWidgets.QSpinBox(self.patientInfoGroup)
        self.ageSpinBox.setObjectName("ageSpinBox")
        self.ageSpinBox.setMinimum(0)
        self.ageSpinBox.setMaximum(150)
        self.ageSpinBox.setSuffix(" 岁")
        self.ageSpinBox.setMinimumWidth(100)
        self.infoGridLayout.addWidget(self.ageSpinBox, 1, 1)
        
        self.strokeTypeLabel = QtWidgets.QLabel(self.patientInfoGroup)
        self.strokeTypeLabel.setObjectName("strokeTypeLabel")
        self.strokeTypeLabel.setText("卒中类型：")
        self.infoGridLayout.addWidget(self.strokeTypeLabel, 1, 2)
        
        self.strokeTypeComboBox = QtWidgets.QComboBox(self.patientInfoGroup)
        self.strokeTypeComboBox.setObjectName("strokeTypeComboBox")
        self.strokeTypeComboBox.setMinimumWidth(120)
        self.strokeTypeComboBox.addItem("出血型")
        self.strokeTypeComboBox.addItem("缺血型")
        self.strokeTypeComboBox.addItem("无卒中")
        self.infoGridLayout.addWidget(self.strokeTypeComboBox, 1, 3)
        
        # Row 3: Duration and Paralysis Side
        self.durationLabel = QtWidgets.QLabel(self.patientInfoGroup)
        self.durationLabel.setObjectName("durationLabel")
        self.durationLabel.setText("卒中时长：")
        self.infoGridLayout.addWidget(self.durationLabel, 2, 0)
        
        self.durationSpinBox = QtWidgets.QSpinBox(self.patientInfoGroup)
        self.durationSpinBox.setObjectName("durationSpinBox")
        self.durationSpinBox.setMinimum(0)
        self.durationSpinBox.setMaximum(999)
        self.durationSpinBox.setSuffix(" 个月")
        self.durationSpinBox.setMinimumWidth(100)
        self.infoGridLayout.addWidget(self.durationSpinBox, 2, 1)
        
        self.paralysisSideLabel = QtWidgets.QLabel(self.patientInfoGroup)
        self.paralysisSideLabel.setObjectName("paralysisSideLabel")
        self.paralysisSideLabel.setText("偏瘫侧：")
        self.infoGridLayout.addWidget(self.paralysisSideLabel, 2, 2)
        
        self.paralysisSideComboBox = QtWidgets.QComboBox(self.patientInfoGroup)
        self.paralysisSideComboBox.setObjectName("paralysisSideComboBox")
        self.paralysisSideComboBox.setMinimumWidth(100)
        self.paralysisSideComboBox.addItem("左侧")
        self.paralysisSideComboBox.addItem("右侧")
        self.paralysisSideComboBox.addItem("无")
        self.infoGridLayout.addWidget(self.paralysisSideComboBox, 2, 3)
        
        # Row 4: Additional Notes
        self.notesLabel = QtWidgets.QLabel(self.patientInfoGroup)
        self.notesLabel.setObjectName("notesLabel")
        self.notesLabel.setText("其他说明：")
        self.infoGridLayout.addWidget(self.notesLabel, 3, 0)
        
        self.notesTextEdit = QtWidgets.QTextEdit(self.patientInfoGroup)
        self.notesTextEdit.setObjectName("notesTextEdit")
        self.notesTextEdit.setMaximumHeight(80)
        self.notesTextEdit.setPlaceholderText("请输入其他相关说明信息...")
        self.infoGridLayout.addWidget(self.notesTextEdit, 3, 1, 1, 3)
        
        self.mainLayout.addWidget(self.patientInfoGroup)
        
        # Vertical spacer
        spacerItem = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, 
                                          QtWidgets.QSizePolicy.Expanding)
        self.mainLayout.addItem(spacerItem)
        
        # Button layout
        self.buttonLayout = QtWidgets.QHBoxLayout()
        self.buttonLayout.setObjectName("buttonLayout")
        
        # Button spacer
        buttonSpacer1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, 
                                            QtWidgets.QSizePolicy.Minimum)
        self.buttonLayout.addItem(buttonSpacer1)
        
        # Save button
        self.saveButton = QtWidgets.QPushButton(UserInfoForm)
        self.saveButton.setObjectName("saveButton")
        self.saveButton.setText("保存")
        self.saveButton.setMinimumSize(QtCore.QSize(100, 35))
        self.saveButton.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                font-size: 14px; 
                font-weight: bold; 
            }
            QPushButton:hover { 
                background-color: #2980b9; 
            }
            QPushButton:pressed { 
                background-color: #21618c; 
            }
        """)
        self.buttonLayout.addWidget(self.saveButton)
        
        # Clear button
        self.clearButton = QtWidgets.QPushButton(UserInfoForm)
        self.clearButton.setObjectName("clearButton")
        self.clearButton.setText("清空")
        self.clearButton.setMinimumSize(QtCore.QSize(100, 35))
        self.clearButton.setStyleSheet("""
            QPushButton { 
                background-color: #e74c3c; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                font-size: 14px; 
                font-weight: bold; 
            }
            QPushButton:hover { 
                background-color: #c0392b; 
            }
            QPushButton:pressed { 
                background-color: #a93226; 
            }
        """)
        self.buttonLayout.addWidget(self.clearButton)
        
        # Cancel button
        self.cancelButton = QtWidgets.QPushButton(UserInfoForm)
        self.cancelButton.setObjectName("cancelButton")
        self.cancelButton.setText("取消")
        self.cancelButton.setMinimumSize(QtCore.QSize(100, 35))
        self.cancelButton.setStyleSheet("""
            QPushButton { 
                background-color: #95a5a6; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                font-size: 14px; 
                font-weight: bold; 
            }
            QPushButton:hover { 
                background-color: #7f8c8d; 
            }
            QPushButton:pressed { 
                background-color: #6c7b7d; 
            }
        """)
        self.buttonLayout.addWidget(self.cancelButton)
        
        # Button spacer
        buttonSpacer2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, 
                                            QtWidgets.QSizePolicy.Minimum)
        self.buttonLayout.addItem(buttonSpacer2)
        
        self.mainLayout.addLayout(self.buttonLayout)
        
        # Connect slots
        QtCore.QMetaObject.connectSlotsByName(UserInfoForm)

    def retranslateUi(self, UserInfoForm):
        """Set up translations for the UI elements"""
        _translate = QtCore.QCoreApplication.translate
        UserInfoForm.setWindowTitle(_translate("UserInfoForm", "患者信息管理系统"))
        self.titleLabel.setText(_translate("UserInfoForm", "患者信息录入"))
        self.patientInfoGroup.setTitle(_translate("UserInfoForm", "基本信息"))
        self.nameLabel.setText(_translate("UserInfoForm", "姓名："))
        self.nameLineEdit.setPlaceholderText(_translate("UserInfoForm", "请输入患者姓名"))
        self.genderLabel.setText(_translate("UserInfoForm", "性别："))
        self.genderComboBox.setItemText(0, _translate("UserInfoForm", "男"))
        self.genderComboBox.setItemText(1, _translate("UserInfoForm", "女"))
        self.ageLabel.setText(_translate("UserInfoForm", "年龄："))
        self.strokeTypeLabel.setText(_translate("UserInfoForm", "卒中类型："))
        self.strokeTypeComboBox.setItemText(0, _translate("UserInfoForm", "出血型"))
        self.strokeTypeComboBox.setItemText(1, _translate("UserInfoForm", "缺血型"))
        self.strokeTypeComboBox.setItemText(2, _translate("UserInfoForm", "无卒中"))
        self.durationLabel.setText(_translate("UserInfoForm", "卒中时长："))
        self.paralysisSideLabel.setText(_translate("UserInfoForm", "偏瘫侧："))
        self.paralysisSideComboBox.setItemText(0, _translate("UserInfoForm", "左侧"))
        self.paralysisSideComboBox.setItemText(1, _translate("UserInfoForm", "右侧"))
        self.paralysisSideComboBox.setItemText(2, _translate("UserInfoForm", "无"))
        self.notesLabel.setText(_translate("UserInfoForm", "其他说明："))
        self.notesTextEdit.setPlaceholderText(_translate("UserInfoForm", "请输入其他相关说明信息..."))
        self.saveButton.setText(_translate("UserInfoForm", "保存"))
        self.clearButton.setText(_translate("UserInfoForm", "清空"))
        self.cancelButton.setText(_translate("UserInfoForm", "取消"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    UserInfoForm = QtWidgets.QWidget()
    ui = Ui_UserInfoForm()
    ui.setupUi(UserInfoForm)
    UserInfoForm.show()
    sys.exit(app.exec_())
import ui_sensorwidget
from PyQt5.QtWidgets import QWidget, QSizePolicy, QGridLayout, QHBoxLayout, QLabel, QCheckBox
from PyQt5.QtCore import Qt, pyqtSignal
import pyqtgraph as pg
import numpy as np

TIME_WINDOW = 500

class SensorWidget(QWidget):
    onSampleRateSet = pyqtSignal(list, int, int) # id, type, sampleRate
    onChannelsSet = pyqtSignal(list, int, int, int, list) # id, type, lights, detectors, channel

    def __init__(self, id = [0,0,0], type = 4, parent=None):
        super(SensorWidget, self).__init__(parent)
        self.ui = ui_sensorwidget.Ui_SensorWidget()
        self.ui.setupUi(self)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(1500, 300)
        self.move(0, 0)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.channels = []
        self.plot = []
        self.hb_curve = []
        self.hbo2_curve = []

        self.id = id
        self.type = type
        # self.ui.Label_SensorID.setText("传感器ID: " + str(id[0]) + "-" + str(id[1]) + "-" + str(id[2]))
        self.ui.Label_SensorID.setText("传感器ID:{:X}-{:X}-{:X}".format(id[0], id[1], id[2]))

        if type == 1:
            typetext = "EEG"
        elif type == 2:
            typetext = "sEMG"
        elif type == 3:
            typetext = "EEG/sEMG"
        elif type == 4:
            typetext = "fNIRS"
        elif type == 5:
            typetext = "EEG/fNIRS"
        elif type == 7:
            typetext = "EEG/fNIRS/sEMG"
        elif type == 8:
            typetext = "NIRS"
        else:
            typetext = "Undefined"
        self.ui.Label_SensorType.setText("类型: " + typetext)

        self.SetSampleRateButtonAlarm(True)
        self.SetChannelsButtonAlarm(True)
        self.ui.ComboBox_SampleRate.currentIndexChanged.connect(lambda: self.SetSampleRateButtonAlarm(True))
        self.ui.Button_SampleRate.clicked.connect(self.UpdateSampleRate)
        self.ui.Button_Channels.clicked.connect(self.UpdateChannels)

        self.ui.SpinBox_Detectors.valueChanged.connect(self.SetFnirsChannelConfig)
        self.ui.SpinBox_Detectors.valueChanged.connect(lambda: self.SetChannelsButtonAlarm(True))
        self.ui.SpinBox_Lights.valueChanged.connect(self.SetFnirsChannelConfig)
        self.ui.SpinBox_Lights.valueChanged.connect(lambda: self.SetChannelsButtonAlarm(True))

        # ------- 对Layout进行配置, 实现滚轮效果 -------

        old_items = []
        while self.ui.GridLayout_Channels.count():
            item = self.ui.GridLayout_Channels.takeAt(0)
            if item.widget():
                old_items.append(item.widget()) 
            elif item.layout():
                pass

        self.ui.gridLayoutWidget.deleteLater()
        self.ui.GridLayout_Channels = QGridLayout(self.ui.Widget_Channels)
        self.ui.GridLayout_Channels.setContentsMargins(5, 5, 5, 5)  # 适当留白
        self.ui.GridLayout_Channels.setSpacing(5)  # 控件间距
        self.ui.GridLayout_Channels.setAlignment(Qt.AlignTop | Qt.AlignLeft)  # 顶部左对齐
        
        self.ui.ScrollArea_Channels.setWidgetResizable(True)
        self.ui.ScrollArea_Channels.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.ScrollArea_Channels.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ui.Widget_Channels.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)


        old_items = []
        while self.ui.HLayout_Plot.count():
            item = self.ui.HLayout_Plot.takeAt(0)
            if item.widget():
                old_items.append(item.widget()) 
            elif item.layout():
                pass
        
        self.ui.horizontalLayoutWidget.deleteLater()
        self.ui.HLayout_Plot = QHBoxLayout(self.ui.Widget_Plot)
        self.ui.HLayout_Plot.setContentsMargins(5, 5, 5, 5)  # 适当留白
        self.ui.HLayout_Plot.setSpacing(5)  # 控件间距
        self.ui.HLayout_Plot.setAlignment(Qt.AlignLeft)  # 顶部左对齐
        
        self.ui.ScrollArea_Plot.setWidgetResizable(True)
        self.ui.ScrollArea_Plot.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.ui.ScrollArea_Plot.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ui.Widget_Plot.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        # -------------- #

        self.SetFnirsChannelConfig()

    def SetSampleRateButtonAlarm(self, isDevideRespond = True): 
        # 连接设备或采样率更改,但未发送设备采样率信息时进行提示
        # 收到采样率设置成功后文字恢复黑色
        if isDevideRespond:
            self.ui.Button_SampleRate.setStyleSheet("color: rgb(255, 0, 0);")
        else:
            self.ui.Button_SampleRate.setStyleSheet("color: rgb(0, 0, 0);")

    def SetChannelsButtonAlarm(self, isDevideRespond = True): 
        if isDevideRespond:
            self.ui.Button_Channels.setStyleSheet("color: rgb(255, 0, 0);")
        else:
            self.ui.Button_Channels.setStyleSheet("color: rgb(0, 0, 0);")

    # 设置采样率按钮, 当前仅适配fNIRS
    def UpdateSampleRate(self):
        self.onSampleRateSet.emit(self.id, self.type, self.ui.ComboBox_SampleRate.currentIndex())

    # fNIRS通道配置界面
    def SetFnirsChannelConfig(self):
        lights = self.ui.SpinBox_Lights.value()
        detectors = self.ui.SpinBox_Detectors.value()
        for i in reversed(range(self.ui.GridLayout_Channels.count())):
            widgetToRemove = self.ui.GridLayout_Channels.itemAt(i).widget()
            self.ui.GridLayout_Channels.removeWidget(widgetToRemove)
            widgetToRemove.setParent(None)
        self.ui.GridLayout_Channels.addWidget(QLabel("  "), 0, 0)
        for i in range(lights):
            self.ui.GridLayout_Channels.addWidget(QLabel("S" + str(i + 1)), 0, i + 1)
        for j in range(detectors):
            self.ui.GridLayout_Channels.addWidget(QLabel("D" + str(j + 1)), j + 1, 0)
            for i in range(lights):
                checkbox = QCheckBox()
                checkbox.stateChanged.connect(lambda: self.SetChannelsButtonAlarm(True))
                self.ui.GridLayout_Channels.addWidget(checkbox, j + 1, i + 1)

    def UpdateChannels(self):  # 格式为[Si, Dj], 如[[2, 1], [3, 2]]
        lights, detectors, self.channels = self.getChannels()
        self.onChannelsSet.emit(self.id, self.type, lights, detectors, self.channels)

    def getChannels(self):
        enableChannels = []
        for i in range(self.ui.SpinBox_Lights.value()):
            for j in range(self.ui.SpinBox_Detectors.value()):
                if self.ui.GridLayout_Channels.itemAtPosition(j + 1, i + 1).widget().isChecked():
                    enableChannels.append([i + 1, j + 1])
        return self.ui.SpinBox_Lights.value(), self.ui.SpinBox_Detectors.value(), enableChannels
    
    # 初始化绘图区域
    def PlotWidgetInit(self, chs):
        for i in range(self.ui.HLayout_Plot.count()):           
            self.ui.HLayout_Plot.itemAt(i).widget().deleteLater()
        for ch in chs:
            plot = pg.PlotWidget(title="S" + str(ch[0]) + "-D" + str(ch[1]))
            plot.setBackground((255, 255, 255))
            plot.resize(300, 200)
            plot.setMinimumSize(300, 200)
            self.ui.HLayout_Plot.addWidget(plot)
            self.plot.append(plot)
            # 绘制初始曲线
            self.hb_curve.append(plot.plot(np.array([-1]), np.array([0]), pen=pg.mkPen('b', width=2)) )
            self.hbo2_curve.append(plot.plot(np.array([-1]), np.array([0]), pen=pg.mkPen('r', width=2)) )
    
    def Plot(self, time, resolved):
        if resolved.shape[0]==0 or time.shape[0]==0:
            # print("No data to plot")
            return
        # print("resolved shape:", resolved.shape, "plot shape: ", len(self.plot))
        for i in range(len(self.plot)):
            self.hb_curve[i].setData(  time[-TIME_WINDOW:], resolved[-TIME_WINDOW:, 0, i])
            self.hbo2_curve[i].setData(time[-TIME_WINDOW:], resolved[-TIME_WINDOW:, 1, i])

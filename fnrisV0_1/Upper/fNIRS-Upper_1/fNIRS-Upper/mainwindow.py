from sys import argv, exit
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QSizePolicy, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer, QThread

import network
import sensor
import ui  # 命令行执行导出ui:  pyuic5 -x mainwindow.ui -o ui.py
import sensorwidget # pyuic5 -x sensorWidget.ui -o ui_sensorwidget.py

class PlotThread(QThread):
    def __init__(self):
        super(PlotThread, self).__init__()
        # 创建定时器
        self.timer = QTimer()
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.draw)

    def run(self):
        # 启动定时器
        self.timer.start()
        # 执行父类的run方法
        super().run()

    def stop(self):
        # 停止定时器
        self.timer.stop()
        # 执行父类的stop方法
        super().stop()

    def draw(self):
        for i in range(MainWindow_ui.VLayout_Sensors.count()):
            widget = MainWindow_ui.VLayout_Sensors.itemAt(i).widget()

            for i in range(len(SensorList)):
                if SensorList[i].id == widget.id:
                    # 更新绘图显示
                    # widget.Plot(SensorList[i].resolved)
                    widget.Plot(SensorList[i].time,SensorList[i].raw)
                    break
            break


def UpdateSensorList(id, type, operation, params=None):
    # operation: 'r'-删除 'a'-添加 'b'-电量 's'-采样率设置成功反馈 'c'-通道设置成功反馈 'd'-数据
    if operation == 'r':
        # 遍历widgets，找到id对应的widget并删除
        for i in range(MainWindow_ui.VLayout_Sensors.count()):
            widget = MainWindow_ui.VLayout_Sensors.itemAt(i).widget()
            if widget.id == id:
                MainWindow_ui.VLayout_Sensors.itemAt(i).widget().deleteLater()
                break

    elif operation == 'a':
        # 判断SensorList是否存在id对应的sensor
        if not any(sensor.id == id for sensor in SensorList):
            SensorList.append(sensor.Sensor(id, type))
        newWidget = sensorwidget.SensorWidget(id, type)
        MainWindow_ui.VLayout_Sensors.addWidget(newWidget)
        newWidget.onSampleRateSet.connect(Network.sendSampleRate)
        newWidget.onChannelsSet.connect(Network.sendChannels)

    elif operation == 'b':
        for i in range(MainWindow_ui.VLayout_Sensors.count()):
            widget = MainWindow_ui.VLayout_Sensors.itemAt(i).widget()
            if widget.id == id:
                widget.ui.Label_Battery.setText("电量: " + str(params[0]) + "%")
                break

    elif operation == 's':
        for i in range(MainWindow_ui.VLayout_Sensors.count()):
            widget = MainWindow_ui.VLayout_Sensors.itemAt(i).widget()
            if widget.id == id:
                widget.SetSampleRateButtonAlarm(False)
                break

    elif operation == 'c':
        for i in range(MainWindow_ui.VLayout_Sensors.count()):
            widget = MainWindow_ui.VLayout_Sensors.itemAt(i).widget()
            if widget.id == id:
                widget.SetChannelsButtonAlarm(False)
                # 获取ui通道配置信息, 储存到sensor类中
                l, d, c = widget.getChannels()
                for i in range(len(SensorList)):
                    if SensorList[i].id == id:
                        SensorList[i].setChannel(c)
                        # SensorList[i].channel = c
                        break
                widget.PlotWidgetInit(c)
                break
            
    elif operation == 'd':
        for i in range(MainWindow_ui.VLayout_Sensors.count()):
            widget = MainWindow_ui.VLayout_Sensors.itemAt(i).widget()
            if widget.id == id:
                for j in range(len(SensorList)):
                        if SensorList[j].id == id:
                            sen = SensorList[j]
                            # 数据长度验证 此时数据长度应为6*通道数+4
                            if len(params) == len(sen.channel) * 6 + 4:
                                sen.Update(params)
                            else:
                                print("Data length error: Please check the channel configuration")
                        break
                
                break

def ResetAllSensor():
    for i in range(len(SensorList)):
        SensorList[i].ResetData()
        


if __name__ == '__main__':
    app = QApplication(argv)
    MainWindow = QMainWindow()
    MainWindow_ui = ui.Ui_MainWindow()
    MainWindow_ui.setupUi(MainWindow)
    MainWindow.resize(1600, 900)

    MainWindow.show()

    # 设置标题
    # MainWindow.setWindowTitle("fNIRS信号采集系统")

    # 传感器列表
    # SensorList会储存程序运行过程中所有传感器, 但界面显示取决于实际连接的传感器(Network.deviceList)
    SensorList = []

    # 网络模块
    Network = network.UdpPort(1227, 2227)
    # port.onConnected.connect(ShowConnectedDevice)
    # port.onReceiveData.connect(dataProcessing.onReceiveData)
    # port.onReceiveBat.connect(ShowBatVolt)

    # 电量轮询
    batteryQuaryTimer = QTimer()
    batteryQuaryTimer.setInterval(10000)
    batteryQuaryTimer.timeout.connect(Network.sendBatteryQuery)
    batteryQuaryTimer.start()

    # 设置按钮点击事件
    MainWindow_ui.Button_Connect.clicked.connect(Network.sendConnect)
    MainWindow_ui.Button_Connect.clicked.connect(lambda: [MainWindow_ui.VLayout_Sensors.itemAt(i).widget().deleteLater() for i in range(MainWindow_ui.VLayout_Sensors.count())])
    
    MainWindow_ui.Button_Disconnect.clicked.connect(Network.sendDisconnect)
    
    MainWindow_ui.Button_StartSample.clicked.connect(Network.sendStartSample)
    MainWindow_ui.Button_StartSample.clicked.connect(ResetAllSensor)
    
    MainWindow_ui.Button_StopSample.clicked.connect(Network.sendStopSample)
    if MainWindow_ui.Record_click_count:
        MainWindow_ui.Button_StopSample.clicked.connect(lambda: [SensorList[i].SaveData() for i in range(len(SensorList)) if len(SensorList[i].time)>0 ])
    
    # 设置传出信号
    Network.onConnectedDevicesChanged.connect(UpdateSensorList)

    # 传感器显示界面配置
    # .ui生成的.py会在VLayout_Sensors之上额外添加一个verticalLayoutWidget导致滚轮无法正常工作，因此需要手动删除
    while MainWindow_ui.VLayout_Sensors.count():
        item = MainWindow_ui.VLayout_Sensors.takeAt(0)
        widget = item.widget()
        if widget:
            widget.setParent(MainWindow_ui.Widget_Sensors)  # 转移父控件
    MainWindow_ui.verticalLayoutWidget.deleteLater()
    MainWindow_ui.VLayout_Sensors = QVBoxLayout(MainWindow_ui.Widget_Sensors)

    MainWindow_ui.scrollArea.setWidgetResizable(True)
    MainWindow_ui.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # 垂直滚动条按需显示
    MainWindow_ui.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用水平滚动条
    MainWindow_ui.Widget_Sensors.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    MainWindow_ui.VLayout_Sensors.setAlignment(Qt.AlignTop) # 设置布局对齐方式
    MainWindow_ui.VLayout_Sensors.setSpacing(5)

    th = PlotThread()
    th.run()
    
    exit(app.exec_())

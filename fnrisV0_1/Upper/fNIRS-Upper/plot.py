import sys
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QTimer, QThread
import pyqtgraph as pg
import numpy as np
import time

BUFFER_LEN = 100

class LineChart_DrawThread(QThread):
    def __init__(self, linechart):
        super(LineChart_DrawThread, self).__init__()
        self.linechart = linechart
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
        # 绘制曲线
        linechart = self.linechart
        for i in range(linechart.plot_amount):
            linechart.hb_curve[i].setData(linechart.time_buffer, linechart.hb_buffer[i])
            linechart.hbo2_curve[i].setData(linechart.time_buffer, linechart.hbo2_buffer[i])

class LineChart(QWidget):
    def __init__(self, layout=None):
        super().__init__()
        self.layout = layout
        self.draw_thread = LineChart_DrawThread(self)

    def clear_layout(self):
        """清除布局中的所有小部件"""
        while self.layout.count():
            item = self.layout.takeAt(0)  # 获取第一个布局项
            widget = item.widget()  # 获取该布局项对应的控件
            if widget:
                widget.deleteLater()  # 删除控件
            if item.layout():  # 如果布局项本身是一个子布局，则递归清除
                self.clear_layout_recursive(item.layout())

    def initGraph(self, plot_amount):
        self.plot_amount = plot_amount
        # 数据缓冲区
        self.time_buffer = np.linspace(0, 1e-6, BUFFER_LEN)
        self.hb_buffer = np.zeros((plot_amount, BUFFER_LEN))
        self.hbo2_buffer = np.zeros((plot_amount, BUFFER_LEN))

        # 清空当前layout
        self.clear_layout()
        # 创建空图表
        self.plot = [pg.PlotWidget(title="") for i in range(plot_amount)]
        
        for plot in self.plot:
            plot.setTitle(None)
            plot.setBackground((255, 255, 255))
            self.layout.addWidget(plot)

            # 隐藏横轴刻度
            class CustomAxis(pg.AxisItem):
                def tickStrings(self, values, scale, spacing):
                    # 返回空列表以隐藏标签，但仍保留刻度
                    return [''] * len(values)
            # 替换默认的横轴为自定义横轴
            # custom_axis = CustomAxis(orientation='bottom')  # 创建自定义横轴
            # plot.setAxisItems({'bottom': custom_axis})  # 应用到 PlotWidget
            self.layout.setSpacing(5)  # 设置布局之间的间隔为 0
            self.layout.setContentsMargins(0, 0, 0, 0)  # 设置布局的外边距为 0

        # 绘制初始曲线
        self.hb_curve = [self.plot[i].plot(self.time_buffer, self.hb_buffer[i], pen=pg.mkPen('b', width=2)) for i in range(plot_amount)]
        self.hbo2_curve = [self.plot[i].plot(self.time_buffer, self.hbo2_buffer[i], pen=pg.mkPen('r', width=2)) for i in range(plot_amount)]


    def updateData(self, data):
        # 数据更新
        self.time_buffer = np.roll(self.time_buffer, -1)
        self.time_buffer[-1] = data[0] / 10
        for i in range(self.plot_amount):
            self.hb_buffer[i] = np.roll(self.hb_buffer[i], -1)
            self.hb_buffer[i][-1] = data[2*i+1]
            self.hbo2_buffer[i] = np.roll(self.hbo2_buffer[i], -1)
            self.hbo2_buffer[i][-1] = data[2*i+2]






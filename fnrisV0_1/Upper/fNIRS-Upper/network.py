import sys
import socket
import psutil
import ipaddress
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtWidgets import QWidget
from PyQt5.QtNetwork import QUdpSocket, QHostAddress
import time
import crc
import math

POS_SENSOR_ID = 2
POS_SENSOR_TYPE = 5
POS_CMD = 6
POS_DATALENGTH = 8
POS_DATA = 9

# 获取WLAN信息
def get_wlan_ip_and_subnet():
    # 获取本机所有网络接口的信息
    addrs = psutil.net_if_addrs()

    result = {}
    for interface, addr_list in addrs.items():
        for addr in addr_list:
            if addr.family == socket.AF_INET:  # IPv4 地址
                ip = addr.address
                subnet_mask = addr.netmask
                result[interface] = {'ip': ip, 'subnet_mask': subnet_mask}
    return result["WLAN"]

# 获取当前广播地址
def get_broadcast_address():
    network_info = get_wlan_ip_and_subnet()
    network = ipaddress.IPv4Network(f"{network_info['ip']}/{network_info['subnet_mask']}", strict=False)               
    # 获取广播地址
    broadcast_address = network.broadcast_address
    return str(broadcast_address)


class UdpPort(QWidget):
    # 定义信号
    onConnectedDevicesChanged = pyqtSignal(list, int, str, list)

    def __init__(self, localPort=1227, remotePort=2227):  # 下位机端口需相同
        super().__init__()
        # self.lt = 0

        self.crc = crc.Crc(0x1021)  # CRC-16-CCITT polynomial

        # 设备列表(实际连接的设备): 依次存放ip地址, mac地址低3位, 传感器类型
        self.deviceList = []

        self.localPort = localPort
        self.remotePort = remotePort
        self.ip = get_wlan_ip_and_subnet()["ip"]
        self.iplist = self.ip.split('.')
        self.broadcast_ip = get_broadcast_address()

        # 接收端口
        self.socket = QUdpSocket()
        self.socket.bind(QHostAddress(self.ip), self.localPort)
        self.socket.readyRead.connect(self.udpDatagramReceived)

    # 连接广播
    def sendConnect(self):
        # 清空设备列表
        self.deviceList = []
        # 发送广播
        datagram = [0xAB, 0xAB, 0, 0, 0, 4, 0xB0, 0, 4]
        datagram.extend([int(i) for i in self.iplist])
        crc16 = self.crc.crc16(datagram, len(datagram))
        datagram.extend([crc16 >> 8, crc16 & 0xFF])
        self.socket.writeDatagram(bytes(datagram), QHostAddress(self.broadcast_ip), self.remotePort)

    # 断连
    def sendDisconnect(self):
        self.sendEmptyDataPacket(0xB1)

    # 开始采集
    def sendStartSample(self):
        self.sendEmptyDataPacket(0xC0)

    # 结束采集
    def sendStopSample(self):
        self.sendEmptyDataPacket(0xC1)

    # 查询电量
    def sendBatteryQuery(self):
        self.sendEmptyDataPacket(0xC2)

    # 发送采样率
    def sendSampleRate(self, id, type, ratecode):
        device = None
        for dev in self.deviceList:
            if dev["id"] == id:
                device = dev
                break
        if device == None:
            return

        datagram = [0xAB, 0xAB] + id + [type] + [0xC3, 0, 2, type, ratecode]
        crc16 = self.crc.crc16(datagram, len(datagram))
        datagram.extend([crc16 >> 8, crc16 & 0xFF])
        self.socket.writeDatagram(bytes(datagram), QHostAddress(device["ip"]), self.remotePort)

    # 发送通道配置
    def sendChannels(self, id, type, lights, detectors, channel):
        device = None
        for dev in self.deviceList:
            if dev["id"] == id:
                device = dev
                break
        if device == None:
            return
        
        # bytesPerDetector = 2
        bytesPerDetector = math.ceil(detectors/8)

        channelBytes = [0] * (bytesPerDetector * lights)
        for pair in channel:  # [0] - light, [1] - detector
            # channelBytes[(pair[0] - 1) * bytesPerDetector + (bytesPerDetector - (pair[1]) // 8) - 1] |= (1 << ((pair[1]) % 8))
            channelBytes[(pair[0] - 1) * bytesPerDetector + math.floor((pair[1]-1)/8)] |= (1 << ((pair[1]-1) % 8))

        datagram = [0xAB, 0xAB] + id + [type] + [0xA0, 0, bytesPerDetector * lights + 3, type, lights, detectors] + channelBytes

        crc16 = self.crc.crc16(datagram, len(datagram))
        datagram.extend([crc16 >> 8, crc16 & 0xFF])
        self.socket.writeDatagram(bytes(datagram), QHostAddress(device["ip"]), self.remotePort)

    # 发送无数据信息
    def sendEmptyDataPacket(self, cmd):
        for device in self.deviceList:
            # 发送信息
            datagram = [0xAB, 0xAB] + device["id"] + [device["type"]] + [cmd, 0, 0]
            crc16 = self.crc.crc16(datagram, len(datagram))
            datagram.extend([crc16 >> 8, crc16 & 0xFF])
            self.socket.writeDatagram(bytes(datagram), QHostAddress(device["ip"]), self.remotePort)


    # 接收回调
    def udpDatagramReceived(self):
        (datagram, host, port) = self.socket.readDatagram(self.socket.pendingDatagramSize())
        datagram = list(datagram)

        # 包头校验
        if datagram[0] != 0xBA or datagram[1] != 0xBA:
            print("Header error")
            return
        # 数据长度校验: dg[8]为实际数据长度, 总长度应为dg[8]+11
        if len(datagram) < POS_DATALENGTH:  # 防止不完整包导致崩溃
            print("Data len error")
            return
        if len(datagram) != datagram[POS_DATALENGTH] + 11:
            print("Data len error")
            return
        # CRC校验
        crc16 = self.crc.crc16(datagram, len(datagram) - 2)
        if crc16 != (datagram[-2] << 8) + datagram[-1]:
            print("CRC error")
            return
        
        # 解析数据: dg[6]为指令类型])
        if datagram[POS_CMD] == 0xB0:  # 连接反馈
            device = {
                "ip": str(datagram[POS_DATA]) + "." + str(datagram[POS_DATA+1]) + "." + str(datagram[POS_DATA+2]) + "." + str(datagram[POS_DATA+3]),
                "id": datagram[POS_SENSOR_ID:POS_SENSOR_ID+3], 
                "type": datagram[POS_SENSOR_TYPE]}
            self.deviceList.append(device)
            self.onConnectedDevicesChanged.emit(device["id"], device["type"], 'a', [])

        if datagram[6] == 0xB1:  # 断连反馈
            device = {
                "id": datagram[POS_SENSOR_ID:POS_SENSOR_ID+3], 
                "type": datagram[POS_SENSOR_TYPE]}
            if datagram[POS_DATA] == 1:
                # 寻找匹配设备删除
                for i in range(len(self.deviceList)):
                    if self.deviceList[i]["id"] == device["id"]:
                        self.deviceList.pop(i)
                        self.onConnectedDevicesChanged.emit(device["id"], device["type"], 'r', [])
                        break

        if datagram[6] == 0xC2:  # 电量反馈
            device = {
                "id": datagram[POS_SENSOR_ID:POS_SENSOR_ID+3], 
                "type": datagram[POS_SENSOR_TYPE]}
            self.onConnectedDevicesChanged.emit(device["id"], device["type"], 'b', [datagram[POS_DATA]])

        if datagram[6] == 0xC3:  # 采样率设置反馈
            if datagram[POS_DATA] == 1:
                device = {
                    "id": datagram[POS_SENSOR_ID:POS_SENSOR_ID+3], 
                    "type": datagram[POS_SENSOR_TYPE]}
                self.onConnectedDevicesChanged.emit(device["id"], device["type"], 's', [])

        if datagram[6] == 0xA0:  # 通道设置反馈
            if datagram[POS_DATA] == 1:
                device = {
                    "id": datagram[POS_SENSOR_ID:POS_SENSOR_ID+3], 
                    "type": datagram[POS_SENSOR_TYPE]}
                self.onConnectedDevicesChanged.emit(device["id"], device["type"], 'c', [])

        if datagram[6] == 0xA1 or datagram[6] == 0xA2:  # 数据/补包
            device = {
                "id": datagram[POS_SENSOR_ID:POS_SENSOR_ID+3], 
                "type": datagram[POS_SENSOR_TYPE]}
            self.onConnectedDevicesChanged.emit(device["id"], device["type"], 'd', datagram[POS_DATA:POS_DATA+datagram[POS_DATALENGTH]])




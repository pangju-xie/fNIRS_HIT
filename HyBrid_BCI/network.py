# -*- coding: utf-8 -*-
import sys
import socket
import psutil
import logging
import time
from typing import List, Dict, Optional, Callable
from enum import IntEnum
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QWidget
from PyQt5.QtNetwork import QUdpSocket, QHostAddress, QAbstractSocket
import crc

# Simple logging setup
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)



@dataclass
class Device:
    """Device information"""
    ip: str
    id: List[int]
    type: int
    port: int
    
    def __hash__(self):
        return hash((self.ip, tuple(self.id), self.type, self.port))

# @dataclass
class Commands(IntEnum):
    """Command definitions"""
    CONNECT = 0xB0
    DISCONNECT = 0xB1
    START_SAMPLE = 0xC0
    STOP_SAMPLE = 0xC1
    BATTERY_QUERY = 0xC2
    SAMPLE_RATE = 0xC3
    CHANNEL_CONFIG = 0xA0
    DATA_RECEIVE = 0xA1
    DATA_PATCHING = 0xA2

@dataclass
class PendingCommand:
    """Pending command tracking"""
    command: Commands
    packet: bytes
    target_ip: str
    timestamp: float = 0.0
    retry_count: int = 0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

class UdpPort(QWidget):
    """
    Simplified UDP communication handler for fNIRS sensors
    Focuses on core functionality with minimal complexity
    """
    # Essential signals
    #mainwindow
    onDeviceConnected = pyqtSignal(list, int)
    onDeviceDisconnected = pyqtSignal()
    onBatteryUpdated = pyqtSignal(int)
    #config
    onSampleRateSet = pyqtSignal(int, bool)
    onChannelConfigSet = pyqtSignal(int, bool)
    #display
    onDeviceSample = pyqtSignal(bool)
    onDataReceived = pyqtSignal(int, int, list)
    onDataPatched = pyqtSignal(int, int, list)
    
    networkError = pyqtSignal(str)
    connectionStatusChanged = pyqtSignal(bool)
    commandAcknowledged = pyqtSignal(int, list, int, bool)
    
    def __init__(self, localPort: int = 1227, remotePort: int = 2227):
        super().__init__()
        
        # Network settings
        self.localPort = localPort
        self.remotePort = remotePort
        
        # Device management
        self.devices: List[Device] = []
        
        # Network components
        self.socket: Optional[QUdpSocket] = None
        self.crc = crc.Crc(0x1021)
        
        # Network info
        self.local_ip = ""
        self.broadcast_ip = ""
        
        # Command tracking
        self.pending_commands: Dict[str, PendingCommand] = {}
        self.retry_timer = QTimer()
        self.retry_timer.timeout.connect(self._check_retries)
        self.retry_timer_interval = 2000  # 2 seconds
        # self.retry_timer.start(2000)  # Check every 2 seconds
        
        # Initialize
        self._setup_network()
    
    ### Network setup and management ###
    
    def _setup_network(self):
        """Setup network with minimal complexity"""
        try:
            # Get network info
            self._get_network_info()
            
            # Setup socket
            self._setup_socket()
            
            logger.info(f"Network ready: {self.local_ip}:{self.localPort} -> {self.broadcast_ip}:{self.remotePort}")
            
        except Exception as e:
            error_msg = f"Network setup failed: {e}"
            logger.error(error_msg)
            self.networkError.emit(error_msg)
    
    def _get_network_info(self):
        """Get local IP and broadcast address"""
        try:
            # Find active network interface
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            
            # Try common interface names first
            preferred = ['WLAN', 'Wi-Fi', 'wlan0', 'eth0', 'en0']
            
            for name in preferred:
                if name in addrs and name in stats and stats[name].isup:
                    for addr in addrs[name]:
                        if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                            self.local_ip = addr.address
                            self._calc_broadcast(addr.address, addr.netmask)
                            return
            
            # Fallback to any active interface
            for name, addr_list in addrs.items():
                if name in stats and stats[name].isup:
                    for addr in addr_list:
                        if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                            self.local_ip = addr.address
                            self._calc_broadcast(addr.address, addr.netmask)
                            return
                            
            raise Exception("No suitable network interface found")
            
        except Exception as e:
            raise Exception(f"Network detection failed: {e}")
    
    def _calc_broadcast(self, ip: str, netmask: str):
        """Calculate broadcast address"""
        try:
            import ipaddress
            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
            self.broadcast_ip = str(network.broadcast_address)
        except:
            # Simple fallback
            self.broadcast_ip = '.'.join(ip.split('.')[:-1] + ['255'])
    
    def _setup_socket(self):
        """Setup UDP socket with retry"""
        for port_offset in range(5):  # Try 5 ports times
            try:
                if self.socket:
                    self.socket.close()
                    self.socket = None
                
                self.socket = QUdpSocket(self)
                
                # Try binding
                if self.socket.bind(QHostAddress.Any, self.localPort, QUdpSocket.ReuseAddressHint):
                    # self.localPort = current_port
                    self.socket.readyRead.connect(self._handle_data)
                    logger.info(f"Socket bound to port {self.localPort}")
                    return
                    
            except Exception as e:
                logger.warning(f"Port {self.localPort + port_offset} failed: {e}")
                continue
        
        raise Exception("Could not bind to any port")
    
    ##### Handle incoming data  #####
    
    def _handle_data(self):
        """Handle incoming UDP data"""
        while self.socket.hasPendingDatagrams():
            try:
                size = self.socket.pendingDatagramSize()
                data, host, port = self.socket.readDatagram(size)
                
                if data:
                    # logger.info(f'Received {len(data)} bytes from {host.toString()}:{port}')
                    self._process_packet(list(data), host.toString())
                    
            except Exception as e:
                logger.error(f"Error reading datagram: {e}")
    
    def _process_packet(self, packet: List[int], host_ip: str):
        """Process received packet"""
        try:
            # Basic validation
            if len(packet) < 11:
                logger.warning("Packet too short")
                return
            
            # Check headers (incoming should be 0xBA)
            if packet[0] != 0xBA or packet[1] != 0xBA:
                logger.warning("Invalid packet header")
                return
            
            # Validate CRC
            crc_calc = self.crc.crc16(packet, len(packet) - 2)
            crc_recv = (packet[-2] << 8) + packet[-1]
            if crc_calc != crc_recv:
                logger.warning("CRC error")
                return
            
            # Parse packet
            sensor_id = packet[2:5]
            sensor_type = packet[5]
            command = Commands(packet[6])
            data_len = (packet[7]<<8) + packet[8]
            
            if len(packet) != 9 + data_len + 2:
                logger.warning("Packet length mismatch")
                return
            
            data = packet[9:9+data_len]
            
            logger.debug(f"Received: cmd=0x{command.name} from {host_ip}")
            
            # Handle command
            self._handle_command(command, sensor_id, sensor_type, data, host_ip)
            
        except Exception as e:
            logger.error(f"Packet processing error: {e}")
    
    def _handle_command(self, cmd: Commands, sensor_id: List[int], sensor_type: int, data: List[int], host_ip: str):
        """Handle different commands"""
        try:
            success = False
            if cmd == Commands.CONNECT:
                success = self._handle_connect(sensor_id, sensor_type, data, host_ip)
            elif cmd == Commands.DISCONNECT:
                success = self._handle_disconnect(data)
            elif cmd == Commands.START_SAMPLE:
                success = self._handle_start_sample(data)
            elif cmd == Commands.STOP_SAMPLE:
                success = self._handle_stop_sample(data)
            elif cmd == Commands.BATTERY_QUERY:
                success = self._handle_battery_query(data)
            elif cmd == Commands.SAMPLE_RATE:
                success = self._handle_sample_rate(sensor_type, data)
            elif cmd == Commands.CHANNEL_CONFIG:
                success = self._handle_channel_config(sensor_type, data)
            elif cmd == Commands.DATA_RECEIVE:
                success = self._handle_data_receive(sensor_type, data)
            elif cmd == Commands.DATA_PATCHING:
                success = self._handle_data_patching(sensor_type, data)
            else:
                logger.warning(f"Unknown command: 0x{cmd:02X}")
                return
                    
            # Handle pending command acknowledgment if command was processed successfully
            if success:
                self._acknowledge_pending_command(cmd, sensor_id)
                
        except Exception as e:
            logger.error(f"Command handling error: {e}")
    
    def _acknowledge_pending_command(self, cmd: Commands, sensor_id: List[int]):
        """Handle acknowledgment of pending commands"""
        # For CONNECT command, check both broadcast key and specific device key
        if cmd == Commands.CONNECT:
            # Check broadcast key first (original send key)
            broadcast_key = f"{tuple([0,0,0])}_{cmd.name}"
            if broadcast_key in self.pending_commands:
                logger.info(f"Command {cmd.name} acknowledged by device {sensor_id}")
                del self.pending_commands[broadcast_key]
            
            # # Also check for device-specific key if exists
            # device_key = f"{tuple(sensor_id)}_{cmd.name}"
            # if device_key in self.pending_commands:
            #     logger.info(f"Command {cmd.name} acknowledged by device {sensor_id}")
            #     del self.pending_commands[device_key]
        else:
            # For other commands, use device-specific key
            cmd_key = f"{tuple(sensor_id)}_{cmd.name}"
            if cmd_key in self.pending_commands:
                logger.info(f"Command {cmd.name} acknowledged by device {sensor_id}")
                del self.pending_commands[cmd_key]
        
        # Stop timer only if no pending commands remain
        if not self.pending_commands and self.retry_timer.isActive():
            self.retry_timer.stop()
            logger.debug("All commands acknowledged, stopping retry timer")
            
    def _handle_connect(self, sensor_id: List[int], sensor_type: int, data: List[int], host_ip: str):
        """Handle device connection"""
        if len(data) >= 4:
            device_ip = f"{data[0]}.{data[1]}.{data[2]}.{data[3]}"
            device = Device(ip=device_ip, id=sensor_id, type=sensor_type, port=self.remotePort)
            
            if device not in self.devices:
                self.devices.append(device)
                logger.info(f"Device connected: {sensor_id} at {device_ip}")
                if self.devices.__len__() != 1:
                    logger.warning("Multiple devices connected, specify target IP for commands")
                else:
                    logger.info("Single device connected, commands will target this device")
                    self.onDeviceConnected.emit(sensor_id, sensor_type)
            return True
        return False
    
    def _handle_disconnect(self, data: List[int]):
        """Handle device disconnection"""
        if data and data[0] == 1:
            for device in self.devices[:]:
                logger.info(f"Device disconnected: {device.id} at {device.ip}")
                self.devices.remove(device)
                self.onDeviceDisconnected.emit()
            return True
        return False
        
    def _handle_start_sample(self, data: List[int]):
        if data and data[0] == 1:
            logger.info(f"start sampling")
            self.onDeviceSample.emit(True)
            return True
        return False
    
    def _handle_stop_sample(self, data: List[int]):
        if data and data[0] == 1:
            logger.info(f"stop sampling")
            self.onDeviceSample.emit(False)
            return True
        return False
        
    def _handle_battery_query(self, data: List[int]):
        if data:
            battery_level = data[0]
            logger.info(f'device battery level:{battery_level}')
            self.onBatteryUpdated.emit(battery_level)
            return True
        return False
    
    def _handle_sample_rate(self, sensor_type: int, data: List[int]):
        if len(self.devices) == 0:
            logger.warning("No devices connected")
            return False
        if sensor_type & self.devices[0].type == 0:
            logger.warning(f"Sample rate type mismatch, receive type: {sensor_type}, device type: {self.devices[0].type}")
            return False
        elif data and data[0] == 1:
            logger.info("Sample rate set success")
            self.onSampleRateSet.emit(sensor_type, True)
            return True
        return False
    
    def _handle_channel_config(self,sensor_type: int, data: List[int]):
        if len(self.devices) == 0:
            logger.warning("No devices connected")
            return False
        if sensor_type & self.devices[0].type == 0:
            logger.warning(f"Channel config type mismatch, receive type: {sensor_type}, device type: {self.devices[0].type}")
            return False
        elif data and data[0] == 1:
            logger.info("Channel config set success")
            self.onChannelConfigSet.emit(sensor_type, True)
            return True
        return False
    
    def _handle_data_receive(self,sensor_type: int, data:List[int]):
        if len(self.devices) == 0:
            logger.warning("No devices connected")
            return False
        if sensor_type & self.devices[0].type != 0:
            logger.warning(f"Data receive type mismatch, receive type:{sensor_type}, device type:{self.devices[0].type}")
            return False
        elif data:
            packet_id = (data[-4]<<24) + (data[-3]<<16) + (data[-2]<<8) + data[-1]
            self.onDataReceived.emit(sensor_type, packet_id, data)
            return True
        return False
    
    def _handle_data_patching(self, sensor_type: int, data: List[int]):
        if len(self.devices) == 0:
            logger.warning("No devices connected")
            return False
        if sensor_type & self.devices[0].type == 0:
            logger.warning(f"Data patching type mismatch, receive type: {sensor_type}, device type: {self.devices[0].type}")
            return False
        elif data:
            packet_id = (data[-4]<<24) + (data[-3]<<16) + (data[-2]<<8) + data[-1]
            self.onDataPatched.emit(sensor_type, packet_id, data[:-4])
            return True
        return False
    
    
    #### Sending commands with retry tracking ###
    
    def _send_packet(self, cmd: Commands, sensor_id: List[int], sensor_type: int, data: List[int], target_ip: str) -> bool:
        """Send packet to target"""
        # Build packet (outgoing uses 0xAB headers)
        data_len = len(data)
        send_datalen = [(data_len >> 8) & 0xFF, data_len & 0xFF]
        packet = [0xAB, 0xAB] + sensor_id + [sensor_type, cmd] + send_datalen + data

        # Add CRC
        crc_val = self.crc.crc16(packet, len(packet))
        packet.extend([crc_val >> 8, crc_val & 0xFF])
        
        #Send data
        if self._udp_send_data(bytes(packet), target_ip, self.remotePort):
            # Track for retry 
            if (cmd != Commands.DATA_PATCHING and cmd != Commands.BATTERY_QUERY):
                cmd_key = f"{tuple(sensor_id)}_{cmd.name}"
                self.pending_commands[cmd_key] = PendingCommand(cmd, bytes(packet), target_ip)
                
                # Start retry timer if not already running
                if not self.retry_timer.isActive():
                    self.retry_timer.start(self.retry_timer_interval)
                    
                logger.debug(f"Command {cmd.name}:{cmd_key} sent to {sensor_id}, waiting for acknowledgment")
            return True
        return False
    
    def _udp_send_data(self, packet:bytes, ip: str, port: int):
        try:
            # Send
            bytes_sent = self.socket.writeDatagram(packet, QHostAddress(ip), port)
            
            if bytes_sent == -1:
                logger.error(f"Failed to send packet to {ip}")
                return False
            return bytes_sent > 0
            
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False
    
    def _send_command(self, cmd: Commands, data: List[int] = None) -> bool:
        """Send command with retry tracking"""
        if data is None:
            data = []
        
        try:
            # Determine target IP
            if cmd == Commands.CONNECT:
                target_ip = self.broadcast_ip
                sensor_id = [0,0,0]
                sensor_type = 4  # Broadcast type
            else:
                device = self.devices[0] if len(self.devices) == 1 else None
                if not device:
                    logger.warning("Multiple devices connected, specify target IP")
                    return False
                target_ip = device.ip
                sensor_id = device.id
                sensor_type = device.type
            
            #Create and send packet
            return self._send_packet(cmd, sensor_id, sensor_type, data, target_ip)
            
        except Exception as e:
            logger.error(f"Failed to send command {cmd.name}: {e}")
            return False
    
    def _check_retries(self):
        """Check for commands that need retry"""
        current_time = time.time()
        # timeout = 5.0  # 5 second timeout
        max_retries = 3
        
        expired = []
        for cmd_key, pending in self.pending_commands.items():
            if current_time - pending.timestamp > self.retry_timer_interval / 1000.0:
                if pending.retry_count < max_retries:
                    # Retry
                    pending.retry_count += 1
                    pending.timestamp = current_time
                    self._udp_send_data(pending.packet, pending.target_ip, self.remotePort)
                    logger.warning(f"Retrying command {pending.command.name}")
                else:
                    # Give up
                    expired.append(cmd_key)
        
        # Remove expired commands
        for cmd_key in expired:
            del self.pending_commands[cmd_key]
        
        # Stop timer if no pending commands remain
        if not self.pending_commands and self.retry_timer.isActive():
            self.retry_timer.stop()  # Stop timer if no pending commands
            logger.debug("No pending commands, stopping retry timer")
    
    # Public API methods
    def sendConnect(self) -> bool:
        """Send connection broadcast"""
        self.devices.clear()
        send_data = [int(x) for x in self.local_ip.split('.')]
        success = self._send_command(Commands.CONNECT, send_data)
        if success:
            logger.info("Connection broadcast sent")
        return success
    
    def sendDisconnect(self) -> bool:
        """Disconnect all devices"""
        success = self._send_command(Commands.DISCONNECT)
        if success:
            logger.info("Disconnect sent to all devices")
        return success
    
    def sendStartSample(self) -> bool:
        """Start sampling on all devices"""
        success = self._send_command(Commands.START_SAMPLE)
        if success:
            logger.info("Start sampling sent to all devices")
        return success
    
    def sendStopSample(self) -> bool:
        """Stop sampling on all devices"""
        success = self._send_command(Commands.STOP_SAMPLE)
        if success:
            logger.info("Stop sampling sent to all devices")
        return success
    
    def sendBatteryQuery(self) -> bool:
        """Query battery status"""
        success = self._send_command(Commands.BATTERY_QUERY)
        if success:
            logger.info("Battery query sent to all devices")
        return success
    
    def sendSampleRate(self, sensor_type: int, rate: int) -> bool:
        data = [sensor_type, rate]
        success = self._send_command(Commands.SAMPLE_RATE, data)
        if success:
            logger.info(f"Sample rate set to {rate} for type {sensor_type}")
        return success
    
    def sendChannelConfig(self, sensor_type: int, config: List[int]) -> bool:
        data = [sensor_type] + config
        success = self._send_command(Commands.CHANNEL_CONFIG, data)
        if success:
            logger.info(f"Channel config sent for type {sensor_type}")
        return success
    
    def sendDataPatching(self, sensor_type: int, patch_data: int) -> bool:
        data = [sensor_type, (patch_data>>24) & 0xFF, (patch_data>>16) & 0xFF, (patch_data>>8) & 0xFF, patch_data & 0xFF]
        success = self._send_command(Commands.DATA_PATCHING, data)
        if success:
            logger.info(f"Data patching sent for type {sensor_type}")
        return success
    
    def get_connected_devices(self) -> List[Device]:
        """Get list of connected devices"""
        return self.devices.copy()
    
    def get_statistics(self) -> Dict[str, int]:
        """Get basic statistics"""
        return {
            'connected_devices': len(self.devices),
            'pending_commands': len(self.pending_commands)
        }
    
    def close(self):
        """Close network connection"""
        try:
            if self.retry_timer.isActive():
                self.retry_timer.stop()
            
            if self.devices:
                self.sendDisconnect()
            
            if self.socket:
                self.socket.close()
                self.socket = None
            
            self.devices.clear()
            self.pending_commands.clear()
            logger.info("Network closed")
            
        except Exception as e:
            logger.error(f"Close error: {e}")


# Simple test function
def test_simple_udp():
    """Simple test of UDP handler"""
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer
    
    app = QApplication(sys.argv)
    udp = UdpPort()
    
    def on_device_connected(sensor_id, sensor_type):
        print(f"Device connected: {sensor_id}, type: {sensor_type}")
    
    def on_battery(level):
        print(f"Battery level: {level}%")
    
    def on_error(error):
        print(f"Error: {error}")
    
    # Connect signals
    udp.onDeviceConnected.connect(on_device_connected)
    udp.onBatteryStatusUpdated.connect(on_battery)
    udp.networkError.connect(on_error)
    
    # Test sequence
    def start_test():
        print(f"Local IP: {udp.local_ip}")
        print(f"Broadcast: {udp.broadcast_ip}")
        print("Sending connection...")
        udp.sendConnect()
    
    def check_devices():
        devices = udp.get_connected_devices()
        print(f"Connected devices: {len(devices)}")
        if devices:
            udp.sendBatteryQuery()
    
    def finish_test():
        stats = udp.get_statistics()
        print(f"Final stats: {stats}")
        udp.close()
        app.quit()
    
    # Schedule test
    QTimer.singleShot(100, start_test)
    QTimer.singleShot(3000, check_devices)
    QTimer.singleShot(6000, finish_test)
    
    print("Starting simple UDP test...")
    sys.exit(app.exec_())


if __name__ == "__main__":
    test_simple_udp()
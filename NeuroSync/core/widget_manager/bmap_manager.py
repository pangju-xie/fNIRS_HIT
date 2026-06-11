import math
import logging
import mne
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

class BrainMapManager(QObject):
    """
    脑电拓扑二维坐标引擎 (Manager/Model)
    核心亮点：
    1. 彻底抛弃 3D 投影带来的球面边缘畸变。
    2. 使用命名解析器将 10-5 系统转换为均匀的正方形网格。
    3. 采用图形学「方圆映射算法 (Squircle Mapping)」将正方形平滑拉伸为标准圆形。
    """
    signal_selection_changed = pyqtSignal()
    signal_warning = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.all_nodes = {}         
        self.selected_states = {}   
        self.node_aliases = {}      
        self.valid_channels = []    
        self.blacklisted_channels = set() 
        
        self.channel_distance_threshold = 0.35 

        self.limits = {'EEG': 32, 'Source': 16, 'Detector': 16, 'EMG': 16}
        
        # 初始化时直接生成纯 2D 平面拓扑坐标
        self._generate_2d_planar_layout()

    def _parse_1005_grid(self, name):
        """
        核心引擎：将脑电名称直接解析为二维网格坐标 (X, Y)，取值范围 [-1.0, 1.0]
        原理：根据国际 10-5 系统的命名规律，将其排布在一个标准正方形网格上。
        """
        name = name.upper()
        y_val = None
        
        if name.startswith('AFP'): y_val = 0.875; name = name[3:]
        elif name.startswith('AFF'): y_val = 0.625; name = name[3:]
        elif name.startswith('FFC'): y_val = 0.375; name = name[3:]
        elif name.startswith('FCC'): y_val = 0.125; name = name[3:]
        elif name.startswith('CCP'): y_val = -0.125; name = name[3:]
        elif name.startswith('CPP'): y_val = -0.375; name = name[3:]
        elif name.startswith('PPO'): y_val = -0.625; name = name[3:]
        elif name.startswith('POO'): y_val = -0.875; name = name[3:]
        # 解析 10-10 系统的主干行
        elif name.startswith('FP'): y_val = 1.0; name = name[2:]
        elif name.startswith('AF'): y_val = 0.75; name = name[2:]
        elif name.startswith('FC'): y_val = 0.25; name = name[2:]
        elif name.startswith('CP'): y_val = -0.25; name = name[2:]
        elif name.startswith('PO'): y_val = -0.75; name = name[2:]
        elif name.startswith('FT'): y_val = 0.25; name = name[2:]
        elif name.startswith('TP'): y_val = -0.25; name = name[2:]
        elif name.startswith('F'): y_val = 0.5; name = name[1:]
        elif name.startswith('C'): y_val = 0.0; name = name[1:]
        elif name.startswith('P'): y_val = -0.5; name = name[1:]
        elif name.startswith('O'): y_val = -1.0; name = name[1:]
        elif name.startswith('T'): y_val = 0.0; name = name[1:]
        else: return None, None # 未知前缀，丢弃

        # 2. 解析 X 轴 (左右向矢状切面)
        x_val = None
        if name == 'Z': 
            x_val = 0.0  # 中轴线
        elif name.endswith('H'):
            # 10-5 过渡列 (如 1h, 2h)，它们位于标准列之间
            try:
                num = int(name[:-1])
                val = (num + 1) // 2 * 0.25 - 0.125
                x_val = -val if num % 2 != 0 else val # 奇数在左(负)，偶数在右(正)
            except: return None, None
        else:
            # 10-10 主干列 (如 1, 2, 3)
            try:
                num = int(name)
                val = (num + 1) // 2 * 0.25
                x_val = -val if num % 2 != 0 else val
            except: return None, None

        return x_val, y_val

    def _generate_2d_planar_layout(self):
        """核心魔法：生成节点并使用方圆映射 (Squircle Mapping)"""
        try:
            # 仅借用 MNE 内置的 10-5 字符串名字列表，不使用它的 3D 坐标
            montage = mne.channels.make_standard_montage('standard_1005')
            names = montage.ch_names
            
            for name in names:
                x, y = self._parse_1005_grid(name)
                if x is None or y is None: continue
                
                # 【约束 1】：彻底切除 T7/T8, Oz, Fpz 更外层的所有干扰节点 (脸部/颈部)
                if abs(x) > 1.0 or abs(y) > 1.0: continue
                
                # 【约束 2】：图形学绝技 - 方圆映射 (Squircle Mapping)。
                # 作用是将原本方形排布的网格，像橡皮筋一样平滑地撑成一个圆形。
                # 效果：保证 T7-Cz-T8 保持笔直，且 Fp1、Oz 等边缘点被完美锁在圆周(半径=1.0)上。
                x_circle = x * math.sqrt(1.0 - (y**2) / 2.0)
                y_circle = y * math.sqrt(1.0 - (x**2) / 2.0)
                
                # 保存坐标 (注意 Y 轴反转，让 Fp 鼻子端指向上方)
                self.all_nodes[name] = (x_circle, -y_circle)
                
            
        except ImportError:
            logger.error("未找到 MNE 库，请运行 pip install mne。")

    
    # ==========================================
    # 以下逻辑管理节点状态、智能编号(S1,D1)及通道
    # ==========================================
    def cycle_node_state(self, node_name: str):
        """、
        按 None -> Source -> Detector -> EEG -> None 顺序轮换。
        如果中间某个状态名额已满，自动跳过它，寻找下一个有空位的状态。
        """
        if node_name not in self.all_nodes: return
        
        current = self.selected_states.get(node_name, 'None')
        flow = ['None', 'Source', 'Detector', 'EEG']
        start_idx = flow.index(current)
        
        # 往后最多看 3 个状态
        for offset in range(1, 4):
            next_state = flow[(start_idx + offset) % 4]
            
            # None 状态没有数量限制，永远可以轮换到
            if next_state == 'None':
                self.set_node_state(node_name, 'None')
                return
                
            # 检查其它状态是否超限，如果不超限，就可以跳入这个状态
            current_count = sum(1 for s in self.selected_states.values() if s == next_state)
            if current_count < self.limits.get(next_state, 999):
                self.set_node_state(node_name, next_state)
                return
            
    def set_node_state(self, node_name: str, state: str, alias: str = None):
        """设置节点状态，并自动分配或回收别名"""
        if node_name not in self.all_nodes: return
        
        # 如果超限，不触发任何警告，直接静默 return，禁止增加。
        if state != 'None':
            current_count = sum(1 for s in self.selected_states.values() if s == state)
            if current_count >= self.limits.get(state, 999):
                return
        
        old_state = self.selected_states.get(node_name, 'None')
        if old_state != 'None':
            # 如果是从已选变成未选，必须先清理和它相关的通道黑名单
            if node_name in self.node_aliases:
                alias = self.node_aliases[node_name]
                self.blacklisted_channels = {c for c in self.blacklisted_channels if alias not in c}
                del self.node_aliases[node_name]
                
        if state == 'None':
            if node_name in self.selected_states:
                del self.selected_states[node_name]
        else:
            self.selected_states[node_name] = state
            # 自动分配连续且最小的序号
            if alias:
                self.node_aliases[node_name] = alias
            elif state == 'Source': self.node_aliases[node_name] = self._get_next_alias('S')
            elif state == 'Detector': self.node_aliases[node_name] = self._get_next_alias('D')
            elif state == 'EEG': self.node_aliases[node_name] = self._get_next_alias('E')
            
        self._calculate_channels()
        self.signal_selection_changed.emit()

    def _get_next_alias(self, prefix: str) -> str:
        """寻找当前前缀 (如 S, D, E) 下最小可用的连续数字序号"""
        existing_nums = []
        for alias in self.node_aliases.values():
            if alias.startswith(prefix):
                try: existing_nums.append(int(alias[len(prefix):]))
                except: pass
        i = 1
        while i in existing_nums: i += 1 # 填补空缺，保持连续
        return f"{prefix}{i}"

    def _calculate_channels(self):
        """根据距离阈值，自动将源和探测器两两配对成 fNIRS 通道"""
        self.valid_channels.clear()
        sources = [n for n, s in self.selected_states.items() if s == 'Source']
        detectors = [n for n, s in self.selected_states.items() if s == 'Detector']
        sources.sort(key=lambda n: self._alias_index(self.node_aliases.get(n, 'S0')))
        detectors.sort(key=lambda n: self._alias_index(self.node_aliases.get(n, 'D0')))
        
        for s in sources:
            for d in detectors:
                s_alias, d_alias = self.node_aliases[s], self.node_aliases[d]
                # 跳过被用户手动拉黑的连线
                if (s_alias, d_alias) in self.blacklisted_channels or (d_alias, s_alias) in self.blacklisted_channels:
                    continue
                # 计算两点距离，如果在阈值内则连线
                p1, p2 = self.all_nodes[s], self.all_nodes[d]
                dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                if dist <= self.channel_distance_threshold:
                    self.valid_channels.append((s, d))

    def _alias_index(self, alias: str) -> int:
        try:
            return int(alias[1:])
        except (TypeError, ValueError):
            return 0

    def toggle_channel_blacklist(self, source_alias: str, detector_alias: str, disable: bool):
        """添加或移除通道黑名单 (即 UI 上的右键断开/重连功能)"""
        pair = (source_alias, detector_alias)
        if disable: 
            self.blacklisted_channels.add(pair)
        else:
            self.blacklisted_channels.discard(pair)
            self.blacklisted_channels.discard((detector_alias, source_alias))
        self._calculate_channels()
        self.signal_selection_changed.emit()
        
    def set_limits(self, eeg=32, source=16, detector=16, emg=16):
        """由外部 UI 动态传入最新的通道数限制"""
        self.limits['EEG'] = eeg
        self.limits['Source'] = source
        self.limits['Detector'] = detector
        self.limits['EMG'] = emg

    def clear_all_selections(self):
        """一键清空画布上所有的电极和连线"""
        self.selected_states.clear()
        self.node_aliases.clear()
        self.valid_channels.clear()
        self.blacklisted_channels.clear()
        self.signal_selection_changed.emit()
        
    def get_fnirs_montage_dict(self):
        """导出 fNIRS 配置字典 (包含排序后的 S1/D1 编号、10-5真实名称及物理坐标)"""
        sources, detectors = {}, {}
        
        # 使用智能排序，保证导出字典按照 S1, S2, D1, D2 顺序排列
        def alias_sort_key(item):
            alias = item[1]
            prefix = alias[0] if alias else ''
            num = int(alias[1:]) if len(alias)>1 and alias[1:].isdigit() else 0
            return (prefix, num)
            
        sorted_items = sorted(self.node_aliases.items(), key=alias_sort_key)
        
        for name, alias in sorted_items:
            state = self.selected_states.get(name)
            coord = self.all_nodes.get(name)
            if state == 'Source':
                sources[alias] = {'standard_name': name, 'coord': coord}
            elif state == 'Detector':
                detectors[alias] = {'standard_name': name, 'coord': coord}
                
        channels = []
        for s_name, d_name in self.valid_channels:
            s_alias = self.node_aliases[s_name]
            d_alias = self.node_aliases[d_name]
            channels.append(f"{s_alias}-{d_alias}")
            
        return {
            'source_num': len(sources), 
            'detector_num': len(detectors),
            'sources': sources, 
            'detectors': detectors, 
            'fnirs_pairs': channels
        }

    def get_eeg_montage_dict(self):
        """导出 EEG 配置字典 (包含排序后的 E1-E32 编号、10-5真实名称及物理坐标)"""
        eeg_electrodes = {}
        
        def alias_sort_key(item):
            alias = item[1]
            prefix = alias[0] if alias else ''
            num = int(alias[1:]) if len(alias)>1 and alias[1:].isdigit() else 0
            return (prefix, num)
            
        sorted_items = sorted(self.node_aliases.items(), key=alias_sort_key)
        
        for name, alias in sorted_items:
            state = self.selected_states.get(name)
            if state == 'EEG':
                coord = self.all_nodes.get(name)
                eeg_electrodes[alias] = {'standard_name': name, 'coord': coord}
                
        return {
            'eeg_num': len(eeg_electrodes), 
            'eeg_channels': list(eeg_electrodes.keys()), 
            'eeg_details': eeg_electrodes
        }

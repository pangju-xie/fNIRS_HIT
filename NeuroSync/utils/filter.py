# physioSignal/signal_processor.py
import numpy as np
from scipy.signal import butter, sosfilt_zi, sosfilt, savgol_filter
import logging

logger = logging.getLogger(__name__)

class FilterState:
    """实时滤波状态缓存器"""
    def __init__(self, filter_type: str, **kwargs):
        self.filter_type = filter_type
        self.params = kwargs
        self.initialized = False
        self.sos = None
        self.zi = None
        
        # 针对平滑滤波的滑动窗口
        self.window_length = kwargs.get('window_length', 11)
        self.polyorder = kwargs.get('polyorder', 3)
        self.buffer = []

    def reset(self):
        self.initialized = False
        self.zi = None
        self.buffer.clear()

class SignalProcessor:
    """实时信号流处理器"""
    def __init__(self, sample_rate: float = 100.0, num_channels: int = 8):
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.nyquist_freq = sample_rate / 2.0
        self.filter_states = {} # {channel_idx: FilterState}
        

    def setup_online_filter(self, channel: int, filter_type: str, **params):
        """为特定通道装配滤波器 (自带强力参数防呆保护)"""
        
        # 1. 强制纠正填反的参数：保证 下限 < 上限
        if 'low_cutoff' in params and 'high_cutoff' in params:
            if params['low_cutoff'] >= params['high_cutoff']:
                # 如果填反了，自动交换它们
                params['low_cutoff'], params['high_cutoff'] = params['high_cutoff'], params['low_cutoff']
                
        # 2. 限制在奈奎斯特频率的安全范围内 (绝对禁止 Wn[0] >= Wn[1])
        if 'low_cutoff' in params: 
            params['low_cutoff'] = max(0.001, min(params['low_cutoff'], self.nyquist_freq * 0.95))
            
        if 'high_cutoff' in params: 
            # 保证上限绝对大于刚修正过的下限
            min_high = params.get('low_cutoff', 0.001) + 0.001
            params['high_cutoff'] = max(min_high, min(params['high_cutoff'], self.nyquist_freq * 0.99))
            
        # 3. S-G 滤波窗口强制奇数保护
        if 'window_length' in params and params['window_length'] % 2 == 0: 
            params['window_length'] += 1 
            
        self.filter_states[channel] = FilterState(filter_type, **params)

    def reset_online_filters(self, channel=None):
        if channel is not None and channel in self.filter_states:
            self.filter_states[channel].reset()
        else:
            for state in self.filter_states.values():
                state.reset()

    def process_sample_online(self, channel: int, sample: float) -> float:
        """单点实时滤波核心引擎"""
        if channel not in self.filter_states:
            return sample
            
        state = self.filter_states[channel]
        try:
            if state.filter_type in ['lowpass', 'highpass', 'bandpass']:
                return self._process_iir(state, sample)
            elif state.filter_type == 'sg':
                return self._process_sg(state, sample)
            return sample
        except Exception as e:
            # 容错：算炸了就原样输出，不要让软件崩溃
            logger.warning(f"Ch{channel} 滤波异常: {e}")
            return sample

    def _process_iir(self, state: FilterState, sample: float) -> float:
        
        if not state.initialized:
            order = state.params.get('order', 4)
            if state.filter_type == 'bandpass':
                low = state.params['low_cutoff'] / self.nyquist_freq
                high = state.params['high_cutoff'] / self.nyquist_freq
                state.sos = butter(order, [low, high], btype='bandpass', output='sos') # type: ignore
            elif state.filter_type == 'lowpass':
                cut = state.params['high_cutoff'] / self.nyquist_freq
                state.sos = butter(order, cut, btype='lowpass', output='sos')# type: ignore
            elif state.filter_type == 'highpass':
                cut = state.params['low_cutoff'] / self.nyquist_freq
                state.sos = butter(order, cut, btype='highpass', output='sos')# type: ignore
                
            state.zi = sosfilt_zi(state.sos) * sample# type: ignore
            state.initialized = True
            
        filtered, state.zi = sosfilt(state.sos, [sample], zi=state.zi)# type: ignore
        return float(filtered[0])

    def _process_sg(self, state: FilterState, sample: float) -> float:
        state.buffer.append(sample)
        if len(state.buffer) > state.window_length:
            state.buffer.pop(0)
            
        if len(state.buffer) == state.window_length:
            # 只有凑齐窗口长度才能算出有效的 SG 值
            filtered = savgol_filter(state.buffer, state.window_length, state.polyorder)
            return float(filtered[-1])
        return sample
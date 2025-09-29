# -*- coding: utf-8 -*-

"""
Signal Processing Module

This module provides comprehensive signal processing capabilities including
real-time (online) and batch (offline) filtering operations for multi-channel
physiological and optical signals.

Features:
- Online filtering for real-time data streams
- Offline filtering for recorded data analysis
- Multiple filter types: Savitzky-Golay, Butterworth, Moving Average
- Signal type conversions: Raw → Optical Density → Hemoglobin Concentration
- Robust error handling and parameter validation
"""

import numpy as np
from scipy import signal
from scipy.signal import savgol_filter, butter, filtfilt, sosfilt, sosfiltfilt
from collections import deque
import warnings
from typing import Union, Tuple, Optional, List, Dict, Any


class FilterState:
    """Maintains filter state for online filtering operations"""
    
    def __init__(self, filter_type: str, **kwargs):
        self.filter_type = filter_type
        self.params = kwargs
        self.initialized = False
        
        # State variables for different filter types
        self.zi = None  # Initial conditions for IIR filters
        self.buffer = np.array([])  # Ring buffer for moving average and S-G filters
        self.sos = None
        self.buffer_size = 0
        self.buffer_index = 0
        
    def reset(self):
        """Reset filter state"""
        self.initialized = False
        self.zi = None
        if self.buffer is not None:
            self.buffer.fill(0)
        self.buffer_index = 0


class SignalProcessor:
    """
    Comprehensive signal processing class supporting both online and offline filtering
    """
    
    def __init__(self, sample_rate: float = 100.0, num_channels: int = 8):
        """
        Initialize the signal processor
        
        Args:
            sample_rate: Sampling frequency in Hz
            num_channels: Number of signal channels
        """
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.nyquist_freq = sample_rate / 2.0
        
        # Online filter states for each channel
        self.online_filter_states: Dict[int, FilterState] = {}
        
        # Default parameters for different filter types
        self.default_params = {
            'sg': {'window_length': 11, 'polyorder': 3},
            'butterworth': {'low_cutoff': 0.1, 'high_cutoff': 10.0, 'order': 4, 'filter_type': 'bandpass'},
            'smooth': {'window_size': 5},
            'lowpass': {'cutoff': 10.0, 'order': 4},
            'highpass': {'cutoff': 0.1, 'order': 4}
        }
    
    def validate_filter_params(self, filter_type: str, **params) -> Dict[str, Any]:
        """
        Validate and sanitize filter parameters
        
        Args:
            filter_type: Type of filter ('sg', 'butterworth', 'smooth', etc.)
            **params: Filter parameters
            
        Returns:
            Dict of validated parameters
        """
        validated = self.default_params.get(filter_type, {}).copy()
        validated.update(params)
        
        if filter_type == 'sg':
            window_length = validated['window_length']
            polyorder = validated['polyorder']
            
            # Ensure window_length is odd
            if window_length % 2 == 0:
                window_length += 1
                validated['window_length'] = window_length
            
            # Ensure window_length > polyorder
            if window_length <= polyorder:
                validated['window_length'] = polyorder + 2
                if validated['window_length'] % 2 == 0:
                    validated['window_length'] += 1
                    
        elif filter_type in ['butterworth', 'lowpass', 'highpass']:
            # Validate frequency parameters
            if 'low_cutoff' in validated:
                validated['low_cutoff'] = max(0.001, min(validated['low_cutoff'], self.nyquist_freq * 0.99))
            if 'high_cutoff' in validated:
                validated['high_cutoff'] = max(0.001, min(validated['high_cutoff'], self.nyquist_freq * 0.99))
            if 'cutoff' in validated:
                validated['cutoff'] = max(0.001, min(validated['cutoff'], self.nyquist_freq * 0.99))
                
            # Ensure proper frequency ordering for bandpass
            if filter_type == 'butterworth' and validated.get('filter_type') == 'bandpass':
                low = validated['low_cutoff']
                high = validated['high_cutoff']
                if low >= high:
                    validated['low_cutoff'] = high * 0.1
                    
        elif filter_type == 'smooth':
            validated['window_size'] = max(1, validated['window_size'])
            
        return validated
    
    def setup_online_filter(self, channel: int, filter_type: str, **params):
        """
        Setup online filter for a specific channel
        
        Args:
            channel: Channel index
            filter_type: Type of filter
            **params: Filter parameters
        """
        validated_params = self.validate_filter_params(filter_type, **params)
        filter_state = FilterState(filter_type, **validated_params)
        
        # Pre-allocate buffers for filters that need them
        if filter_type == 'sg':
            filter_state.buffer_size = validated_params['window_length']
            filter_state.buffer = np.zeros(filter_state.buffer_size)
        elif filter_type == 'smooth':
            filter_state.buffer_size = validated_params['window_size']
            filter_state.buffer = np.zeros(filter_state.buffer_size)
            
        self.online_filter_states[channel] = filter_state
    
    def process_sample_online(self, channel: int, sample: float) -> float:
        """
        Process a single sample through the online filter
        
        Args:
            channel: Channel index
            sample: Input sample value
            
        Returns:
            Filtered sample value
        """
        if channel not in self.online_filter_states:
            return sample
            
        filter_state = self.online_filter_states[channel]
        filter_type = filter_state.filter_type
        params = filter_state.params
        
        try:
            if filter_type == 'sg':
                return self._process_sg_online(filter_state, sample)
            elif filter_type in ['butterworth', 'lowpass', 'highpass']:
                return self._process_iir_online(filter_state, sample)
            elif filter_type == 'smooth':
                return self._process_smooth_online(filter_state, sample)
            else:
                return sample
        except Exception as e:
            warnings.warn(f"Online filtering error for channel {channel}: {e}")
            return sample
    
    def _process_sg_online(self, filter_state: FilterState, sample: float) -> float:
        """Process sample through online Savitzky-Golay filter"""
        # Add sample to circular buffer
        filter_state.buffer[filter_state.buffer_index] = sample
        filter_state.buffer_index = (filter_state.buffer_index + 1) % filter_state.buffer_size
        
        if not filter_state.initialized:
            filter_state.initialized = True
            return sample
        
        # Apply S-G filter to buffer
        try:
            window_length = filter_state.params['window_length']
            polyorder = filter_state.params['polyorder']
            
            if len(filter_state.buffer) >= window_length:
                # Reorder buffer to get chronological order
                ordered_buffer = np.roll(filter_state.buffer, -filter_state.buffer_index)
                filtered = savgol_filter(ordered_buffer, window_length, polyorder)
                return filtered[-1]  # Return the most recent filtered sample
            else:
                return sample
        except Exception:
            return sample
    
    def _process_iir_online(self, filter_state: FilterState, sample: float) -> float:
        """Process sample through online IIR filter (Butterworth, etc.)"""
        params = filter_state.params
        
        if not filter_state.initialized:
            # Initialize filter coefficients and state
            try:
                if filter_state.filter_type == 'butterworth':
                    if params.get('filter_type') == 'bandpass':
                        sos = butter(params['order'], 
                                   [params['low_cutoff'] / self.nyquist_freq, 
                                    params['high_cutoff'] / self.nyquist_freq], 
                                   btype='band', output='sos')
                    elif params.get('filter_type') == 'lowpass':
                        sos = butter(params['order'], 
                                   params.get('cutoff', params['high_cutoff']) / self.nyquist_freq, 
                                   btype='low', output='sos')
                    else:  # Default to bandpass
                        sos = butter(params['order'], 
                                   [params['low_cutoff'] / self.nyquist_freq, 
                                    params['high_cutoff'] / self.nyquist_freq], 
                                   btype='band', output='sos')
                elif filter_state.filter_type == 'lowpass':
                    sos = butter(params['order'], 
                               params['cutoff'] / self.nyquist_freq, 
                               btype='low', output='sos')
                elif filter_state.filter_type == 'highpass':
                    sos = butter(params['order'], 
                               params['cutoff'] / self.nyquist_freq, 
                               btype='high', output='sos')
                else:
                    return sample
                    
                filter_state.sos = sos
                filter_state.zi = signal.sosfilt_zi(sos) * sample # type: ignore
                filter_state.initialized = True
                
            except Exception:
                return sample
        
        # Apply filter to single sample
        try:
            filtered_sample, filter_state.zi = signal.sosfilt( # type: ignore
                filter_state.sos, [sample], zi=filter_state.zi)
            return filtered_sample[0]
        except Exception:
            return sample
    
    def _process_smooth_online(self, filter_state: FilterState, sample: float) -> float:
        """Process sample through online moving average filter"""
        # Add sample to circular buffer
        filter_state.buffer[filter_state.buffer_index] = sample
        filter_state.buffer_index = (filter_state.buffer_index + 1) % filter_state.buffer_size
        
        if not filter_state.initialized:
            filter_state.initialized = True
        
        # Return moving average
        return np.mean(filter_state.buffer) # type: ignore
    
    def process_data_offline(self, data: np.ndarray, filter_type: str, **params) -> np.ndarray:
        """
        Apply offline filtering to data array
        
        Args:
            data: Input data array (1D or 2D with channels as columns)
            filter_type: Type of filter to apply
            **params: Filter parameters
            
        Returns:
            Filtered data array
        """
        if len(data) == 0:
            return data.copy()
            
        # Ensure data is 2D (samples x channels)
        if data.ndim == 1:
            data = data.reshape(-1, 1)
            
        validated_params = self.validate_filter_params(filter_type, **params)
        filtered_data = np.zeros_like(data)
        
        # Apply filter to each channel
        for ch in range(data.shape[1]):
            channel_data = data[:, ch]
            try:
                if filter_type == 'sg':
                    filtered_data[:, ch] = self._apply_sg_filter_offline(channel_data, validated_params)
                elif filter_type in ['butterworth', 'lowpass', 'highpass']:
                    filtered_data[:, ch] = self._apply_iir_filter_offline(channel_data, filter_type, validated_params)
                elif filter_type == 'smooth':
                    filtered_data[:, ch] = self._apply_smooth_filter_offline(channel_data, validated_params)
                else:
                    filtered_data[:, ch] = channel_data
            except Exception as e:
                warnings.warn(f"Offline filtering error for channel {ch}: {e}")
                filtered_data[:, ch] = channel_data
                
        return filtered_data.squeeze() if data.shape[1] == 1 else filtered_data
    
    def _apply_sg_filter_offline(self, data: np.ndarray, params: Dict) -> np.ndarray:
        """Apply Savitzky-Golay filter offline"""
        window_length = params['window_length']
        polyorder = params['polyorder']
        
        if len(data) < window_length:
            return data.copy()
            
        return savgol_filter(data, window_length, polyorder)
    
    def _apply_iir_filter_offline(self, data: np.ndarray, filter_type: str, params: Dict) -> np.ndarray:
        """Apply IIR filter offline"""
        if len(data) < params['order'] * 3:
            return data.copy()
            
        try:
            if filter_type == 'butterworth':
                if params.get('filter_type') == 'bandpass':
                    sos = butter(params['order'], 
                               [params['low_cutoff'] / self.nyquist_freq, 
                                params['high_cutoff'] / self.nyquist_freq], 
                               btype='band', output='sos')
                elif params.get('filter_type') == 'lowpass':
                    sos = butter(params['order'], 
                               params.get('cutoff', params['high_cutoff']) / self.nyquist_freq, 
                               btype='low', output='sos')
                else:  # Default bandpass
                    sos = butter(params['order'], 
                               [params['low_cutoff'] / self.nyquist_freq, 
                                params['high_cutoff'] / self.nyquist_freq], 
                               btype='band', output='sos')
            elif filter_type == 'lowpass':
                sos = butter(params['order'], 
                           params['cutoff'] / self.nyquist_freq, 
                           btype='low', output='sos')
            elif filter_type == 'highpass':
                sos = butter(params['order'], 
                           params['cutoff'] / self.nyquist_freq, 
                           btype='high', output='sos')
            else:
                return data.copy()
                
            return sosfiltfilt(sos, data)
        except Exception:
            return data.copy()
    
    def _apply_smooth_filter_offline(self, data: np.ndarray, params: Dict) -> np.ndarray:
        """Apply moving average filter offline"""
        window_size = params['window_size']
        if len(data) < window_size:
            return data.copy()
        return np.convolve(data, np.ones(window_size)/window_size, mode='same')
    
    def convert_to_optical_density(self, raw_data: np.ndarray, reference: Optional[float] = None) -> np.ndarray:
        """
        Convert raw light intensity to optical density using Beer-Lambert law
        
        Args:
            raw_data: Raw intensity data
            reference: Reference intensity (if None, uses mean of first 100 samples)
            
        Returns:
            Optical density data
        """
        if reference is None:
            if len(raw_data) > 100:
                if raw_data.ndim == 1:
                    reference = np.mean(raw_data[:100])
                else:
                    reference = np.mean(raw_data[:100], axis=0)
            else:
                if raw_data.ndim == 1:
                    reference = np.mean(raw_data)
                else:
                    reference = np.mean(raw_data, axis=0)
        
        # Avoid log(0) by adding small epsilon
        epsilon = 1e-10
        raw_data_safe = np.maximum(raw_data, epsilon)
        reference_safe = np.maximum(reference, epsilon)
        
        od = -np.log10(raw_data_safe / reference_safe)
        return od
    
    def convert_to_hemoglobin(self, od_data: np.ndarray, pathlength: float = 3.0, 
                            extinction_coeff: float = 2.3) -> np.ndarray:
        """
        Convert optical density to hemoglobin concentration using Beer-Lambert law
        
        Args:
            od_data: Optical density data
            pathlength: Optical path length in cm
            extinction_coeff: Extinction coefficient in cm⁻¹·mM⁻¹
            
        Returns:
            Hemoglobin concentration in µM
        """
        # Simplified Beer-Lambert law: C = OD / (ε * L)
        concentration = od_data / (extinction_coeff * pathlength)
        return concentration * 1000  # Convert to µM
    
    def reset_online_filters(self, channel: Optional[int] = None):
        """
        Reset online filter states
        
        Args:
            channel: Specific channel to reset (if None, resets all channels)
        """
        if channel is not None:
            if channel in self.online_filter_states:
                self.online_filter_states[channel].reset()
        else:
            for filter_state in self.online_filter_states.values():
                filter_state.reset()
    
    def get_filter_info(self, channel: int) -> Dict[str, Any]:
        """
        Get information about the filter setup for a channel
        
        Args:
            channel: Channel index
            
        Returns:
            Dictionary with filter information
        """
        if channel not in self.online_filter_states:
            return {'filter_type': 'none', 'initialized': False}
            
        filter_state = self.online_filter_states[channel]
        return {
            'filter_type': filter_state.filter_type,
            'params': filter_state.params,
            'initialized': filter_state.initialized
        }
    
    def apply_multiple_filters_offline(self, data: np.ndarray, filter_chain: List[Tuple[str, Dict]]) -> np.ndarray:
        """
        Apply multiple filters in sequence (offline processing)
        
        Args:
            data: Input data
            filter_chain: List of (filter_type, params) tuples
            
        Returns:
            Data after applying all filters in sequence
        """
        result = data.copy()
        for filter_type, params in filter_chain:
            result = self.process_data_offline(result, filter_type, **params)
        return result
    
    def get_filter_frequency_response(self, filter_type: str, **params) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get frequency response of a filter
        
        Args:
            filter_type: Type of filter
            **params: Filter parameters
            
        Returns:
            Tuple of (frequencies, magnitude_response)
        """
        validated_params = self.validate_filter_params(filter_type, **params)
        
        # Generate frequency vector
        freqs = np.logspace(-2, np.log10(self.nyquist_freq), 1000)
        
        if filter_type == 'butterworth':
            if validated_params.get('filter_type') == 'bandpass':
                sos = butter(validated_params['order'], 
                           [validated_params['low_cutoff'] / self.nyquist_freq, 
                            validated_params['high_cutoff'] / self.nyquist_freq], 
                           btype='band', output='sos')
            else:
                sos = butter(validated_params['order'], 
                           [validated_params['low_cutoff'] / self.nyquist_freq, 
                            validated_params['high_cutoff'] / self.nyquist_freq], 
                           btype='band', output='sos')
            w, h = signal.sosfreqz(sos, worN=freqs, fs=self.sample_rate)
            return w, np.abs(h)
        elif filter_type in ['lowpass', 'highpass']:
            btype = 'low' if filter_type == 'lowpass' else 'high'
            sos = butter(validated_params['order'], 
                       validated_params['cutoff'] / self.nyquist_freq, 
                       btype=btype, output='sos')
            w, h = signal.sosfreqz(sos, worN=freqs, fs=self.sample_rate)
            return w, np.abs(h)
        else:
            # For non-frequency domain filters, return flat response
            return freqs, np.ones_like(freqs)


# Factory function for easy instantiation
def create_signal_processor(sample_rate: float = 100.0, num_channels: int = 8) -> SignalProcessor:
    """
    Create a SignalProcessor instance with specified parameters
    
    Args:
        sample_rate: Sampling frequency in Hz
        num_channels: Number of signal channels
        
    Returns:
        SignalProcessor instance
    """
    return SignalProcessor(sample_rate=sample_rate, num_channels=num_channels)
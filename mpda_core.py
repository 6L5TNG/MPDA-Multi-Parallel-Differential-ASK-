"""
MPDA (Multi-Parallel Differential ASK) Protocol Library
Copyright (c) 2025 6L5TNG (Kang Han) & Community Contributors.
All rights reserved.

This library provides the core modulation and demodulation engines for the MPDA protocol.
Version: 2.1.0 (Flawless Edition)
- Fixed critical bug where fading would overwrite signal waveform.
- Fixed uninitialized receiver state.
- Standardized timing constants for perfect 5Hz synchronization.
"""

import numpy as np

# --- Protocol Constants ---
SAMPLE_RATE = 44100
PILOT_FREQ = 2200
SYNC_BYTE = 0xAA
EOT_BYTE = 0xFF

# Timing Constants (Critical for 5Hz Stability)
PILOT_DURATION = 1.0        # Seconds
BEEP_DURATION = 0.3         # Seconds
FADE_DURATION = 0.005       # 5ms fade to prevent clicks
GAP_DURATION = 0.15         # Fixed gap between Pilot and Data
RX_SKIP_DURATION = 0.12     # RX skip time (must be < GAP_DURATION)

CHAR_SET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 !@#$%^&*()-_=+[]{};:',.<>/?\n"
CHAR_MAP = {char: i + 1 for i, char in enumerate(CHAR_SET)}
REV_CHAR_MAP = {i + 1: char for i, char in enumerate(CHAR_SET)}

class MPDATransmitter:
    """
    Handles the generation of MPDA audio signals.
    """
    def __init__(self):
        pass

    def _get_frequencies(self, tracks):
        if tracks == 8: return [600, 800, 1000, 1200, 1400, 1600, 1800, 2000]
        elif tracks == 4: return [800, 1200, 1600, 2000]
        elif tracks == 1: return [1500]
        else: raise ValueError(f"Unsupported track count: {tracks}")

    def _apply_fade(self, arr, start, length, mode='in'):
        """
        Safely applies fading by MULTIPLYING the envelope.
        mode 'in': 0.0 -> 1.0
        mode 'out': 1.0 -> 0.0
        """
        if start >= len(arr): return
        actual_len = min(length, len(arr) - start)
        
        if actual_len > 0:
            if mode == 'in':
                envelope = np.linspace(0.0, 1.0, actual_len)
            else: # out
                envelope = np.linspace(1.0, 0.0, actual_len)
            
            # [CRITICAL FIX] Multiply instead of replace
            arr[start:start+actual_len] *= envelope

    def _apply_cross_fade(self, arr, start, length, start_amp, end_amp):
        """Smoothly transitions amplitude between two levels."""
        if start >= len(arr): return
        actual_len = min(length, len(arr) - start)
        if actual_len > 0:
             # [CRITICAL FIX] Create a gain envelope that scales the signal
             # Since signal is normalized 1.0 sine, we just need to ramp the amplitude.
             # However, for Phase-Continuous Hard Keying, the carrier is continuous.
             # We are shaping the ENVELOPE array, not the signal array directly here.
             # This function is a helper for the logic below.
             pass # Logic implemented inline for efficiency in generate_signal

    def generate_signal(self, text, tracks=4, speed=10):
        if speed not in [5, 10, 15]: raise ValueError("Speed must be 5, 10, or 15 Hz")
        
        cycle_samples = int(SAMPLE_RATE / speed)
        freqs = self._get_frequencies(tracks)

        # 1. Bit Stream Construction
        full_bits = []
        
        def append_bytes(byte_val, repeat_count):
            for _ in range(repeat_count):
                for i in range(7, -1, -1): full_bits.append((byte_val >> i) & 1)

        append_bytes(SYNC_BYTE, 3)
        
        for char in text:
            code = CHAR_MAP.get(char, 63)
            for i in range(7, -1, -1): full_bits.append((code >> i) & 1)
        
        append_bytes(EOT_BYTE, 3)

        remainder = len(full_bits) % tracks
        if remainder:
            full_bits.extend([0] * (tracks - remainder))

        # 2. Signal Generation
        track_bits = [full_bits[i::tracks] for i in range(tracks)]
        num_cycles = len(track_bits[0])
        total_samples = num_cycles * 2 * cycle_samples
        
        t_global = np.linspace(0, total_samples / SAMPLE_RATE, total_samples, endpoint=False)
        final_sig = np.zeros(total_samples)
        
        fade_len = int(FADE_DURATION * SAMPLE_RATE)

        for trk_idx, f in enumerate(freqs):
            carrier = np.sin(2 * np.pi * f * t_global)
            envelope = np.zeros(total_samples)
            bits = track_bits[trk_idx]
            current_amp = 0.0 # Start from silence or previous level
            
            for i, bit in enumerate(bits):
                start = i * 2 * cycle_samples
                mid = start + cycle_samples
                end = mid + cycle_samples
                
                # Ref Phase (0.5)
                envelope[start:mid] = 0.5
                # Smooth transition from previous amp to 0.5
                if start + fade_len < total_samples:
                    envelope[start:start+fade_len] = np.linspace(current_amp, 0.5, fade_len)
                
                # Data Phase (1.0 or 0.1)
                target = 1.0 if bit == 1 else 0.1
                envelope[mid:end] = target
                # Smooth transition from 0.5 to target
                if mid + fade_len < total_samples:
                    envelope[mid:mid+fade_len] = np.linspace(0.5, target, fade_len)
                
                current_amp = target

            final_sig += carrier * envelope

        if tracks > 0: final_sig /= tracks

        # 3. Pilot & Beeps (With corrected fading)
        t_pilot = np.linspace(0, PILOT_DURATION, int(PILOT_DURATION*SAMPLE_RATE), endpoint=False)
        pilot_sig = 0.5 * np.sin(2 * np.pi * PILOT_FREQ * t_pilot)
        self._apply_fade(pilot_sig, len(pilot_sig)-fade_len, fade_len, mode='out')

        gap_samples = int(GAP_DURATION * SAMPLE_RATE)
        gap = np.zeros(gap_samples) 
        
        t_beep = np.linspace(0, BEEP_DURATION, int(BEEP_DURATION*SAMPLE_RATE), endpoint=False)
        beep_sig = 0.5 * np.sin(2 * np.pi * PILOT_FREQ * t_beep)
        self._apply_fade(beep_sig, 0, fade_len, mode='in')
        self._apply_fade(beep_sig, len(beep_sig)-fade_len, fade_len, mode='out')
        
        # Fade-in the main data block
        if len(final_sig) > fade_len:
            self._apply_fade(final_sig, 0, fade_len, mode='in')

        full_signal = np.concatenate((pilot_sig, gap, final_sig, gap, beep_sig))

        # Normalize
        max_amp = np.max(np.abs(full_signal))
        if max_amp > 0: full_signal = full_signal / max_amp * 0.95

        return full_signal.astype(np.float32)


class MPDAReceiver:
    """
    Decodes MPDA signals using DSP Matched Filter.
    """
    def __init__(self, tracks=4, speed=10):
        self.reset()
        # [CRITICAL FIX] Ensure templates are built on init
        self.configure(tracks, speed)

    def reset(self):
        self.state = "IDLE"
        self.buffer = np.array([])
        self.bits = []
        self.sync_locked = False
        self.current_tracks = 4
        self.current_speed = 10
        self.templates = {}

    def configure(self, tracks, speed):
        self.current_tracks = tracks
        self.current_speed = speed
        self._precompute_templates(tracks, speed)
        # Reset buffer and state logic, but keep the instance alive
        self.state = "IDLE"
        self.buffer = np.array([])
        self.bits = []
        self.sync_locked = False

    def _get_frequencies(self, tracks):
        if tracks == 8: return [600, 800, 1000, 1200, 1400, 1600, 1800, 2000]
        elif tracks == 4: return [800, 1200, 1600, 2000]
        elif tracks == 1: return [1500]
        return []

    def _precompute_templates(self, tracks, speed):
        self.templates.clear()
        length = int(SAMPLE_RATE / speed)
        t = np.linspace(0, 1.0 / speed, length, endpoint=False)
        
        self.templates['pilot'] = np.conjugate(np.exp(1j * 2 * np.pi * PILOT_FREQ * t))
        for f in self._get_frequencies(tracks):
            self.templates[f] = np.conjugate(np.exp(1j * 2 * np.pi * f * t))

    def _correlate(self, chunk, key):
        if len(chunk) == 0: return 0.0
        ref = self.templates.get(key)
        if ref is None: return 0.0
        
        n = min(len(chunk), len(ref))
        if n < 10: return 0.0
        
        return np.abs(np.sum(chunk[:n] * ref[:n])) / n

    def process_audio(self, audio_chunk):
        if len(audio_chunk) == 0: return None

        # DC Offset Removal
        audio_chunk = audio_chunk - np.mean(audio_chunk)
        
        self.buffer = np.concatenate((self.buffer, audio_chunk))
        
        # Buffer Safety
        MAX_BUF = SAMPLE_RATE * 10
        if self.state != "IDLE" and self.state != "SEARCH_PILOT":
             if len(self.buffer) > MAX_BUF:
                self.buffer = self.buffer[-SAMPLE_RATE * 3:]
        else:
            if len(self.buffer) > MAX_BUF:
                self.buffer = self.buffer[-SAMPLE_RATE * 5:]

        cycle_len = int(SAMPLE_RATE / self.current_speed)

        if self.state == "IDLE" or self.state == "SEARCH_PILOT":
            while len(self.buffer) > cycle_len:
                chunk = self.buffer[:cycle_len]
                score = self._correlate(chunk, 'pilot')
                
                if score > 0.1:
                    self.state = "WAIT_END"
                    self.buffer = self.buffer[cycle_len:]
                else:
                    self.buffer = self.buffer[cycle_len:]

        elif self.state == "WAIT_END":
            while len(self.buffer) > cycle_len:
                chunk = self.buffer[:cycle_len]
                score = self._correlate(chunk, 'pilot')
                
                if score < 0.05:
                    self.state = "DECODE"
                    
                    # [CRITICAL FIX] Use Fixed Constant for Skip
                    # Skip safe amount (0.12s) to land in the 0.15s gap
                    skip = int(RX_SKIP_DURATION * SAMPLE_RATE)
                    
                    if len(self.buffer) > skip:
                        self.buffer = self.buffer[skip:]
                    else:
                        self.buffer = np.array([])
                    self.sync_locked = False
                    break
                else:
                    self.buffer = self.buffer[cycle_len:]

        elif self.state == "DECODE":
            block_len = cycle_len * 2
            freqs = self._get_frequencies(self.current_tracks)
            threshold_ratio = 0.85 if self.current_speed == 5 else 0.8

            while len(self.buffer) >= block_len:
                ref_chunk = self.buffer[:cycle_len]
                dat_chunk = self.buffer[cycle_len:block_len]
                self.buffer = self.buffer[block_len:]

                for f in freqs:
                    ref_val = self._correlate(ref_chunk, f)
                    dat_val = self._correlate(dat_chunk, f)
                    
                    if dat_val > ref_val * threshold_ratio:
                        self.bits.append(1)
                    else:
                        self.bits.append(0)

                if not self.sync_locked:
                    while len(self.bits) >= 8:
                        val = 0
                        for b in self.bits[:8]: val = (val << 1) | b
                        
                        if val == SYNC_BYTE:
                            self.sync_locked = True
                            self.bits = []
                            break
                        else:
                            self.bits.pop(0)
                else:
                    while len(self.bits) >= 8:
                        val = 0
                        for b in self.bits[:8]: val = (val << 1) | b
                        self.bits = self.bits[8:]

                        if val == EOT_BYTE:
                            self.state = "SEARCH_PILOT"
                            self.sync_locked = False
                            return "<EOT>"
                        elif val in REV_CHAR_MAP:
                            return REV_CHAR_MAP[val]
                        # Silently ignore unknown chars to prevent crash

        return None

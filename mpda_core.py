"""
MPDA (Multi-Parallel Differential ASK) Protocol Library
Copyright (c) 2025 6L5TNG (Kang Han) & Community Contributors.
All rights reserved.

This library provides the core modulation and demodulation engines for the MPDA protocol.
Designed for extreme robustness in low-bandwidth, high-noise environments.

Version: 2.0.0 (Ultimate Stable)
- "Survives without Internet" Edition
- Full 5Hz/8-Track synchronization fix
- Adaptive DC offset removal & Safe fading algorithms
"""

import numpy as np

# --- Protocol Constants ---
SAMPLE_RATE = 44100
PILOT_FREQ = 2200
SYNC_BYTE = 0xAA
EOT_BYTE = 0xFF
CHAR_SET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 !@#$%^&*()-_=+[]{};:',.<>/?\n"
CHAR_MAP = {char: i + 1 for i, char in enumerate(CHAR_SET)}
REV_CHAR_MAP = {i + 1: char for i, char in enumerate(CHAR_SET)}

class MPDATransmitter:
    """
    Handles the generation of MPDA audio signals.
    Features: Phase-Continuous Hard Keying, Micro-Fade Anti-Click, Robust Padding.
    """
    def __init__(self):
        pass

    def _get_frequencies(self, tracks):
        if tracks == 8: return [600, 800, 1000, 1200, 1400, 1600, 1800, 2000]
        elif tracks == 4: return [800, 1200, 1600, 2000]
        elif tracks == 1: return [1500]
        else: raise ValueError(f"Unsupported track count: {tracks}")

    def _safe_fade(self, arr, start, length, start_val, end_val):
        """Safely applies fading without array bounds errors."""
        if start >= len(arr): return
        actual_len = min(length, len(arr) - start)
        if actual_len > 0:
            arr[start:start+actual_len] = np.linspace(start_val, end_val, actual_len)

    def generate_signal(self, text, tracks=4, speed=10):
        if speed not in [5, 10, 15]: raise ValueError("Speed must be 5, 10, or 15 Hz")
        
        cycle_samples = int(SAMPLE_RATE / speed)
        freqs = self._get_frequencies(tracks)

        # 1. Bit Stream Construction
        full_bits = []
        
        # Helper for byte insertion
        def append_bytes(byte_val, repeat_count):
            for _ in range(repeat_count):
                for i in range(7, -1, -1): full_bits.append((byte_val >> i) & 1)

        # Preamble (Sync)
        append_bytes(SYNC_BYTE, 3)
        
        # Payload
        for char in text:
            code = CHAR_MAP.get(char, 63)
            for i in range(7, -1, -1): full_bits.append((code >> i) & 1)
        
        # Postamble (EOT)
        append_bytes(EOT_BYTE, 3)

        # Global Padding (Robust alignment)
        remainder = len(full_bits) % tracks
        if remainder:
            full_bits.extend([0] * (tracks - remainder))

        # 2. Signal Generation
        track_bits = [full_bits[i::tracks] for i in range(tracks)]
        num_cycles = len(track_bits[0])
        total_samples = num_cycles * 2 * cycle_samples
        
        t_global = np.linspace(0, total_samples / SAMPLE_RATE, total_samples, endpoint=False)
        final_sig = np.zeros(total_samples)
        
        fade_len = int(0.005 * SAMPLE_RATE)

        for trk_idx, f in enumerate(freqs):
            carrier = np.sin(2 * np.pi * f * t_global)
            envelope = np.zeros(total_samples)
            bits = track_bits[trk_idx]
            current_amp = 0.0
            
            for i, bit in enumerate(bits):
                start = i * 2 * cycle_samples
                mid = start + cycle_samples
                end = mid + cycle_samples
                
                # Ref Phase (0.5)
                envelope[start:mid] = 0.5
                self._safe_fade(envelope, start, fade_len, current_amp, 0.5)
                
                # Data Phase (1.0 or 0.1)
                target = 1.0 if bit == 1 else 0.1
                envelope[mid:end] = target
                self._safe_fade(envelope, mid, fade_len, 0.5, target)
                
                current_amp = target

            final_sig += carrier * envelope

        if tracks > 0: final_sig /= tracks

        # 3. Pilot & Beeps (Standardized 0.15s Gap for 5Hz stability)
        t_pilot = np.linspace(0, 1.0, SAMPLE_RATE, endpoint=False)
        pilot_sig = 0.5 * np.sin(2 * np.pi * PILOT_FREQ * t_pilot)
        self._safe_fade(pilot_sig, len(pilot_sig)-fade_len, fade_len, 1.0, 0.0)

        gap = np.zeros(int(0.15 * SAMPLE_RATE)) 
        
        t_beep = np.linspace(0, 0.3, int(0.3 * SAMPLE_RATE), endpoint=False)
        beep_sig = 0.5 * np.sin(2 * np.pi * PILOT_FREQ * t_beep)
        self._safe_fade(beep_sig, 0, fade_len, 0.0, 1.0)
        self._safe_fade(beep_sig, len(beep_sig)-fade_len, fade_len, 1.0, 0.0)
        
        if len(final_sig) > fade_len:
            self._safe_fade(final_sig, 0, fade_len, 0.0, 1.0)

        full_signal = np.concatenate((pilot_sig, gap, final_sig, gap, beep_sig))

        # Normalize (Headroom -1dB)
        max_amp = np.max(np.abs(full_signal))
        if max_amp > 0: full_signal = full_signal / max_amp * 0.95

        return full_signal.astype(np.float32)


class MPDAReceiver:
    """
    Decodes MPDA signals using DSP Matched Filter.
    Optimized for real-world acoustic coupling (Speaker-to-Mic).
    """
    def __init__(self):
        self.reset()

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
        # Reset buffer but keep settings
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
        
        # Pre-conjugate for fast correlation
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
        """Main processing pipeline. Returns decoded char or None."""
        if len(audio_chunk) == 0: return None

        # DC Offset Removal (Essential for phone lines / cheap mics)
        audio_chunk = audio_chunk - np.mean(audio_chunk)
        
        self.buffer = np.concatenate((self.buffer, audio_chunk))
        
        # Intelligent Buffer Management
        MAX_BUF = SAMPLE_RATE * 10
        if self.state == "DECODE":
             # Keep strictly required buffer during decode to avoid lag
             if len(self.buffer) > MAX_BUF:
                self.buffer = self.buffer[-SAMPLE_RATE * 3:]
        else:
            # Keep longer history while searching for pilot
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
                
                if score < 0.05: # Pilot End Detected
                    self.state = "DECODE"
                    
                    # Gap Skip Logic (Safe for 5Hz)
                    # TX Gap is 0.15s. Skip 0.12s to safely land in the silence without eating Data.
                    skip = int(0.12 * SAMPLE_RATE)
                    
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
            
            # Adaptive Threshold
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
                    # Sync Search
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
                    # Character Decode
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
                        # Ignore unknown/noise

        return None

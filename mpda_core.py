"""
MPDA (Multi-Parallel Differential ASK) Protocol Library
Copyright (c) 2024 6L5TNG (Kang Han). All rights reserved.

This library provides the core modulation and demodulation engines for the MPDA protocol,
designed for robust text communication over HF/VHF amateur radio bands.

Protocol Specification:
- Modulation: Audio Frequency Shift Keying (AFSK) based Multi-tone
- Mode: Multi-Parallel Differential Amplitude Shift Keying
- Tracks: 1, 4, or 8 parallel tones
- Speed: 5, 10, 15 Hz (Symbol Rate)
- Error Detection: Correlation-based Matched Filter
"""

import numpy as np

# --- Protocol Constants ---
SAMPLE_RATE = 44100
PILOT_FREQ = 2200
SYNC_BYTE = 0xAA
EOT_BYTE = 0xFF  # End of Transmission
CHAR_SET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 !@#$%^&*()-_=+[]{};:',.<>/?\n"
CHAR_MAP = {char: i + 1 for i, char in enumerate(CHAR_SET)}
REV_CHAR_MAP = {i + 1: char for i, char in enumerate(CHAR_SET)}

class MPDATransmitter:
    """
    Handles the generation of MPDA audio signals from text data.
    Implements Phase-Continuous Hard Keying for maximum signal clarity.
    """

    def __init__(self):
        pass

    def _get_frequencies(self, tracks):
        if tracks == 8:
            return [600, 800, 1000, 1200, 1400, 1600, 1800, 2000]
        elif tracks == 4:
            return [800, 1200, 1600, 2000]
        elif tracks == 1:
            return [1500]
        else:
            raise ValueError("MPDA supports only 1, 4, or 8 tracks.")

    def generate_signal(self, text, tracks=4, speed=10):
        """
        Generates a raw PCM audio signal for the given text.
        
        Args:
            text (str): The message to send.
            tracks (int): Number of parallel tones (1, 4, 8).
            speed (int): Symbol rate in Hz (5, 10, 15).

        Returns:
            np.array: Floating point audio samples (-1.0 to 1.0).
        """
        cycle_samples = int(SAMPLE_RATE / speed)
        freqs = self._get_frequencies(tracks)

        # 1. Construct Bit Stream
        full_bits = []
        
        # Preamble (Sync)
        for _ in range(3):
            for i in range(7, -1, -1):
                full_bits.append((SYNC_BYTE >> i) & 1)
        
        # Payload
        for char in text:
            code = CHAR_MAP.get(char, 63) # Default to '?' if unknown
            for i in range(7, -1, -1):
                full_bits.append((code >> i) & 1)
        
        # Postamble (End of Transmission)
        for _ in range(3):
            for i in range(7, -1, -1):
                full_bits.append((EOT_BYTE >> i) & 1)

        # Padding
        remainder = len(full_bits) % tracks
        if remainder:
            full_bits.extend([0] * (tracks - remainder))

        # 2. Parallel Mapping
        track_bits = [full_bits[i::tracks] for i in range(tracks)]
        num_cycles = len(track_bits[0])
        total_samples = num_cycles * 2 * cycle_samples
        
        # 3. Signal Generation (Phase Continuous)
        t_global = np.linspace(0, total_samples / SAMPLE_RATE, total_samples, endpoint=False)
        final_sig = np.zeros(total_samples)

        # Tuning: Apply 5ms micro-fade to prevent audible clicks while maintaining sharpness
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
                
                # Reference Phase (0.5)
                envelope[start:mid] = 0.5
                if start + fade_len < total_samples:
                    envelope[start:start+fade_len] = np.linspace(current_amp, 0.5, fade_len)
                
                # Data Phase (1.0 or 0.1)
                target = 1.0 if bit == 1 else 0.1
                envelope[mid:end] = target
                if mid + fade_len < total_samples:
                    envelope[mid:mid+fade_len] = np.linspace(0.5, target, fade_len)
                
                current_amp = target

            final_sig += carrier * envelope

        if tracks > 0:
            final_sig /= tracks

        # 4. Add Pilot Tone and Beeps with smooth transitions
        t_pilot = np.linspace(0, 1.0, SAMPLE_RATE, endpoint=False)
        pilot_sig = 0.5 * np.sin(2 * np.pi * PILOT_FREQ * t_pilot)
        pilot_sig[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)

        gap = np.zeros(int(0.1 * SAMPLE_RATE))
        
        t_beep = np.linspace(0, 0.3, int(0.3 * SAMPLE_RATE), endpoint=False)
        beep_sig = 0.5 * np.sin(2 * np.pi * PILOT_FREQ * t_beep)
        beep_sig[:fade_len] *= np.linspace(0.0, 1.0, fade_len)
        beep_sig[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)
        
        if len(final_sig) > fade_len:
            final_sig[:fade_len] *= np.linspace(0.0, 1.0, fade_len)

        full_signal = np.concatenate((pilot_sig, gap, final_sig, gap, beep_sig))

        # Normalize
        max_amp = np.max(np.abs(full_signal))
        if max_amp > 0:
            full_signal = full_signal / max_amp * 0.95

        return full_signal.astype(np.float32)


class MPDAReceiver:
    """
    Decodes MPDA audio signals.
    Uses Matched Filter (Correlation) with adaptive thresholding.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Resets the internal state of the decoder."""
        self.state = "IDLE"
        self.buffer = np.array([])
        self.bits = []
        self.sync_locked = False
        self.templates = {}
        self.current_tracks = 4
        self.current_speed = 10

    def configure(self, tracks, speed):
        """
        Configures the decoder parameters.
        Must be called before processing audio or when changing modes.
        """
        self.current_tracks = tracks
        self.current_speed = speed
        self._precompute_templates(tracks, speed)
        self.reset() # Clear buffer on config change

    def _get_frequencies(self, tracks):
        if tracks == 8:
            return [600, 800, 1000, 1200, 1400, 1600, 1800, 2000]
        elif tracks == 4:
            return [800, 1200, 1600, 2000]
        elif tracks == 1:
            return [1500]
        return []

    def _precompute_templates(self, tracks, speed):
        """
        Generates complex reference templates for correlation.
        Clears existing templates to prevent mode conflict.
        """
        self.templates.clear() # Crucial for switching between 1/4/8 tracks
        
        length = int(SAMPLE_RATE / speed)
        t = np.linspace(0, 1.0 / speed, length, endpoint=False)
        
        # Pilot Template
        self.templates['pilot'] = np.exp(1j * 2 * np.pi * PILOT_FREQ * t)
        
        # Data Frequency Templates
        for f in self._get_frequencies(tracks):
            self.templates[f] = np.exp(1j * 2 * np.pi * f * t)

    def _correlate(self, chunk, key):
        """Calculates the normalized correlation coefficient."""
        if len(chunk) == 0: return 0.0
        
        ref = self.templates.get(key)
        if ref is None: return 0.0
        
        n = min(len(chunk), len(ref))
        if n < 10: return 0.0
        
        # Complex dot product for phase-invariant energy detection
        return np.abs(np.vdot(chunk[:n], ref[:n])) / n

    def process_audio(self, audio_chunk):
        """
        Ingests an audio chunk and performs decoding.
        
        Args:
            audio_chunk (np.array): Incoming audio samples (mono).

        Returns:
            str: Decoded character if available, otherwise None.
        """
        self.buffer = np.concatenate((self.buffer, audio_chunk))
        
        # Buffer overflow protection
        if len(self.buffer) > SAMPLE_RATE * 10:
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
                    
                    # Gap optimization for 5Hz (longer cycle needs shorter skip)
                    gap_ratio = 0.1 if self.current_speed == 5 else 0.2
                    skip = int(gap_ratio * SAMPLE_RATE)
                    
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
            
            # Adaptive thresholding for 5Hz (higher energy needs stricter check)
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
                    # Search for Sync Byte (0xAA)
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
                    # Decode Characters
                    while len(self.bits) >= 8:
                        val = 0
                        for b in self.bits[:8]: val = (val << 1) | b
                        self.bits = self.bits[8:]

                        if val == EOT_BYTE:
                            self.state = "SEARCH_PILOT"
                            self.sync_locked = False
                            return "<EOT>" # Indicator for End of Transmission
                        elif val in REV_CHAR_MAP:
                            return REV_CHAR_MAP[val]

        return None

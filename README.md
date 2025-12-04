# MPDA (Multi-Parallel Intra-Symbol Differential ASK) Protocol

**MPDA** is a robust, narrowband digital communication protocol designed for amateur radio text transmission over HF and VHF bands.  
Developed by **6L5TNG**, MPDA combines **multiple parallel audio tones** with **intra-symbol differential amplitude shift keying** to deliver reliable text communication even under severe fading, QSB, and noise.

This repository contains the complete Python modem core (`mpda_core.py`) with a **phase-continuous** transmitter and a **matched-filter correlation** receiver.

## Key Features

- **Intra-Symbol Differential ASK**  
  Each symbol is split into two equal halves:  
  - **Reference Half**: fixed 0.5 amplitude (instantaneous channel reference)  
  - **Data Half**: 1.0 (bit 1) or 0.1 (bit 0) amplitude  
  The receiver compares within the same symbol → outstanding fading immunity

- **100% Phase-Continuous Waveform**  
  No key clicks, minimal splatter, clean spectrum

- **Coherent Matched-Filter Detection**  
  3–6 dB better than simple energy detection

- **Flexible Multi-Parallel Modes**  
  1, 4, or 8 parallel tones × 5, 10, or 15 baud

## Technical Specifications

| Parameter              | Specification                                                                 |
|------------------------|-------------------------------------------------------------------------------|
| **Modulation Type**    | Multi-Parallel Intra-Symbol Differential ASK (self-referenced 2-level)       |
| **Symbol Rates**       | 5, 10, 15 baud                                                               |
| **Parallel Tones**     | **1-Track:** 1500 Hz<br>**4-Track:** 800, 1200, 1600, 2000 Hz<br>**8-Track:** 600–2000 Hz (200 Hz spacing) |
| **Pilot Tone**         | 2200 Hz (AGC wake-up & rough timing)                                        |
| **Sync Word**          | `0xAA` (10101010…)                                                           |
| **EOT Marker**         | `0xFF` (11111111…)                                                           |
| **Sample Rate**        | 44100 Hz                                                                     |

### Mode List

| Mode Name  | Tracks | Symbol Rate | Raw Bit Rate | Notes                 |
|------------|:------:|:-----------:|:------------:|-----------------------|
| MPDA-1x5   |   1    |    5 Baud   |    5 bps     | Very robust, very slow |
| MPDA-1x10  |   1    |   10 Baud   |   10 bps     | Robust single-track    |
| MPDA-1x15  |   1    |   15 Baud   |   15 bps     | Faster single-track    |
| MPDA-4x5   |   4    |    5 Baud   |   20 bps     | Robust multi-track     |
| MPDA-4x10* |   4    |   10 Baud   |   40 bps     | Default mode           |
| MPDA-4x15  |   4    |   15 Baud   |   60 bps     | Fast multi-track       |
| MPDA-8x5   |   8    |    5 Baud   |   40 bps     | Many tracks, low rate  |
| MPDA-8x10  |   8    |   10 Baud   |   80 bps     | High throughput        |
| MPDA-8x15  |   8    |   15 Baud   |  120 bps     | Maximum speed          |

> **Note on Speed:** The raw bit rate is calculated as `Tracks × Symbol Rate`. For example, MPDA-4x10 achieves **40 bps** (4 tracks × 10 baud).  
> \* `MPDA-4x10` is the reference mode used in most examples.

### Signal Structure & Differential Encoding

MPDA ensures reliability through a structured transmission sequence:

1. **Pilot Tone:** A 2200 Hz tone precedes the data burst to wake up the receiver and establish AGC/timing lock.
2. **Gap:** A fixed silence period (0.15s) separates the pilot and data burst.
3. **Preamble:** Three bytes of `0xAA` are sent for bit synchronization.
4. **Payload (Differential Encoding):**  
   Each symbol duration is divided into two halves:
   * **First Half (Reference):** Transmitted at **0.5** amplitude. This establishes a local baseline for the current channel condition.
   * **Second Half (Data):** Transmitted at either **1.0** or **0.1** amplitude.
     * **Logic 1:** High Amplitude (1.0) – *Louder than reference.*
     * **Logic 0:** Soft-Low Amplitude (0.1) – *Quieter than reference (maintains PLL lock).*
   
   *The receiver decodes bits by comparing the energy of the Data half against the Reference half. This makes MPDA highly resistant to amplitude fluctuations caused by fading.*

5. **Postamble:** Three bytes of `0xFF` signal the end of transmission.

## Installation

This library requires `numpy` for DSP operations. If you intend to run the example application with real-time audio, `sounddevice` is also required.

```bash
pip install numpy sounddevice
```

## Usage

The core logic is encapsulated in `mpda_core.py`. You can import this module to build your own modem application.

### Transmitter Example

```python
from mpda_core import MPDATransmitter

# Initialize
tx = MPDATransmitter()

# Generate Audio Data (float32 array)
# Mode: 4 Parallel Tracks, 10 Hz Symbol Rate (MPDA-4x10)
message = "CQ CQ DE 6L5TNG"
audio_signal = tx.generate_signal(message, tracks=4, speed=10)

# Pass 'audio_signal' to your sound card output stream
```

### Receiver Example

```python
from mpda_core import MPDAReceiver

# Initialize
rx = MPDAReceiver(tracks=4, speed=10)  # MPDA-4x10

# Feed audio chunks (from microphone input)
# 'chunk' should be a numpy array of float samples
char = rx.process_audio(chunk)

if char:
    if char == "<EOT>":
        print("Transmission Ended")
    else:
        print(f"Received: {char}")
```

## License

This project is open-source software.  
Copyright (c) 2025 **6L5TNG (Kang Han) & Community Contributors**.

## Contact

* **Callsign:** 6L5TNG  
* **Developer:** Kang Han (Republic of Korea)  
* **Email:** ies0812@icloud.com  
* **QRZ Page:** https://www.qrz.com/db/6L5TNG

PS: I'm a beginner, so contributions are welcome!

# MPDA (Multi-Parallel Differential ASK) Protocol

**MPDA** is a robust, narrowband digital communication protocol designed for amateur radio text transmission over HF and VHF bands. Developed by **6L5TNG**, this protocol employs **Multi-Parallel Differential Amplitude Shift Keying** to achieve reliable data transfer even in noisy channel conditions.

This repository contains the core Python implementation (`mpda_core.py`) of the modem engine, featuring a **Phase-Continuous Hard Keying** transmitter and a **Matched Filter (Correlation)** receiver.

## Key Features

* **Robust Modulation:** Uses **AFSK-based Multi-tone ASK**. Unlike traditional FSK, MPDA utilizes amplitude states across multiple parallel carriers, providing high spectral efficiency.
* **Phase Continuity:** The transmitter generates **Phase-Continuous** waveforms to eliminate key clicks and minimize splatter, ensuring a clean signal on the air.
* **DSP-Based Demodulation:** The receiver utilizes **Matched Filter Correlation (Coherent Detection)**, which offers superior performance in low SNR environments compared to simple energy detection.
* **Adaptive Modes:** Supports multiple configurations to balance speed and reliability:
  * **Tracks:** 1, 4, or 8 parallel tones.
  * **Symbol Rate:** 5, 10, or 15 Hz (Baud).

## Technical Specifications

| Parameter | Specification |
| :--- | :--- |
| **Modulation Type** | Multi-Parallel Differential ASK (Audio Band) |
| **Symbol Rates** | 5 Hz, 10 Hz, 15 Hz |
| **Parallel Tones** | **1-Track:** 1500 Hz<br>**4-Tracks:** 800, 1200, 1600, 2000 Hz<br>**8-Tracks:** 600, 800, ..., 2000 Hz (200 Hz spacing) |
| **Pilot Tone** | 2200 Hz (Used for synchronization and channel estimation) |
| **Sync Word** | `0xAA` (10101010) |
| **End of Tx (EOT)** | `0xFF` (11111111) |
| **Sample Rate** | 44100 Hz (Standard Audio) |

## Supported Modes

### Mode Naming

MPDA modes are named as:

> `MPDA-<tracks>x<baud>`

where:

- `<tracks>` is the number of parallel tones (1, 4, 8).
- `<baud>` is the symbol rate in symbols per second (5, 10, 15).

Examples:

- `MPDA-4x10` → 4 tracks, 10 baud  
- `MPDA-1x5` → 1 track, 5 baud  
- `MPDA-8x15` → 8 tracks, 15 baud  

Unless otherwise noted, **MPDA-4x10** is considered the basic/default mode.

### Mode List

| Mode Name  | Tracks | Symbol Rate (Baud) | Notes                 |
|------------|:------:|:------------------:|-----------------------|
| MPDA-1x5   |   1    |         5          | Very robust, very slow |
| MPDA-1x10  |   1    |        10          | Robust single-track    |
| MPDA-1x15  |   1    |        15          | Faster single-track    |
| MPDA-4x5   |   4    |         5          | Robust multi-track     |
| MPDA-4x10* |   4    |        10          | Default mode           |
| MPDA-4x15  |   4    |        15          | Fast multi-track       |
| MPDA-8x5   |   8    |         5          | Many tracks, low rate  |
| MPDA-8x10  |   8    |        10          | High throughput        |
| MPDA-8x15  |   8    |        15          | Maximum speed          |

\* `MPDA-4x10` is the reference mode used in most examples.

### Signal Structure

1. **Pilot Tone:** A 2200 Hz tone precedes the data burst to wake up the receiver and establish AGC/timing lock.
2. **Gap:** A fixed silence period (0.15s) separates the pilot and data burst.
3. **Preamble:** Three bytes of `0xAA` are sent for bit synchronization.
4. **Payload:** Text data is encoded into bit streams and mapped onto parallel frequency tracks.
   * **Logic 1:** High Amplitude (1.0)
   * **Logic 0:** Soft-Low Amplitude (0.1) - *Maintains PLL lock without losing phase.*
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

#!/usr/bin/env python3
"""
MPDA Sample Generator Script
Generates MP3 sample files for all track/speed combinations.
"""

import os
import sys
import numpy as np
from scipy.io import wavfile
from pydub import AudioSegment

# Add parent directory to path to import mpda_core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mpda_core import MPDATransmitter, SAMPLE_RATE


def generate_all_samples():
    """Generate MPDA sample files for all track/speed combinations."""
    
    # Configuration
    message = "CQ CQ DE 6L5TUC 6L5TUC PSE K"
    tracks_list = [1, 4, 8]
    speeds_list = [5, 10, 15]
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize transmitter
    tx = MPDATransmitter()
    
    print(f"Generating MPDA samples with message: {message}")
    print(f"Output directory: {output_dir}")
    print("-" * 50)
    
    for tracks in tracks_list:
        for speed in speeds_list:
            # Generate signal
            print(f"Generating Track {tracks}, Speed {speed}...")
            audio_signal = tx.generate_signal(message, tracks=tracks, speed=speed)
            
            # Convert float32 (-1 to 1) to int16
            audio_int16 = (audio_signal * 32767).astype(np.int16)
            
            # Save as temporary WAV file
            temp_wav = os.path.join(output_dir, f"temp_track{tracks}_speed{speed}.wav")
            wavfile.write(temp_wav, SAMPLE_RATE, audio_int16)
            
            # Convert to MP3
            output_mp3 = os.path.join(output_dir, f"MPDA-Track{tracks}-Speed{speed}.mp3")
            audio_segment = AudioSegment.from_wav(temp_wav)
            audio_segment.export(output_mp3, format="mp3", bitrate="128k")
            
            # Remove temporary WAV file
            os.remove(temp_wav)
            
            print(f"  -> Created: {os.path.basename(output_mp3)}")
    
    print("-" * 50)
    print(f"Successfully generated {len(tracks_list) * len(speeds_list)} MP3 files.")


if __name__ == "__main__":
    generate_all_samples()

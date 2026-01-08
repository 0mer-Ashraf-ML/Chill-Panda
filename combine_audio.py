"""
Combine PCM audio files from test_socket_audio folder into a single WAV file.

PCM format: 16-bit signed, 16kHz, mono
Output: combined_output.wav

Run with: python combine_audio.py
"""

import os
import wave
import glob

# Audio settings (matching client_v2.js)
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes

# Paths
INPUT_DIR = "test_socket_audio"
OUTPUT_FILE = "combined_output.wav"


def get_pcm_files(directory: str) -> list:
    """Get all PCM files sorted by filename."""
    pattern = os.path.join(directory, "*.pcm")
    files = glob.glob(pattern)
    return sorted(files)


def combine_pcm_to_wav(pcm_files: list, output_path: str):
    """Combine multiple PCM files into a single WAV file."""
    if not pcm_files:
        print("[ERROR] No PCM files found!")
        return False
    
    print(f"[INFO] Found {len(pcm_files)} PCM files")
    
    # Read all PCM data
    combined_data = bytearray()
    for pcm_file in pcm_files:
        with open(pcm_file, "rb") as f:
            data = f.read()
            combined_data.extend(data)
        print(f"  + {os.path.basename(pcm_file)} ({len(data)} bytes)")
    
    print(f"\n[INFO] Total audio data: {len(combined_data)} bytes")
    
    # Calculate duration
    duration_seconds = len(combined_data) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
    print(f"[INFO] Duration: {duration_seconds:.2f} seconds")
    
    # Write WAV file
    with wave.open(output_path, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(bytes(combined_data))
    
    print(f"\n[SUCCESS] Created: {output_path}")
    return True


def main():
    print("="*60)
    print("PCM to WAV Converter")
    print("="*60)
    
    # Check if input directory exists
    if not os.path.exists(INPUT_DIR):
        print(f"[ERROR] Directory not found: {INPUT_DIR}")
        return
    
    # Get PCM files
    pcm_files = get_pcm_files(INPUT_DIR)
    
    # Combine and convert
    success = combine_pcm_to_wav(pcm_files, OUTPUT_FILE)
    
    if success:
        print(f"\n[TIP] Play with: ffplay {OUTPUT_FILE}")
        print(f"[TIP] Or open in any audio player")


if __name__ == "__main__":
    main()

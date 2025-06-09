# VideoLingo Lip Sync Functionality

This module provides lip synchronization capabilities for VideoLingo using Easy-Wav2Lip technology.

## Features

- **Automatic Face Detection**: Detects faces in video frames to ensure compatibility
- **Video Segmentation**: Splits long videos into <30s segments for optimal processing
- **Easy-Wav2Lip Integration**: Uses state-of-the-art lip sync technology
- **Automatic Model Download**: Downloads required models automatically
- **GPU Acceleration**: Supports CUDA for faster processing

## Requirements

### System Requirements
- Python 3.10+
- FFmpeg
- CUDA-compatible GPU (recommended)
- At least 8GB RAM
- 5GB free disk space for models

### Dependencies
The following packages are automatically installed:
- torch>=1.9.0
- torchvision>=0.10.0
- torchaudio>=0.9.0
- face-alignment
- gfpgan
- basicsr
- facexlib
- realesrgan

## Installation

1. **Automatic Installation** (Recommended):
   ```bash
   python core/lip_sync_utils/install_lipsync.py
   ```

2. **Manual Installation**:
   ```bash
   pip install torch torchvision torchaudio face-alignment gfpgan basicsr facexlib realesrgan
   ```

## Usage

### Via Streamlit Interface
1. Enable "Lip Synchronization" in the sidebar settings
2. Complete video translation and dubbing first
3. Navigate to the "Lip Synchronization" section
4. Adjust quality settings if needed
5. Click "Start Lip Sync Processing"

### Via Command Line
```bash
python -m core._13_lip_sync
```

### Via Python API
```python
from core._13_lip_sync import apply_lip_sync

# Apply lip sync with default settings
apply_lip_sync()

# Apply with custom quality factor
apply_lip_sync(resize_factor=1.5)  # Higher quality, slower processing
```

## Configuration

### Quality Settings
- **resize_factor**: Controls quality vs speed trade-off
  - `0.5`: Fastest, lower quality
  - `1.0`: Balanced (default)
  - `2.0`: Highest quality, slowest

### Video Requirements
- **Face Presence**: Video must contain faces in at least 80% of frames
- **Resolution**: Works best with 720p-1080p videos
- **Duration**: Automatically segments videos >30 seconds
- **Format**: Supports MP4, AVI, MOV, and other common formats

## How It Works

1. **Face Detection**: Scans video frames to detect faces using OpenCV
2. **Video Segmentation**: Splits long videos into manageable segments
3. **Environment Setup**: Downloads Easy-Wav2Lip and required models
4. **Processing**: Applies lip sync to each segment individually
5. **Merging**: Combines processed segments back into final video

## Troubleshooting

### Common Issues

**"No faces detected in video"**
- Ensure the video contains clear, visible faces
- Try adjusting video brightness/contrast
- Check if faces are too small or at extreme angles

**"Lip sync processing failed"**
- Verify GPU drivers are up to date
- Check available disk space (>5GB required)
- Ensure stable internet connection for model downloads

**"Out of memory" errors**
- Reduce resize_factor to 0.5 or 0.75
- Close other GPU-intensive applications
- Consider using CPU mode (slower but uses less memory)

### Performance Tips

1. **GPU Acceleration**: Ensure CUDA is properly installed
2. **Video Quality**: Use 720p videos for best speed/quality balance
3. **Segment Length**: Shorter segments process faster but may have slight discontinuities
4. **Batch Processing**: Process multiple videos sequentially rather than simultaneously

## Technical Details

### Model Information
- **Wav2Lip Models**: ~149MB each (wav2lip.pth, wav2lip_gan.pth)
- **Face Detection**: S3FD model (~89MB)
- **Total Storage**: ~400MB for all models

### Processing Pipeline
1. Video duration analysis
2. Face detection validation
3. Segmentation (if needed)
4. Easy-Wav2Lip setup
5. Individual segment processing
6. Final video assembly

## Limitations

- Requires faces to be present in most frames
- Processing time scales with video length
- GPU memory requirements increase with video resolution
- May have slight quality loss compared to original video

## Support

For issues specific to lip sync functionality:
1. Check the troubleshooting section above
2. Verify all dependencies are installed correctly
3. Ensure video meets the requirements listed
4. Check GPU compatibility and drivers

For general VideoLingo support, refer to the main project documentation. 
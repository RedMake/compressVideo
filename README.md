**Video Compression Tool**

> This Python application is designed for compressing video files using the ffmpeg library and a Tkinter-based graphical interface. It allows users to reduce video file sizes with adjustable quality settings while maintaining good visual fidelity. The application can queue multiple videos for batch compression and offers the ability to cancel ongoing processes. It is ideal for handling large video files and making them more manageable for sharing or storage.

**_Features:_**

- **Multiple Quality Modes**: Choose between different compression quality modes (Max Quality, Super, Ultra-High, High, Medium, Low) depending on your needs.
- **Two-Pass Encoding**: Optionally use two-pass encoding to improve video quality at the target bitrate.
- **[Not Implemented Yet]** <s>**Drag-and-Drop Interface**: Easily add videos via drag-and-drop or by manually selecting files.</s>
- **[Not Implemented Yet]** <s>**Batch Compression**: Queue up to 10 video files for compression at once.</s>
- **File Type Support**: Supports common video formats including .mp4, .mov, .avi, .mkv, .flv, and .wmv.
- **Cancel Compression**: Option to cancel compression processes while they are running.
- **Progress** Tracking: View real-time progress and compression logs.

**_How to Use:_**

1. Drag and drop video files into the window or select them manually.
2. Choose the desired output location.
3. Select a quality mode.
4. Start the compression process.
5. Cancel anytime if needed.

**_Dependencies:_**
1. ffmpeg-python: For video processing.
2. Tkinter: For the GUI.
- **[Not Implemented Yet]** <s>TkinterDnD2: For drag-and-drop functionality.</s>



import sys
import os
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QListWidget, QListWidgetItem,
    QFileDialog, QProgressBar, QSpinBox, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QFont, QIcon, QColor, QPixmap, QPainter, QPen
from PyQt5.QtWidgets import QApplication
import pygame
from mutagen.mp3 import MP3
import numpy as np

class AudioVisualizer(QWidget):
    """Custom widget for audio spectrum visualizer"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frequencies = [0] * 32
        self.setMinimumHeight(100)
        self.setStyleSheet("background-color: #1a1a1a;")
        
    def set_frequencies(self, frequencies):
        self.frequencies = frequencies[:32]
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        bar_width = width // 32
        
        # Draw bars
        for i, freq in enumerate(self.frequencies):
            bar_height = (freq / 255) * height
            x = i * bar_width
            y = height - bar_height
            
            # Gradient color based on frequency
            hue = int((i / 32) * 120)  # Blue to green gradient
            painter.fillRect(int(x), int(y), int(bar_width - 2), int(bar_height), 
                           QColor.fromHsv(hue, 255, 200))


class AudioDecoder:
    """Handles audio file decoding and playback"""
    
    def __init__(self):
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        self.current_sound = None
        self.is_playing = False
        self.current_file = None
    
    def load_file(self, filepath):
        """Load MP3 file"""
        try:
            self.current_file = filepath
            self.current_sound = pygame.mixer.Sound(filepath)
            return True
        except Exception as e:
            print(f"Error loading file: {e}")
            return False
    
    def play(self):
        """Play audio"""
        if self.current_sound:
            self.current_sound.play(-1)
            self.is_playing = True
    
    def pause(self):
        """Pause audio"""
        pygame.mixer.pause()
        self.is_playing = False
    
    def unpause(self):
        """Resume audio"""
        pygame.mixer.unpause()
        self.is_playing = True
    
    def stop(self):
        """Stop audio"""
        pygame.mixer.stop()
        self.is_playing = False
    
    def set_volume(self, volume):
        """Set volume (0-100)"""
        pygame.mixer.music.set_volume(volume / 100)


class PlaylistManager:
    """Manages playlist data"""
    
    def __init__(self):
        self.playlist = []
        self.current_index = 0
        self.config_file = Path.home() / ".mp3_reader_config.json"
        self.load_config()
    
    def add_files(self, filepaths):
        """Add files to playlist"""
        for filepath in filepaths:
            if filepath.lower().endswith('.mp3'):
                self.playlist.append(filepath)
    
    def remove_file(self, index):
        """Remove file from playlist"""
        if 0 <= index < len(self.playlist):
            self.playlist.pop(index)
    
    def get_current_file(self):
        """Get current file"""
        if 0 <= self.current_index < len(self.playlist):
            return self.playlist[self.current_index]
        return None
    
    def next(self):
        """Move to next file"""
        if self.playlist:
            self.current_index = (self.current_index + 1) % len(self.playlist)
            return self.get_current_file()
    
    def previous(self):
        """Move to previous file"""
        if self.playlist:
            self.current_index = (self.current_index - 1) % len(self.playlist)
            return self.get_current_file()
    
    def save_config(self):
        """Save playlist to config"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump({'playlist': self.playlist}, f)
        except:
            pass
    
    def load_config(self):
        """Load playlist from config"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.playlist = data.get('playlist', [])
        except:
            pass


class MP3ReaderApp(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Reader")
        self.setGeometry(100, 100, 900, 700)
        
        # Initialize components
        self.decoder = AudioDecoder()
        self.playlist_manager = PlaylistManager()
        self.is_playing = False
        self.current_duration = 0
        
        # Setup UI
        self.setup_ui()
        self.apply_stylesheet()
        
        # Timer for updating display
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)
        
        # Visualizer update timer
        self.viz_timer = QTimer()
        self.viz_timer.timeout.connect(self.update_visualizer)
        self.viz_timer.start(50)
    
    def setup_ui(self):
        """Setup user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Visualizer
        self.visualizer = AudioVisualizer()
        main_layout.addWidget(self.visualizer)
        
        # Info section
        info_layout = QVBoxLayout()
        
        self.song_label = QLabel("No song loaded")
        self.song_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.song_label.setStyleSheet("color: #00ff00;")
        
        self.artist_label = QLabel("Unknown Artist")
        self.artist_label.setFont(QFont("Arial", 11))
        self.artist_label.setStyleSheet("color: #cccccc;")
        
        info_layout.addWidget(self.song_label)
        info_layout.addWidget(self.artist_label)
        main_layout.addLayout(info_layout)
        
        # Timeline
        timeline_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00")
        self.time_label.setFont(QFont("Courier", 10))
        self.time_label.setStyleSheet("color: #00ff00;")
        
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setSliderPosition(0)
        self.progress_slider.sliderMoved.connect(self.seek_song)
        
        self.duration_label = QLabel("00:00")
        self.duration_label.setFont(QFont("Courier", 10))
        self.duration_label.setStyleSheet("color: #00ff00;")
        
        timeline_layout.addWidget(self.time_label)
        timeline_layout.addWidget(self.progress_slider)
        timeline_layout.addWidget(self.duration_label)
        main_layout.addLayout(timeline_layout)
        
        # Control buttons
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        
        self.prev_btn = QPushButton("⏮ Previous")
        self.prev_btn.clicked.connect(self.previous_track)
        self.prev_btn.setMinimumHeight(40)
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self.toggle_play)
        self.play_btn.setMinimumHeight(40)
        
        self.next_btn = QPushButton("Next ⏭")
        self.next_btn.clicked.connect(self.next_track)
        self.next_btn.setMinimumHeight(40)
        
        control_layout.addWidget(self.prev_btn)
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.next_btn)
        main_layout.addLayout(control_layout)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.valueChanged.connect(self.set_volume)
        
        self.volume_label = QLabel("70%")
        self.volume_label.setMaximumWidth(40)
        
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        main_layout.addLayout(volume_layout)
        
        # Playback mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItems(["No Repeat", "Repeat All", "Repeat One"])
        
        self.shuffle_btn = QPushButton("🔀 Shuffle OFF")
        self.shuffle_btn.clicked.connect(self.toggle_shuffle)
        self.shuffle_enabled = False
        
        mode_layout.addWidget(self.repeat_combo)
        mode_layout.addWidget(self.shuffle_btn)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)
        
        # Playlist section
        playlist_label = QLabel("📋 Playlist")
        playlist_label.setFont(QFont("Arial", 11, QFont.Bold))
        main_layout.addWidget(playlist_label)
        
        self.playlist_widget = QListWidget()
        self.playlist_widget.itemDoubleClicked.connect(self.play_selected)
        main_layout.addWidget(self.playlist_widget)
        
        # File management buttons
        file_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Add Files")
        self.add_btn.clicked.connect(self.add_files)
        
        self.remove_btn = QPushButton("➖ Remove")
        self.remove_btn.clicked.connect(self.remove_selected)
        
        self.clear_btn = QPushButton("🗑 Clear All")
        self.clear_btn.clicked.connect(self.clear_playlist)
        
        file_layout.addWidget(self.add_btn)
        file_layout.addWidget(self.remove_btn)
        file_layout.addWidget(self.clear_btn)
        main_layout.addLayout(file_layout)
    
    def apply_stylesheet(self):
        """Apply dark theme"""
        stylesheet = """
        QMainWindow {
            background-color: #0a0a0a;
            color: #ffffff;
        }
        QLabel {
            color: #ffffff;
        }
        QPushButton {
            background-color: #1a1a1a;
            color: #00ff00;
            border: 2px solid #00ff00;
            border-radius: 5px;
            padding: 5px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #00ff00;
            color: #000000;
        }
        QPushButton:pressed {
            background-color: #00cc00;
        }
        QSlider::groove:horizontal {
            background-color: #1a1a1a;
            height: 8px;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background-color: #00ff00;
            width: 15px;
            margin: -4px 0;
            border-radius: 7px;
        }
        QListWidget {
            background-color: #1a1a1a;
            border: 1px solid #00ff00;
            color: #ffffff;
        }
        QListWidget::item:selected {
            background-color: #00ff00;
            color: #000000;
        }
        QComboBox {
            background-color: #1a1a1a;
            color: #00ff00;
            border: 1px solid #00ff00;
        }
        """
        self.setStyleSheet(stylesheet)
    
    def add_files(self):
        """Add files to playlist"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add MP3 Files", "", "MP3 Files (*.mp3)"
        )
        if files:
            self.playlist_manager.add_files(files)
            self.refresh_playlist_display()
            self.playlist_manager.save_config()
    
    def refresh_playlist_display(self):
        """Refresh playlist display"""
        self.playlist_widget.clear()
        for i, filepath in enumerate(self.playlist_manager.playlist):
            filename = Path(filepath).name
            item = QListWidgetItem(filename)
            if i == self.playlist_manager.current_index:
                item.setBackground(QColor("#00ff00"))
                item.setForeground(QColor("#000000"))
            self.playlist_widget.addItem(item)
    
    def remove_selected(self):
        """Remove selected item from playlist"""
        current_row = self.playlist_widget.currentRow()
        if current_row >= 0:
            self.playlist_manager.remove_file(current_row)
            self.refresh_playlist_display()
            self.playlist_manager.save_config()
    
    def clear_playlist(self):
        """Clear entire playlist"""
        self.playlist_manager.playlist.clear()
        self.playlist_manager.current_index = 0
        self.decoder.stop()
        self.is_playing = False
        self.play_btn.setText("▶ Play")
        self.refresh_playlist_display()
        self.playlist_manager.save_config()
    
    def play_selected(self, item):
        """Play selected item"""
        index = self.playlist_widget.row(item)
        self.playlist_manager.current_index = index
        self.load_and_play()
    
    def load_and_play(self):
        """Load current file and play"""
        filepath = self.playlist_manager.get_current_file()
        if filepath and self.decoder.load_file(filepath):
            try:
                audio = MP3(filepath)
                self.current_duration = int(audio.info.length)
                self.progress_slider.setMaximum(self.current_duration * 1000)
                
                # Get metadata
                title = filepath.split(os.sep)[-1].replace('.mp3', '')
                artist = "Unknown"
                if audio.get('TIT2'):
                    title = str(audio['TIT2'])
                if audio.get('TPE1'):
                    artist = str(audio['TPE1'])
                
                self.song_label.setText(title)
                self.artist_label.setText(artist)
                
            except:
                self.song_label.setText(Path(filepath).name)
                self.artist_label.setText("Unknown Artist")
            
            self.decoder.play()
            self.is_playing = True
            self.play_btn.setText("⏸ Pause")
            self.refresh_playlist_display()
    
    def toggle_play(self):
        """Toggle play/pause"""
        if not self.is_playing:
            if self.playlist_manager.get_current_file():
                self.load_and_play()
            else:
                self.song

import sys
import os
import json
import random
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, QUrl
from PyQt5.QtGui import QFont, QColor, QPixmap, QPainter, QPen
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import pygame
from mutagen.mp3 import MP3


class AudioVisualizer(QWidget):
    """مرئي الطيف الصوتي (Audio Spectrum Visualizer)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frequencies = [0] * 32
        self.setMinimumHeight(120)
        self.setStyleSheet("background-color: #0f0f0f; border: 2px solid #00ff00;")
        
    def set_frequencies(self, frequencies):
        self.frequencies = frequencies[:32] if frequencies else [0] * 32
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        bar_width = max(1, width // 32)
        
        for i, freq in enumerate(self.frequencies):
            bar_height = (freq / 255.0) * height * 0.9
            x = i * bar_width
            y = height - bar_height
            
            # ألوان متدرجة (Gradient colors)
            hue = int((i / 32.0) * 120)
            painter.fillRect(int(x), int(y), int(bar_width - 2), int(bar_height), 
                           QColor.fromHsv(hue, 255, 200))
            
            # خطوط عاكسة (Reflection)
            painter.fillRect(int(x), int(height - bar_height - 30), 
                           int(bar_width - 2), 25, 
                           QColor.fromHsv(hue, 100, 100))


class PlaylistManager:
    """إدارة قائمة التشغيل (Playlist Management)"""
    
    def __init__(self):
        self.playlist = []
        self.current_index = 0
        self.config_file = Path.home() / ".mp3_reader_config.json"
        self.load_config()
    
    def add_files(self, filepaths):
        """إضافة ملفات"""
        for filepath in filepaths:
            if filepath.lower().endswith('.mp3') and filepath not in self.playlist:
                self.playlist.append(filepath)
    
    def remove_file(self, index):
        """إزالة ملف"""
        if 0 <= index < len(self.playlist):
            self.playlist.pop(index)
            if self.current_index >= len(self.playlist) and self.current_index > 0:
                self.current_index -= 1
    
    def get_current_file(self):
        """الملف الحالي"""
        if 0 <= self.current_index < len(self.playlist):
            return self.playlist[self.current_index]
        return None
    
    def next(self):
        """الملف التالي"""
        if self.playlist:
            self.current_index = (self.current_index + 1) % len(self.playlist)
            return self.get_current_file()
        return None
    
    def previous(self):
        """الملف السابق"""
        if self.playlist:
            self.current_index = (self.current_index - 1) % len(self.playlist)
            return self.get_current_file()
        return None
    
    def shuffle_track(self):
        """تشغيل عشوائي"""
        if self.playlist:
            self.current_index = random.randint(0, len(self.playlist) - 1)
            return self.get_current_file()
        return None
    
    def save_config(self):
        """حفظ الإعدادات"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump({'playlist': self.playlist}, f, indent=2)
        except Exception as e:
            print(f"خطأ في الحفظ: {e}")
    
    def load_config(self):
        """تحميل الإعدادات"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.playlist = [f for f in data.get('playlist', []) if Path(f).exists()]
        except Exception as e:
            print(f"خطأ في التحميل: {e}")


class MP3ReaderApp(QMainWindow):
    """تطبيق MP3 Reader الرئيسي"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎵 MP3 Reader")
        self.setGeometry(100, 50, 1000, 800)
        
        # المكونات الأساسية
        self.playlist_manager = PlaylistManager()
        self.current_duration = 0
        self.is_playing = False
        self.repeat_mode = 0  # 0: No Repeat, 1: Repeat All, 2: Repeat One
        self.shuffle_enabled = False
        
        # تهيئة pygame mixer
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.sound = None
        except:
            pass
        
        # إنشاء الواجهة
        self.setup_ui()
        self.apply_stylesheet()
        
        # المؤقتات
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)
        
        self.visualizer_timer = QTimer()
        self.visualizer_timer.timeout.connect(self.update_visualizer)
        self.visualizer_timer.start(50)
        
        self.auto_next_timer = QTimer()
        self.auto_next_timer.timeout.connect(self.check_track_end)
        self.auto_next_timer.start(500)
    
    def setup_ui(self):
        """تهيئة الواجهة"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # === المرئي (Visualizer) ===
        self.visualizer = AudioVisualizer()
        main_layout.addWidget(self.visualizer)
        
        # === معلومات الأغنية ===
        self.song_label = QLabel("لم يتم تحميل أغنية")
        self.song_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.song_label.setStyleSheet("color: #00ff00; text-align: center;")
        
        self.artist_label = QLabel("فنان غير معروف")
        self.artist_label.setFont(QFont("Arial", 12))
        self.artist_label.setStyleSheet("color: #cccccc; text-align: center;")
        
        main_layout.addWidget(self.song_label)
        main_layout.addWidget(self.artist_label)
        
        # === الخط الزمني ===
        timeline_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00")
        self.time_label.setFont(QFont("Courier", 11, QFont.Bold))
        self.time_label.setStyleSheet("color: #00ff00;")
        self.time_label.setMinimumWidth(50)
        
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setMaximum(1000)
        self.progress_slider.sliderMoved.connect(self.seek_song)
        
        self.duration_label = QLabel("00:00")
        self.duration_label.setFont(QFont("Courier", 11, QFont.Bold))
        self.duration_label.setStyleSheet("color: #00ff00;")
        self.duration_label.setMinimumWidth(50)
        
        timeline_layout.addWidget(self.time_label)
        timeline_layout.addWidget(self.progress_slider)
        timeline_layout.addWidget(self.duration_label)
        main_layout.addLayout(timeline_layout)
        
        # === أزرار التحكم الرئيسية ===
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        
        self.prev_btn = QPushButton("⏮ السابق")
        self.prev_btn.clicked.connect(self.previous_track)
        self.prev_btn.setMinimumHeight(45)
        self.prev_btn.setFont(QFont("Arial", 11, QFont.Bold))
        
        self.play_btn = QPushButton("▶ تشغيل")
        self.play_btn.clicked.connect(self.toggle_play)
        self.play_btn.setMinimumHeight(45)
        self.play_btn.setFont(QFont("Arial", 11, QFont.Bold))
        
        self.next_btn = QPushButton("التالي ⏭")
        self.next_btn.clicked.connect(self.next_track)
        self.next_btn.setMinimumHeight(45)
        self.next_btn.setFont(QFont("Arial", 11, QFont.Bold))
        
        control_layout.addWidget(self.prev_btn)
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.next_btn)
        main_layout.addLayout(control_layout)
        
        # === التحكم بالصوت ===
        volume_layout = QHBoxLayout()
        volume_label = QLabel("🔊 مستوى الصوت:")
        volume_label.setFont(QFont("Arial", 10, QFont.Bold))
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.valueChanged.connect(self.set_volume)
        
        self.volume_label = QLabel("70%")
        self.volume_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        self.volume_label.setMinimumWidth(40)
        
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        main_layout.addLayout(volume_layout)
        
        # === أوضاع التشغيل ===
        mode_layout = QHBoxLayout()
        
        self.repeat_btn = QPushButton("🔁 بدون تكرار")
        self.repeat_btn.clicked.connect(self.toggle_repeat)
        
        self.shuffle_btn = QPushButton("🔀 عشوائي: OFF")
        self.shuffle_btn.clicked.connect(self.toggle_shuffle)
        
        mode_layout.addWidget(self.repeat_btn)
        mode_layout.addWidget(self.shuffle_btn)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)
        
        # === قائمة التشغيل ===
        playlist_label = QLabel("📋 قائمة التشغيل")
        playlist_label.setFont(QFont("Arial", 12, QFont.Bold))
        playlist_label.setStyleSheet("color: #00ff00;")
        main_layout.addWidget(playlist_label)
        
        self.playlist_widget = QListWidget()
        self.playlist_widget.itemDoubleClicked.connect(self.play_selected)
        self.playlist_widget.setMinimumHeight(200)
        main_layout.addWidget(self.playlist_widget)
        
        # === أزرار إدارة الملفات ===
        file_layout = QHBoxLayout()
        file_layout.setSpacing(10)
        
        self.add_btn = QPushButton("➕ إضافة ملفات")
        self.add_btn.clicked.connect(self.add_files)
        self.add_btn.setMinimumHeight(40)
        
        self.remove_btn = QPushButton("➖ إزالة")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.remove_btn.setMinimumHeight(40)
        
        self.clear_btn = QPushButton("🗑 حذف الكل")
        self.clear_btn.clicked.connect(self.clear_playlist)
        self.clear_btn.setMinimumHeight(40)
        
        file_layout.addWidget(self.add_btn)
        file_layout.addWidget(self.remove_btn)
        file_layout.addWidget(self.clear_btn)
        main_layout.addLayout(file_layout)
    
    def apply_stylesheet(self):
        """تطبيق ستايل الواجهة المظلمة"""
        stylesheet = """
        QMainWindow {
            background-color: #0a0a0a;
            color: #ffffff;
        }
        QLabel {
            color: #ffffff;
        }
        QPushButton {
            background-color: #1a1a1a;
            color: #00ff00;
            border: 2px solid #00ff00;
            border-radius: 6px;
            padding: 8px;
            font-weight: bold;
            transition: 0.3s;
        }
        QPushButton:hover {
            background-color: #00ff00;
            color: #000000;
            border: 2px solid #00ff00;
        }
        QPushButton:pressed {
            background-color: #00cc00;
        }
        QSlider::groove:horizontal {
            background-color: #2a2a2a;
            height: 10px;
            border-radius: 5px;
        }
        QSlider::handle:horizontal {
            background-color: #00ff00;
            width: 16px;
            margin: -3px 0;
            border-radius: 8px;
        }
        QSlider::handle:horizontal:hover {
            background-color: #00ff44;
        }
        QListWidget {
            background-color: #1a1a1a;
            border: 2px solid #00ff00;
            color: #ffffff;
            padding: 5px;
        }
        QListWidget::item {
            padding: 6px;
        }
        QListWidget::item:selected {
            background-color: #00ff00;
            color: #000000;
            font-weight: bold;
        }
        QListWidget::item:hover {
            background-color: #333333;
        }
        """
        self.setStyleSheet(stylesheet)
    
    def add_files(self):
        """إضافة ملفات MP3"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "اختر ملفات MP3", "",
            "ملفات MP3 (*.mp3);;جميع الملفات (*)"
        )
        if files:
            self.playlist_manager.add_files(files)
            self.refresh_playlist_display()
            self.playlist_manager.save_config()
            QMessageBox.information(self, "نجاح", 
                f"تم إضافة {len(files)} ملف(ات) إلى قائمة التشغيل")
    
    def refresh_playlist_display(self):
        """تحديث عرض قائمة التشغيل"""
        self.playlist_widget.clear()
        for i, filepath in enumerate(self.playlist_manager.playlist):
            filename = Path(filepath).stem
            item = QListWidgetItem(f"{i+1}. {filename}")
            
            if i == self.
playlist_manager.current_index:
                item.setBackground(QColor("#00ff00"))
                item.setForeground(QColor("#000000"))
            self.playlist_widget.addItem(item)
    
    def remove_selected(self):
        """إزالة العنصر المختار"""
        current_row = self.playlist_widget.currentRow()
        if current_row >= 0:
            self.playlist_manager.remove_file(current_row)
            self.refresh_playlist_display()
            self.playlist_manager.save_config()
    
    def clear_playlist(self):
        """حذف كل قائمة التشغيل"""
        reply = QMessageBox.question(self, "تأكيد", 
            "هل أنت متأكد من حذف كل الأغاني؟",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.playlist_manager.playlist.clear()
            self.playlist_manager.current_index = 0
            self.stop_playback()
            self.refresh_playlist_display()
            self.playlist_manager.save_config()
    
    def play_selected(self, item):
        """تشغيل العنصر المختار"""
        index = self.playlist_widget.row(item)
        self.playlist_manager.current_index = index
        self.load_and_play()
    
    def load_and_play(self):
        """تحميل وتشغيل الملف الحالي"""
        filepath = self.playlist_manager.get_current_file()
        
        if not filepath or not Path(filepath).exists():
            QMessageBox.warning(self, "خطأ", "لا يمكن العثور على الملف")
            return
        
        try:
            # تحميل الملف
            self.sound = pygame.mixer.Sound(filepath)
            self.current_duration = int(self.sound.get_length())
            
            # جلب البيانات الوصفية
            try:
                audio = MP3(filepath)
                self.current_duration = int(audio.info.length)
                
                title = filepath.split(os.sep)[-1].replace('.mp3', '')
                artist = "فنان غير معروف"
                
                if audio.get('TIT2'):
                    title = str(audio['TIT2'])
                if audio.get('TPE1'):
                    artist = str(audio['TPE1'])
                
                self.song_label.setText(title)
                self.artist_label.setText(f"🎤 {artist}")
            except:
                self.song_label.setText(Path(filepath).name)
                self.artist_label.setText("فنان غير معروف")
            
            # تحديث المنزلق
            self.progress_slider.setMaximum(self.current_duration * 1000)
            self.progress_slider.setValue(0)
            self.time_label.setText("00:00")
            self.duration_label.setText(self.format_time(self.current_duration))
            
            # التشغيل
            self.sound.play(-1)
            self.is_playing = True
            self.play_btn.setText("⏸ إيقاف مؤقت")
            self.refresh_playlist_display()
            
        except Exception as e:
            QMessageBox.critical(self, "خطأ في التشغيل", 
                f"لم يتم تشغيل الملف: {str(e)}")
    
    def toggle_play(self):
        """تبديل التشغيل/الإيقاف المؤقت"""
        if not self.playlist_manager.playlist:
            QMessageBox.warning(self, "تحذير", "قائمة التشغيل فارغة!")
            return
        
        if not self.is_playing:
            # بدء التشغيل
            current_file = self.playlist_manager.get_current_file()
            if not current_file:
                self.playlist_manager.current_index = 0
            self.load_and_play()
        else:
            # إيقاف مؤقت
            pygame.mixer.pause()
            self.is_playing = False
            self.play_btn.setText("▶ تشغيل")
    
    def next_track(self):
        """الأغنية التالية"""
        if not self.playlist_manager.playlist:
            return
        
        if self.shuffle_enabled:
            self.playlist_manager.shuffle_track()
        else:
            self.playlist_manager.next()
        
        self.load_and_play()
    
    def previous_track(self):
        """الأغنية السابقة"""
        if not self.playlist_manager.playlist:
            return
        
        self.playlist_manager.previous()
        self.load_and_play()
    
    def toggle_repeat(self):
        """تبديل وضع التكرار"""
        self.repeat_mode = (self.repeat_mode + 1) % 3
        
        modes = ["🔁 بدون تكرار", "🔁 تكرار الكل", "🔁 تكرار الواحدة"]
        self.repeat_btn.setText(modes[self.repeat_mode])
    
    def toggle_shuffle(self):
        """تبديل التشغيل العشوائي"""
        self.shuffle_enabled = not self.shuffle_enabled
        state = "ON" if self.shuffle_enabled else "OFF"
        self.shuffle_btn.setText(f"🔀 عشوائي: {state}")
    
    def set_volume(self, value):
        """تعيين مستوى الصوت"""
        pygame.mixer.music.set_volume(value / 100)
        self.volume_label.setText(f"{value}%")
    
    def seek_song(self, position):
        """البحث في الأغنية (التنقل)"""
        if self.sound and self.current_duration > 0:
            seconds = (position / 1000)
            self.sound.set_volume(self.volume_slider.value() / 100)
    
    def stop_playback(self):
        """إيقاف التشغيل"""
        pygame.mixer.stop()
        self.is_playing = False
        self.play_btn.setText("▶ تشغيل")
        self.song_label.setText("لم يتم تحميل أغنية")
        self.artist_label.setText("فنان غير معروف")
        self.progress_slider.setValue(0)
        self.time_label.setText("00:00")
        self.duration_label.setText("00:00")
    
    def format_time(self, seconds):
        """تنسيق الوقت"""
        if seconds < 0:
            return "00:00"
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{minutes:02d}:{secs:02d}"
    
    def update_display(self):
        """تحديث عرض الوقت والمنزلق"""
        if self.is_playing and self.sound:
            try:
                # الحصول على الموضع الحالي
                channel = pygame.mixer.find_channel(False)
                if channel:
                    busy = channel.get_busy()
                    if not busy and self.is_playing:
                        # الأغنية انتهت
                        self.handle_track_end()
            except:
                pass
    
    def check_track_end(self):
        """التحقق من انتهاء الأغنية"""
        if self.is_playing and self.sound:
            try:
                # إذا انتهت الأغنية
                busy = pygame.mixer.get_busy()
                if not busy and self.is_playing:
                    self.handle_track_end()
            except:
                pass
    
    def handle_track_end(self):
        """معالجة نهاية الأغنية"""
        if self.repeat_mode == 2:  # تكرار الواحدة
            self.load_and_play()
        else:
            self.next_track()
    
    def update_visualizer(self):
        """تحديث المرئي الصوتي"""
        # محاكاة البيانات الطيفية
        if self.is_playing:
            import random
            frequencies = [random.randint(20, 250) for _ in range(32)]
            self.visualizer.set_frequencies(frequencies)
        else:
            self.visualizer.set_frequencies([0] * 32)


def main():
    """البرنامج الرئيسي"""
    app = QApplication(sys.argv)
    
    # تعيين الأيقونة والنمط
    window = MP3ReaderApp()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


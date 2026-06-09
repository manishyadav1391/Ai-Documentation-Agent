import sys
import os
import subprocess
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont

from recorder.recorder import Recorder

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class RecorderBridge(QObject):
    # Signal that transmits step count and step description thread-safely
    step_logged = pyqtSignal(int, str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Documentation Bot - Recorder")
        self.setFixedSize(420, 360)
        
        # Thread-safe signal bridge
        self.bridge = RecorderBridge()
        self.bridge.step_logged.connect(self.on_step_logged)
        
        # Initialize recorder
        self.recorder = Recorder(base_dir=".", step_signal=self.bridge.step_logged)
        
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        # Central Widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Main Layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 1. Header Title
        self.title_label = QLabel("Documentation Bot", self)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        # 2. Status Card Panel
        status_card = QFrame(self)
        status_card.setObjectName("statusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(15, 12, 15, 12)
        status_layout.setSpacing(8)
        
        # Status Row (indicator + text)
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        
        self.status_dot = QLabel("●", self)
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setFixedWidth(15)
        status_row.addWidget(self.status_dot)
        
        self.status_text = QLabel("Status: Ready", self)
        self.status_text.setObjectName("statusText")
        status_row.addWidget(self.status_text)
        status_row.addStretch()
        status_layout.addLayout(status_row)
        
        # Step counter
        self.steps_label = QLabel("Total Steps: 0", self)
        self.steps_label.setObjectName("stepsLabel")
        status_layout.addWidget(self.steps_label)
        
        # Last Action description
        self.last_action_label = QLabel("Last Action: None", self)
        self.last_action_label.setObjectName("lastActionLabel")
        self.last_action_label.setWordWrap(True)
        status_layout.addWidget(self.last_action_label)
        
        layout.addWidget(status_card)
        
        # 3. Control Buttons Panel
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.start_btn = QPushButton("Start Recording", self)
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self.start_recording)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Recording", self)
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_recording)
        btn_layout.addWidget(self.stop_btn)
        
        layout.addLayout(btn_layout)
        
        # 4. Folder Button
        self.folder_btn = QPushButton("Open Outputs Folder", self)
        self.folder_btn.setObjectName("folderButton")
        self.folder_btn.clicked.connect(self.open_output_folder)
        layout.addWidget(self.folder_btn)
        
        # 5. Help Hint
        self.hint_label = QLabel("Press Start and perform your tasks. Clicks & key inputs are highlighted automatically.", self)
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setWordWrap(True)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

    def apply_styles(self):
        # Modern CSS styles for PyQt UI
        qss = """
        QMainWindow {
            background-color: #1e1e2e;
        }
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif;
            color: #cdd6f4;
        }
        QLabel#titleLabel {
            font-size: 22px;
            font-weight: bold;
            color: #cba6f7;
            margin-bottom: 2px;
        }
        QFrame#statusCard {
            background-color: #252538;
            border-radius: 10px;
            border: 1px solid #313244;
        }
        QLabel#statusDot {
            font-size: 18px;
            color: #585b70; /* Gray when inactive */
        }
        QLabel#statusText {
            font-size: 14px;
            font-weight: bold;
            color: #a6adc8;
        }
        QLabel#stepsLabel {
            font-size: 13px;
            color: #bac2de;
        }
        QLabel#lastActionLabel {
            font-size: 12px;
            color: #9399b2;
            font-style: italic;
        }
        QLabel#hintLabel {
            font-size: 10px;
            color: #6c7086;
            margin-top: 5px;
        }
        QPushButton {
            font-weight: bold;
            font-size: 13px;
            padding: 10px 18px;
            border-radius: 6px;
            border: none;
        }
        QPushButton#startButton {
            background-color: #a6e3a1;
            color: #11111b;
        }
        QPushButton#startButton:hover {
            background-color: #94d28f;
        }
        QPushButton#startButton:disabled {
            background-color: #313244;
            color: #585b70;
        }
        QPushButton#stopButton {
            background-color: #f38ba8;
            color: #11111b;
        }
        QPushButton#stopButton:hover {
            background-color: #e07a97;
        }
        QPushButton#stopButton:disabled {
            background-color: #313244;
            color: #585b70;
        }
        QPushButton#folderButton {
            background-color: #89b4fa;
            color: #11111b;
            font-size: 12px;
            padding: 8px 15px;
        }
        QPushButton#folderButton:hover {
            background-color: #74a2f6;
        }
        """
        self.setStyleSheet(qss)

    def start_recording(self):
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # Update UI indicators
        self.status_dot.setStyleSheet("color: #f38ba8;")  # Red Dot
        self.status_text.setText("Status: Recording...")
        self.steps_label.setText("Total Steps: 0")
        self.last_action_label.setText("Last Action: None")
        
        # Trigger recorder start
        self.recorder.start()

    def stop_recording(self):
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        
        # Trigger recorder stop
        zip_path = self.recorder.stop()
        
        # Update UI indicators
        self.status_dot.setStyleSheet("color: #585b70;")  # Gray Dot
        self.status_text.setText("Status: Ready")
        
        if zip_path:
            filename = os.path.basename(zip_path)
            self.last_action_label.setText(f"Exported: {filename}")
        else:
            self.last_action_label.setText("Export failed or empty session.")

    def on_step_logged(self, count, desc):
        # Called thread-safely by custom signal
        self.steps_label.setText(f"Total Steps: {count}")
        self.last_action_label.setText(f"Last Action: {desc}")

    def open_output_folder(self):
        output_dir = os.path.abspath("output")
        os.makedirs(output_dir, exist_ok=True)
        if os.name == 'nt':
            os.startfile(output_dir)
        else:
            # Unix-like systems fallback
            subprocess.call(["open", output_dir])

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

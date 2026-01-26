# client_gui.py
"""
QuickIM GUI Client
=========================================
"""

import sys
import socket
import threading
import uuid
import random
import hashlib
import os
from datetime import datetime
from typing import Optional, Dict
from dataclasses import dataclass
from io import BytesIO

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QTextEdit, QFrame, QMessageBox, QDialog, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QPoint, QRect, QBuffer
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QTextCursor, QPainter, QBrush,
    QPen, QPixmap, QLinearGradient, QImage
)

from protocol import (
    Command, ResponseCode, PresenceStatus, AckStatus, ActionCode,
    Message, RegisterMessage, LoginMessage, LogoutMessage,
    SendMsgMessage, ReceiveMsgMessage, MsgAckMessage,
    AddContactMessage, RemoveContactMessage, ContactListReqMessage,
    ContactListMessage, UserSearchMessage, UserSearchResultMessage,
    PresenceMessage, ResponseMessage, ErrorMessage,
    EarthquakeSendMessage, EarthquakeRecvMessage,
    AvatarSetMessage, AvatarGetMessage, AvatarDataMessage,
    ContactInfo, MAX_AVATAR_SIZE,
    send_message, recv_message,
    build_register, build_login, build_logout,
    build_send_msg, build_add_contact, build_remove_contact,
    build_contact_list_req, build_user_search, build_earthquake_send,
    build_avatar_set, build_avatar_get
)


# ============== Colors ==============

COLORS = {
    'bg_primary': '#343538',
    'bg_secondary': '#2d2e31',
    'bg_tertiary': '#3a3b3f',
    'bg_input': '#2a2b2e',
    'bg_hover': '#3f4043',
    'border': '#444548',
    'border_light': '#4a4b4f',
    'green_primary': '#0a3b0e',
    'green_light': '#0d4a12',
    'green_lighter': '#106316',
    'green_text': '#2ecc40',
    'text_primary': '#e8e8e8',
    'text_secondary': '#a0a0a0',
    'text_dim': '#707070',
    'online': '#2ecc40',
    'offline': '#606060',
    'error': '#e74c3c',
    'success': '#2ecc40',
    'earthquake': '#ff6600',
}

AVATAR_COLORS = [
    ('#667eea', '#764ba2'), ('#f093fb', '#f5576c'), ('#4facfe', '#00f2fe'),
    ('#43e97b', '#38f9d7'), ('#fa709a', '#fee140'), ('#30cfd0', '#330867'),
    ('#a8edea', '#fed6e3'), ('#5ee7df', '#b490ca'), ('#d299c2', '#fef9d7'),
    ('#89f7fe', '#66a6ff'), ('#cd9cf2', '#f6f3ff'), ('#fddb92', '#d1fdff'),
]


DARK_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_primary']};
    font-family: 'Segoe UI', 'Arial', sans-serif;
}}
QLineEdit {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 10px 12px;
    color: {COLORS['text_primary']};
    font-size: 13px;
}}
QLineEdit:focus {{
    border: 1px solid {COLORS['green_light']};
}}
QPushButton {{
    background-color: {COLORS['bg_tertiary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 10px 20px;
    color: {COLORS['text_primary']};
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
}}
QPushButton#primaryBtn {{
    background-color: {COLORS['green_primary']};
    border: 1px solid {COLORS['green_light']};
}}
QPushButton#primaryBtn:hover {{
    background-color: {COLORS['green_light']};
}}
QPushButton#earthquakeBtn {{
    background-color: #4a2800;
    border: 1px solid {COLORS['earthquake']};
    color: {COLORS['earthquake']};
}}
QPushButton#earthquakeBtn:hover {{
    background-color: #5a3800;
}}
QListWidget {{
    background-color: {COLORS['bg_primary']};
    border: none;
}}
QTextEdit {{
    background-color: {COLORS['bg_primary']};
    border: none;
    color: {COLORS['text_primary']};
}}
QScrollBar:vertical {{
    background-color: {COLORS['bg_secondary']};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background-color: {COLORS['border']};
    border-radius: 5px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QDialog {{
    background-color: {COLORS['bg_primary']};
}}
"""


# ============== Avatar Manager ==============

class AvatarManager:
    """Manages avatar caching and generation."""
    
    _cache: Dict[str, QPixmap] = {}
    _custom_avatars: Dict[str, bytes] = {}
    
    @classmethod
    def set_custom_avatar(cls, username: str, data: bytes):
        """Store custom avatar data."""
        cls._custom_avatars[username] = data
        # Clear cache for this user
        keys_to_remove = [k for k in cls._cache if k.startswith(f"{username}_")]
        for key in keys_to_remove:
            del cls._cache[key]
    
    @classmethod
    def has_custom_avatar(cls, username: str) -> bool:
        return username in cls._custom_avatars and len(cls._custom_avatars[username]) > 0
    
    @classmethod
    def get_avatar(cls, username: str, size: int = 40) -> QPixmap:
        cache_key = f"{username}_{size}"
        
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        # Check for custom avatar
        if username in cls._custom_avatars and cls._custom_avatars[username]:
            pixmap = cls._load_custom_avatar(cls._custom_avatars[username], size)
            if pixmap:
                cls._cache[cache_key] = pixmap
                return pixmap
        
        # Generate default avatar
        pixmap = cls._generate_default_avatar(username, size)
        cls._cache[cache_key] = pixmap
        return pixmap
    
    @classmethod
    def _load_custom_avatar(cls, data: bytes, size: int) -> Optional[QPixmap]:
        """Load and resize custom avatar."""
        try:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if pixmap.isNull():
                return None
            
            # Scale and crop to circle
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            
            # Center crop
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            cropped = scaled.copy(x, y, size, size)
            
            # Make circular
            result = QPixmap(size, size)
            result.fill(Qt.transparent)
            
            painter = QPainter(result)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(cropped))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, size, size)
            painter.end()
            
            return result
        except:
            return None
    
    @classmethod
    def _generate_default_avatar(cls, username: str, size: int) -> QPixmap:
        """Generate gradient avatar with initials."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get colors
        hash_val = int(hashlib.md5(username.lower().encode()).hexdigest(), 16)
        color1, color2 = AVATAR_COLORS[hash_val % len(AVATAR_COLORS)]
        
        gradient = QLinearGradient(0, 0, size, size)
        gradient.setColorAt(0, QColor(color1))
        gradient.setColorAt(1, QColor(color2))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        
        # Initials
        initials = username[:2].upper() if len(username) >= 2 else username[0].upper()
        font = QFont("Segoe UI", size // 3, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(0, 0, size, size), Qt.AlignCenter, initials)
        
        painter.end()
        return pixmap
    
    @classmethod
    def clear_cache(cls):
        cls._cache.clear()


# ============== Avatar Widget ==============

class AvatarWidget(QLabel):
    clicked = pyqtSignal()
    
    def __init__(self, username: str = "", size: int = 40, clickable: bool = False, parent=None):
        super().__init__(parent)
        self._username = username
        self._size = size
        self._clickable = clickable
        self._show_status = False
        self._status = PresenceStatus.OFFLINE
        
        self.setFixedSize(size, size)
        if clickable:
            self.setCursor(Qt.PointingHandCursor)
        self.update_avatar()
    
    def set_username(self, username: str):
        self._username = username
        self.update_avatar()
    
    def set_status(self, status: PresenceStatus, show: bool = True):
        self._show_status = show
        self._status = status
        self.update_avatar()
    
    def update_avatar(self):
        if not self._username:
            self.clear()
            return
        
        base_pixmap = AvatarManager.get_avatar(self._username, self._size)
        
        if not self._show_status:
            self.setPixmap(base_pixmap)
            return
        
        # Add status indicator
        pixmap = QPixmap(self._size, self._size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, base_pixmap)
        
        status_size = self._size // 4
        status_x = self._size - status_size - 1
        status_y = self._size - status_size - 1
        
        painter.setBrush(QColor(COLORS['bg_secondary']))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(status_x - 2, status_y - 2, status_size + 4, status_size + 4)
        
        color = COLORS['online'] if self._status == PresenceStatus.ONLINE else COLORS['offline']
        painter.setBrush(QColor(color))
        painter.drawEllipse(status_x, status_y, status_size, status_size)
        
        painter.end()
        self.setPixmap(pixmap)
    
    def mousePressEvent(self, event):
        if self._clickable:
            self.clicked.emit()


# ============== Network Client ==============

class NetworkClient:
    def __init__(self):
        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.lock = threading.Lock()
    
    def connect(self, host: str, port: int) -> tuple:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((host, port))
            self.sock.settimeout(None)
            self.connected = True
            return True, "Connected"
        except socket.timeout:
            return False, "Connection timed out"
        except socket.error as e:
            return False, f"Connection failed: {e}"
    
    def disconnect(self):
        self.connected = False
        if self.sock:
            try:
                send_message(self.sock, build_logout())
                self.sock.close()
            except:
                pass
            self.sock = None
    
    def send(self, msg) -> bool:
        if not self.connected:
            return False
        with self.lock:
            return send_message(self.sock, msg)
    
    def receive(self):
        if not self.connected:
            return None
        return recv_message(self.sock)


# ============== Receiver Thread ==============

class ReceiverThread(QThread):
    message_received = pyqtSignal(object)
    disconnected = pyqtSignal()
    
    def __init__(self, client: NetworkClient):
        super().__init__()
        self.client = client
        self.running = True
    
    def run(self):
        while self.running and self.client.connected:
            msg = self.client.receive()
            if msg:
                self.message_received.emit(msg)
            elif self.running:
                self.disconnected.emit()
                break
    
    def stop(self):
        self.running = False


# ============== Data Models ==============

@dataclass
class Contact:
    username: str
    status: PresenceStatus = PresenceStatus.OFFLINE
    unread: int = 0

@dataclass
class ChatMessage:
    sender: str
    content: str
    timestamp: str
    is_mine: bool


# ============== Window Shaker ==============

class WindowShaker:
    def __init__(self, window):
        self.window = window
        self.original_pos = None
        self.shake_timer = None
        self.shake_count = 0
        self.max_shakes = 0
        self.intensity = 5
    
    def shake(self, intensity: int = 5, duration_ms: int = 1000):
        self.intensity = max(1, min(10, intensity))
        self.original_pos = self.window.pos()
        self.shake_count = 0
        self.max_shakes = duration_ms // 25
        
        if self.shake_timer:
            self.shake_timer.stop()
        
        self.shake_timer = QTimer()
        self.shake_timer.timeout.connect(self._do_shake)
        self.shake_timer.start(25)
    
    def _do_shake(self):
        if self.shake_count >= self.max_shakes:
            self.shake_timer.stop()
            self.window.move(self.original_pos)
            return
        
        dx = random.randint(-self.intensity * 4, self.intensity * 4)
        dy = random.randint(-self.intensity * 4, self.intensity * 4)
        self.window.move(QPoint(self.original_pos.x() + dx, self.original_pos.y() + dy))
        self.shake_count += 1


# ============== Contact Widget ==============

class ContactWidget(QWidget):
    clicked = pyqtSignal(str)
    
    def __init__(self, contact: Contact, is_selected: bool = False):
        super().__init__()
        self.contact = contact
        self.is_selected = is_selected
        self._hovered = False
        self.init_ui()
    
    def init_ui(self):
        self.setFixedHeight(60)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 16, 8)
        layout.setSpacing(12)
        
        self.avatar = AvatarWidget(self.contact.username, size=42)
        self.avatar.set_status(self.contact.status, show=True)
        layout.addWidget(self.avatar)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        self.name_label = QLabel(self.contact.username)
        self.name_label.setFont(QFont("Segoe UI", 12, QFont.DemiBold))
        color = COLORS['green_text'] if self.is_selected else COLORS['text_primary']
        self.name_label.setStyleSheet(f"color: {color};")
        info_layout.addWidget(self.name_label)
        
        status_text = "Online" if self.contact.status == PresenceStatus.ONLINE else "Offline"
        self.status_label = QLabel(status_text)
        self.status_label.setFont(QFont("Segoe UI", 10))
        status_color = COLORS['online'] if self.contact.status == PresenceStatus.ONLINE else COLORS['text_dim']
        self.status_label.setStyleSheet(f"color: {status_color};")
        info_layout.addWidget(self.status_label)
        
        layout.addLayout(info_layout, 1)
        
        if self.contact.unread > 0:
            badge = QLabel(str(self.contact.unread))
            badge.setFont(QFont("Segoe UI", 10, QFont.Bold))
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(24, 24)
            badge.setStyleSheet(f"background-color: {COLORS['green_light']}; color: white; border-radius: 12px;")
            layout.addWidget(badge)
        
        self.update_style()
        self.setCursor(Qt.PointingHandCursor)
    
    def update_style(self):
        if self.is_selected:
            self.setStyleSheet(f"background-color: {COLORS['green_primary']}; border-radius: 4px;")
        elif self._hovered:
            self.setStyleSheet(f"background-color: {COLORS['bg_hover']}; border-radius: 4px;")
        else:
            self.setStyleSheet("background-color: transparent;")
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.contact.username)
    
    def enterEvent(self, event):
        self._hovered = True
        self.update_style()
    
    def leaveEvent(self, event):
        self._hovered = False
        self.update_style()


# ============== Add Contact Dialog ==============

class AddContactDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.username = ""
        self.setWindowTitle("Add Contact")
        self.setFixedSize(380, 180)
        self.setStyleSheet(DARK_STYLE)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 28)
        
        title = QLabel("Add Contact")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(title)
        
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter username")
        self.input.returnPressed.connect(self.accept)
        layout.addWidget(self.input)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        add_btn = QPushButton("Add")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.accept)
        btn_layout.addWidget(add_btn)
        
        layout.addLayout(btn_layout)
    
    def accept(self):
        self.username = self.input.text().strip()
        if self.username:
            super().accept()
    
    def get_username(self):
        return self.username


# ============== Login Window ==============

class LoginWindow(QMainWindow):
    login_success = pyqtSignal(NetworkClient, str, bytes)  # Added avatar_data
    
    def __init__(self):
        super().__init__()
        self.client = NetworkClient()
        self.avatar_data = b''
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("QuickIM")
        self.setFixedSize(440, 600)
        self.setStyleSheet(DARK_STYLE)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        top_bar = QLabel()
        top_bar.setFixedHeight(4)
        top_bar.setStyleSheet(f"background-color: {COLORS['green_primary']};")
        layout.addWidget(top_bar)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(48, 28, 48, 28)
        
        # Avatar selection
        avatar_section = QHBoxLayout()
        avatar_section.setAlignment(Qt.AlignCenter)
        
        avatar_container = QVBoxLayout()
        avatar_container.setAlignment(Qt.AlignCenter)
        avatar_container.setSpacing(8)
        
        self.avatar_preview = QLabel()
        self.avatar_preview.setFixedSize(80, 80)
        self.avatar_preview.setStyleSheet(f"""
            background-color: {COLORS['bg_tertiary']};
            border-radius: 40px;
            border: 2px dashed {COLORS['border_light']};
        """)
        self.avatar_preview.setAlignment(Qt.AlignCenter)
        self.avatar_preview.setText("No\nAvatar")
        self.avatar_preview.setCursor(Qt.PointingHandCursor)
        self.avatar_preview.mousePressEvent = lambda e: self.select_avatar()
        avatar_container.addWidget(self.avatar_preview, alignment=Qt.AlignCenter)
        
        avatar_btn = QPushButton("Choose Avatar")
        avatar_btn.setFont(QFont("Segoe UI", 10))
        avatar_btn.setFixedWidth(120)
        avatar_btn.clicked.connect(self.select_avatar)
        avatar_container.addWidget(avatar_btn, alignment=Qt.AlignCenter)
        
        avatar_section.addLayout(avatar_container)
        content_layout.addLayout(avatar_section)
        
        content_layout.addSpacing(8)
        
        # Title
        title = QLabel("QuickIM")
        title.setFont(QFont("Segoe UI", 26, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title)
        
        subtitle = QLabel("Messaging your way.")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet(f"color: {COLORS['text_dim']};")
        subtitle.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(subtitle)
        
        content_layout.addSpacing(16)
        
        # Server
        server_label = QLabel("SERVER")
        server_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        server_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        content_layout.addWidget(server_label)
        
        server_layout = QHBoxLayout()
        server_layout.setSpacing(12)
        
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Host")
        self.host_input.setText("localhost")
        server_layout.addWidget(self.host_input, 3)
        
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("Port")
        self.port_input.setText("9999")
        self.port_input.setFixedWidth(80)
        server_layout.addWidget(self.port_input)
        
        content_layout.addLayout(server_layout)
        content_layout.addSpacing(8)
        
        # Credentials
        cred_label = QLabel("CREDENTIALS")
        cred_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        cred_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        content_layout.addWidget(cred_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        content_layout.addWidget(self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.login)
        content_layout.addWidget(self.password_input)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setFixedHeight(36)
        content_layout.addWidget(self.status_label)
        
        content_layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        register_btn = QPushButton("Register")
        register_btn.setFixedHeight(44)
        register_btn.clicked.connect(self.register)
        btn_layout.addWidget(register_btn)
        
        login_btn = QPushButton("Login")
        login_btn.setObjectName("primaryBtn")
        login_btn.setFixedHeight(44)
        login_btn.clicked.connect(self.login)
        btn_layout.addWidget(login_btn)
        
        content_layout.addLayout(btn_layout)
        layout.addWidget(content)
        
        self.center_window()
    
    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)
    
    def select_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Avatar", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        
        if not file_path:
            return
        
        try:
            # Load and resize image
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", "Could not load image")
                return
            
            # Scale to max 256x256 for storage
            size = 256
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            cropped = scaled.copy(x, y, size, size)
            
            # Convert to bytes
            buffer = QBuffer()
            buffer.open(QBuffer.WriteOnly)
            cropped.save(buffer, "PNG")
            self.avatar_data = bytes(buffer.data())
            buffer.close()
            
            if len(self.avatar_data) > MAX_AVATAR_SIZE:
                # Try JPEG with lower quality
                buffer = QBuffer()
                buffer.open(QBuffer.WriteOnly)
                cropped.save(buffer, "JPEG", 70)
                self.avatar_data = bytes(buffer.data())
                buffer.close()
            
            if len(self.avatar_data) > MAX_AVATAR_SIZE:
                QMessageBox.warning(self, "Error", "Image too large. Please choose a smaller image.")
                self.avatar_data = b''
                return
            
            # Show preview (circular)
            preview_size = 80
            preview = cropped.scaled(preview_size, preview_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            circular = QPixmap(preview_size, preview_size)
            circular.fill(Qt.transparent)
            painter = QPainter(circular)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(preview))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, preview_size, preview_size)
            painter.end()
            
            self.avatar_preview.setPixmap(circular)
            self.avatar_preview.setText("")
            self.avatar_preview.setStyleSheet(f"border-radius: 40px;")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load image: {e}")
    
    def connect_to_server(self) -> bool:
        if self.client.connected:
            return True
        
        host = self.host_input.text().strip()
        try:
            port = int(self.port_input.text().strip())
        except ValueError:
            self.show_status("Invalid port", error=True)
            return False
        
        self.show_status("Connecting...", error=False)
        QApplication.processEvents()
        
        success, message = self.client.connect(host, port)
        if not success:
            self.show_status(message, error=True)
            return False
        return True
    
    def login(self):
        if not self.connect_to_server():
            return
        
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            self.show_status("Enter username and password", error=True)
            return
        
        self.show_status("Logging in...", error=False)
        QApplication.processEvents()
        
        self.client.send(build_login(username, password))
        response = self.client.receive()
        
        if isinstance(response, ResponseMessage) and response.code == ResponseCode.SUCCESS:
            self.login_success.emit(self.client, username, self.avatar_data)
            self.close()
        else:
            msg = response.message if isinstance(response, ResponseMessage) else "Login failed"
            self.show_status(msg, error=True)
    
    def register(self):
        if not self.connect_to_server():
            return
        
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            self.show_status("Enter username and password", error=True)
            return
        
        if len(username) < 3:
            self.show_status("Username: min 3 characters", error=True)
            return
        
        if len(password) < 4:
            self.show_status("Password: min 4 characters", error=True)
            return
        
        self.show_status("Registering...", error=False)
        QApplication.processEvents()
        
        self.client.send(build_register(username, password))
        response = self.client.receive()
        
        if isinstance(response, ResponseMessage) and response.code == ResponseCode.SUCCESS:
            self.show_status("Registered! You can now login.", error=False)
        else:
            msg = response.message if isinstance(response, ResponseMessage) else "Registration failed"
            self.show_status(msg, error=True)
    
    def show_status(self, message: str, error: bool = True):
        color = COLORS['error'] if error else COLORS['success']
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")


# ============== Chat Window ==============

class ChatWindow(QMainWindow):
    def __init__(self, client: NetworkClient, username: str, avatar_data: bytes = b''):
        super().__init__()
        self.client = client
        self.username = username
        self.contacts: Dict[str, Contact] = {}
        self.chat_history: Dict[str, list] = {}
        self.selected_contact: Optional[str] = None
        self.receiver_thread: Optional[ReceiverThread] = None
        self.shaker = WindowShaker(self)
        self.pending_avatar_requests: set = set()
        
        # Set own avatar
        if avatar_data:
            AvatarManager.set_custom_avatar(username, avatar_data)
            # Upload to server
            self.client.send(build_avatar_set(avatar_data))
        
        self.init_ui()
        self.start_receiving()
        self.client.send(build_contact_list_req())
    
    def init_ui(self):
        self.setWindowTitle(f"QuickIM - {self.username}")
        self.setMinimumSize(1000, 650)
        self.resize(1150, 750)
        self.setStyleSheet(DARK_STYLE)
        
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        main_layout.addWidget(self.create_sidebar())
        
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        main_layout.addWidget(sep)
        
        main_layout.addWidget(self.create_chat_area(), 1)
        
        self.center_window()
    
    def create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(320)
        sidebar.setStyleSheet(f"background-color: {COLORS['bg_secondary']};")
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet(f"background-color: {COLORS['green_primary']};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(12)
        
        self.user_avatar = AvatarWidget(self.username, size=48, clickable=True)
        self.user_avatar.clicked.connect(self.change_avatar)
        header_layout.addWidget(self.user_avatar)
        
        user_info = QVBoxLayout()
        user_info.setSpacing(2)
        
        user_label = QLabel(self.username)
        user_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        user_info.addWidget(user_label)
        
        change_label = QLabel("Click avatar to change")
        change_label.setFont(QFont("Segoe UI", 9))
        change_label.setStyleSheet(f"color: {COLORS['green_text']};")
        user_info.addWidget(change_label)
        
        header_layout.addLayout(user_info, 1)
        layout.addWidget(header)
        
        # Contacts header
        ch = QWidget()
        ch.setFixedHeight(48)
        ch_layout = QHBoxLayout(ch)
        ch_layout.setContentsMargins(20, 0, 20, 0)
        ch_layout.addWidget(QLabel("CONTACTS"))
        layout.addWidget(ch)
        
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        layout.addWidget(sep)
        
        self.contacts_list = QListWidget()
        layout.addWidget(self.contacts_list, 1)
        
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {COLORS['border']};")
        layout.addWidget(sep2)
        
        btn_container = QWidget()
        btn_container.setFixedHeight(68)
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(16, 0, 16, 0)
        
        add_btn = QPushButton("+ Add Contact")
        add_btn.setObjectName("primaryBtn")
        add_btn.setFixedHeight(42)
        add_btn.clicked.connect(self.show_add_contact_dialog)
        btn_layout.addWidget(add_btn)
        
        layout.addWidget(btn_container)
        
        return sidebar
    
    def create_chat_area(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        self.chat_header = QWidget()
        self.chat_header.setFixedHeight(80)
        self.chat_header.setStyleSheet(f"background-color: {COLORS['bg_secondary']};")
        
        header_layout = QHBoxLayout(self.chat_header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(16)
        
        self.header_avatar = AvatarWidget("", size=48)
        self.header_avatar.setVisible(False)
        header_layout.addWidget(self.header_avatar)
        
        title_widget = QWidget()
        title_layout = QVBoxLayout(title_widget)
        title_layout.setSpacing(2)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        self.chat_title = QLabel("Select a contact")
        self.chat_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.chat_title.setStyleSheet(f"color: {COLORS['text_secondary']};")
        title_layout.addWidget(self.chat_title)
        
        self.chat_status = QLabel("")
        self.chat_status.setFont(QFont("Segoe UI", 11))
        title_layout.addWidget(self.chat_status)
        
        header_layout.addWidget(title_widget, 1)
        
        self.earthquake_btn = QPushButton("Shake!")
        self.earthquake_btn.setObjectName("earthquakeBtn")
        self.earthquake_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.earthquake_btn.setFixedHeight(38)
        self.earthquake_btn.setMinimumWidth(90)
        self.earthquake_btn.clicked.connect(self.send_earthquake)
        self.earthquake_btn.setVisible(False)
        header_layout.addWidget(self.earthquake_btn)
        
        layout.addWidget(self.chat_header)
        
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        layout.addWidget(sep)
        
        self.messages_area = QTextEdit()
        self.messages_area.setReadOnly(True)
        self.messages_area.setStyleSheet(f"padding: 20px;")
        layout.addWidget(self.messages_area, 1)
        
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {COLORS['border']};")
        layout.addWidget(sep2)
        
        input_container = QWidget()
        input_container.setFixedHeight(76)
        input_container.setStyleSheet(f"background-color: {COLORS['bg_secondary']};")
        
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(20, 0, 20, 0)
        input_layout.setSpacing(12)
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.setFixedHeight(44)
        self.message_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.message_input, 1)
        
        send_btn = QPushButton("Send")
        send_btn.setObjectName("primaryBtn")
        send_btn.setFixedSize(90, 44)
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn)
        
        layout.addWidget(input_container)
        
        return widget
    
    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)
    
    def start_receiving(self):
        self.receiver_thread = ReceiverThread(self.client)
        self.receiver_thread.message_received.connect(self.on_message_received)
        self.receiver_thread.disconnected.connect(self.on_disconnected)
        self.receiver_thread.start()
    
    def change_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Avatar", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return
        
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                return
            
            size = 256
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            cropped = scaled.copy(x, y, size, size)
            
            buffer = QBuffer()
            buffer.open(QBuffer.WriteOnly)
            cropped.save(buffer, "PNG")
            avatar_data = bytes(buffer.data())
            buffer.close()
            
            if len(avatar_data) > MAX_AVATAR_SIZE:
                buffer = QBuffer()
                buffer.open(QBuffer.WriteOnly)
                cropped.save(buffer, "JPEG", 70)
                avatar_data = bytes(buffer.data())
                buffer.close()
            
            if len(avatar_data) > MAX_AVATAR_SIZE:
                QMessageBox.warning(self, "Error", "Image too large")
                return
            
            AvatarManager.set_custom_avatar(self.username, avatar_data)
            self.user_avatar.update_avatar()
            self.client.send(build_avatar_set(avatar_data))
            
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
    
    def request_avatar(self, username: str):
        if username not in self.pending_avatar_requests and not AvatarManager.has_custom_avatar(username):
            self.pending_avatar_requests.add(username)
            self.client.send(build_avatar_get(username))
    
    def update_contacts_list(self):
        self.contacts_list.clear()
        
        if not self.contacts:
            item = QListWidgetItem()
            label = QLabel("No contacts yet")
            label.setFont(QFont("Segoe UI", 11))
            label.setStyleSheet(f"color: {COLORS['text_dim']}; padding: 24px;")
            label.setAlignment(Qt.AlignCenter)
            item.setSizeHint(QSize(0, 80))
            self.contacts_list.addItem(item)
            self.contacts_list.setItemWidget(item, label)
            return
        
        sorted_contacts = sorted(
            self.contacts.values(),
            key=lambda c: (0 if c.status == PresenceStatus.ONLINE else 1, c.username.lower())
        )
        
        for contact in sorted_contacts:
            # Request avatar if not cached
            self.request_avatar(contact.username)
            
            is_selected = contact.username == self.selected_contact
            widget = ContactWidget(contact, is_selected)
            widget.clicked.connect(self.select_contact)
            
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 64))
            self.contacts_list.addItem(item)
            self.contacts_list.setItemWidget(item, widget)
    
    def select_contact(self, username: str):
        self.selected_contact = username
        
        if username in self.contacts:
            self.contacts[username].unread = 0
        
        self.request_avatar(username)
        
        self.update_contacts_list()
        self.update_chat_display()
        
        contact = self.contacts.get(username)
        status = contact.status if contact else PresenceStatus.OFFLINE
        
        self.header_avatar.set_username(username)
        self.header_avatar.set_status(status, show=True)
        self.header_avatar.setVisible(True)
        
        self.chat_title.setText(username)
        self.chat_title.setStyleSheet(f"color: {COLORS['text_primary']};")
        
        self.earthquake_btn.setVisible(status == PresenceStatus.ONLINE)
        
        if status == PresenceStatus.ONLINE:
            self.chat_status.setText("Online")
            self.chat_status.setStyleSheet(f"color: {COLORS['online']};")
        else:
            self.chat_status.setText("Offline")
            self.chat_status.setStyleSheet(f"color: {COLORS['text_dim']};")
        
        self.message_input.setFocus()
    
    def update_chat_display(self):
        self.messages_area.clear()
        
        if not self.selected_contact:
            self.messages_area.setHtml(f'''
                <div style="text-align: center; margin-top: 140px;">
                    <p style="color: {COLORS['text_dim']};">Select a contact</p>
                </div>
            ''')
            return
        
        history = self.chat_history.get(self.selected_contact, [])
        
        if not history:
            self.messages_area.setHtml(f'''
                <div style="text-align: center; margin-top: 140px;">
                    <p style="color: {COLORS['text_dim']};">No messages yet</p>
                </div>
            ''')
            return
        
        html = "<div style='font-family: Segoe UI;'>"
        for msg in history:
            is_system = msg.content.startswith("[") and msg.content.endswith("]")
            
            if is_system:
                who = "You" if msg.is_mine else msg.sender
                html += f'''
                <div style="text-align: center; margin: 12px 0;">
                    <span style="color: {COLORS['earthquake']}; font-size: 12px; font-style: italic;">
                        {who} {msg.content[1:-1].lower()}
                    </span>
                </div>
                '''
            elif msg.is_mine:
                html += f'''
                <div style="text-align: right; margin: 14px 0;">
                    <div style="display: inline-block; background-color: {COLORS['green_primary']}; 
                         padding: 10px 14px; border-radius: 12px; max-width: 60%;">
                        <span style="color: {COLORS['text_primary']};">{msg.content}</span>
                    </div>
                    <div><span style="color: {COLORS['text_dim']}; font-size: 11px;">{msg.timestamp}</span></div>
                </div>
                '''
            else:
                html += f'''
                <div style="margin: 14px 0;">
                    <span style="color: {COLORS['text_secondary']}; font-size: 11px;">{msg.sender}</span>
                    <div style="display: inline-block; background-color: {COLORS['bg_tertiary']}; 
                         padding: 10px 14px; border-radius: 12px; max-width: 60%;">
                        <span style="color: {COLORS['text_primary']};">{msg.content}</span>
                    </div>
                    <div><span style="color: {COLORS['text_dim']}; font-size: 11px;">{msg.timestamp}</span></div>
                </div>
                '''
        html += "</div>"
        
        self.messages_area.setHtml(html)
        cursor = self.messages_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.messages_area.setTextCursor(cursor)
    
    def send_message(self):
        if not self.selected_contact:
            return
        
        content = self.message_input.text().strip()
        if not content:
            return
        
        msg_id = str(uuid.uuid4())[:8]
        self.client.send(build_send_msg(self.selected_contact, content, msg_id))
        
        timestamp = datetime.now().strftime("%H:%M")
        chat_msg = ChatMessage(self.username, content, timestamp, is_mine=True)
        
        if self.selected_contact not in self.chat_history:
            self.chat_history[self.selected_contact] = []
        self.chat_history[self.selected_contact].append(chat_msg)
        
        self.message_input.clear()
        self.update_chat_display()
    
    def send_earthquake(self):
        if not self.selected_contact:
            return
        
        contact = self.contacts.get(self.selected_contact)
        if not contact or contact.status != PresenceStatus.ONLINE:
            return
        
        self.client.send(build_earthquake_send(self.selected_contact, 8))
        
        timestamp = datetime.now().strftime("%H:%M")
        chat_msg = ChatMessage(self.username, "[Sent an earthquake!]", timestamp, is_mine=True)
        
        if self.selected_contact not in self.chat_history:
            self.chat_history[self.selected_contact] = []
        self.chat_history[self.selected_contact].append(chat_msg)
        
        self.update_chat_display()
    
    def show_add_contact_dialog(self):
        dialog = AddContactDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            username = dialog.get_username()
            if username == self.username:
                QMessageBox.warning(self, "Error", "Cannot add yourself")
                return
            if username in self.contacts:
                QMessageBox.warning(self, "Error", "Contact exists")
                return
            self.client.send(build_add_contact(username))
    
    def on_message_received(self, msg):
        if isinstance(msg, ReceiveMsgMessage):
            sender = msg.from_user
            timestamp = datetime.now().strftime("%H:%M")
            chat_msg = ChatMessage(sender, msg.content, timestamp, is_mine=False)
            
            if sender not in self.chat_history:
                self.chat_history[sender] = []
            self.chat_history[sender].append(chat_msg)
            
            self.request_avatar(sender)
            
            if sender != self.selected_contact:
                if sender in self.contacts:
                    self.contacts[sender].unread += 1
                else:
                    self.contacts[sender] = Contact(sender, PresenceStatus.ONLINE, 1)
                self.update_contacts_list()
            else:
                self.update_chat_display()
        
        elif isinstance(msg, ContactListMessage):
            for c in msg.contacts:
                if c.username in self.contacts:
                    self.contacts[c.username].status = c.status
                else:
                    self.contacts[c.username] = Contact(c.username, c.status)
                self.request_avatar(c.username)
            self.update_contacts_list()
        
        elif isinstance(msg, PresenceMessage):
            username = msg.username
            status = msg.status
            
            if username in self.contacts:
                self.contacts[username].status = status
                self.update_contacts_list()
                
                if username == self.selected_contact:
                    self.header_avatar.set_status(status, show=True)
                    self.earthquake_btn.setVisible(status == PresenceStatus.ONLINE)
                    if status == PresenceStatus.ONLINE:
                        self.chat_status.setText("Online")
                        self.chat_status.setStyleSheet(f"color: {COLORS['online']};")
                    else:
                        self.chat_status.setText("Offline")
                        self.chat_status.setStyleSheet(f"color: {COLORS['text_dim']};")
        
        elif isinstance(msg, ResponseMessage):
            if msg.action == ActionCode.ADD_CONTACT:
                if msg.code == ResponseCode.SUCCESS:
                    self.client.send(build_contact_list_req())
                else:
                    QMessageBox.warning(self, "Error", msg.message)
        
        elif isinstance(msg, ErrorMessage):
            QMessageBox.warning(self, "Error", msg.message)
        
        elif isinstance(msg, EarthquakeRecvMessage):
            from_user = msg.from_user
            timestamp = datetime.now().strftime("%H:%M")
            chat_msg = ChatMessage(from_user, "[Sent you an earthquake!]", timestamp, is_mine=False)
            
            if from_user not in self.chat_history:
                self.chat_history[from_user] = []
            self.chat_history[from_user].append(chat_msg)
            
            if from_user == self.selected_contact:
                self.update_chat_display()
            else:
                if from_user in self.contacts:
                    self.contacts[from_user].unread += 1
                self.update_contacts_list()
            
            self.shaker.shake(intensity=msg.intensity, duration_ms=1000)
        
        elif isinstance(msg, AvatarDataMessage):
            username = msg.username
            self.pending_avatar_requests.discard(username)
            
            if msg.avatar_data:
                AvatarManager.set_custom_avatar(username, msg.avatar_data)
                
                # Refresh UI
                self.update_contacts_list()
                if username == self.selected_contact:
                    self.header_avatar.update_avatar()
    
    def on_disconnected(self):
        QMessageBox.critical(self, "Disconnected", "Connection lost")
        self.close()
    
    def closeEvent(self, event):
        if self.receiver_thread:
            self.receiver_thread.stop()
        self.client.disconnect()
        event.accept()


# ============== Main ==============

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS['bg_primary']))
    palette.setColor(QPalette.WindowText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Base, QColor(COLORS['bg_input']))
    palette.setColor(QPalette.Text, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Button, QColor(COLORS['bg_tertiary']))
    palette.setColor(QPalette.ButtonText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Highlight, QColor(COLORS['green_primary']))
    app.setPalette(palette)
    
    login_window = LoginWindow()
    chat_window = None
    
    def on_login_success(client, username, avatar_data):
        nonlocal chat_window
        chat_window = ChatWindow(client, username, avatar_data)
        chat_window.show()
    
    login_window.login_success.connect(on_login_success)
    login_window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

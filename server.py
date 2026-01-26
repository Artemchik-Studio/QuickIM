# server.py
"""
QuickIM Server
======================================
"""

import socket
import threading
import sqlite3
import hashlib
import secrets
import logging
from datetime import datetime
from typing import Dict, Optional, List

from protocol import (
    Command, ResponseCode, PresenceStatus, AckStatus, ActionCode,
    Message, RegisterMessage, LoginMessage, LogoutMessage,
    SendMsgMessage, AddContactMessage, RemoveContactMessage,
    ContactListReqMessage, UserSearchMessage,
    EarthquakeSendMessage, AvatarSetMessage, AvatarGetMessage,
    ContactInfo, MAX_AVATAR_SIZE,
    send_message, recv_message,
    build_response, build_presence, build_contact_list,
    build_msg_ack, build_error, build_receive_msg,
    build_user_search_result, build_earthquake_recv, build_avatar_data
)

HOST = '0.0.0.0'
PORT = 9999
DATABASE = 'im_database.db'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.local = threading.local()
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                avatar BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                contact_id INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (contact_id) REFERENCES users(id),
                UNIQUE(user_id, contact_id)
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    
    def register_user(self, username: str, password: str) -> tuple:
        conn = self._get_conn()
        try:
            salt = secrets.token_hex(32)
            password_hash = self._hash_password(password, salt)
            conn.execute(
                'INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)',
                (username, password_hash, salt)
            )
            conn.commit()
            logger.info(f"User registered: {username}")
            return True, "Registration successful"
        except sqlite3.IntegrityError:
            return False, "Username already exists"
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False, "Registration failed"
    
    def authenticate_user(self, username: str, password: str) -> tuple:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                'SELECT id, password_hash, salt FROM users WHERE username = ?',
                (username,)
            )
            row = cursor.fetchone()
            if not row:
                return False, "User not found", None
            expected_hash = self._hash_password(password, row['salt'])
            if expected_hash == row['password_hash']:
                return True, "Login successful", row['id']
            return False, "Invalid password", None
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return False, "Authentication failed", None
    
    def get_user_id(self, username: str) -> Optional[int]:
        conn = self._get_conn()
        cursor = conn.execute('SELECT id FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        return row['id'] if row else None
    
    def add_contact(self, user_id: int, contact_username: str) -> tuple:
        conn = self._get_conn()
        try:
            contact_id = self.get_user_id(contact_username)
            if not contact_id:
                return False, "User not found"
            if contact_id == user_id:
                return False, "Cannot add yourself"
            conn.execute(
                'INSERT INTO contacts (user_id, contact_id) VALUES (?, ?)',
                (user_id, contact_id)
            )
            conn.commit()
            return True, "Contact added"
        except sqlite3.IntegrityError:
            return False, "Contact already exists"
        except Exception as e:
            logger.error(f"Add contact error: {e}")
            return False, "Failed to add contact"
    
    def remove_contact(self, user_id: int, contact_username: str) -> tuple:
        conn = self._get_conn()
        try:
            contact_id = self.get_user_id(contact_username)
            if not contact_id:
                return False, "User not found"
            cursor = conn.execute(
                'DELETE FROM contacts WHERE user_id = ? AND contact_id = ?',
                (user_id, contact_id)
            )
            conn.commit()
            return (True, "Contact removed") if cursor.rowcount > 0 else (False, "Contact not in list")
        except Exception as e:
            logger.error(f"Remove contact error: {e}")
            return False, "Failed to remove contact"
    
    def get_contacts(self, user_id: int) -> List[str]:
        conn = self._get_conn()
        cursor = conn.execute('''
            SELECT u.username FROM contacts c
            JOIN users u ON c.contact_id = u.id
            WHERE c.user_id = ?
            ORDER BY u.username
        ''', (user_id,))
        return [row['username'] for row in cursor.fetchall()]
    
    def search_users(self, query: str, exclude_user_id: int) -> List[str]:
        conn = self._get_conn()
        cursor = conn.execute('''
            SELECT username FROM users 
            WHERE username LIKE ? AND id != ?
            LIMIT 20
        ''', (f'%{query}%', exclude_user_id))
        return [row['username'] for row in cursor.fetchall()]
    
    def set_avatar(self, user_id: int, avatar_data: bytes) -> bool:
        conn = self._get_conn()
        try:
            conn.execute('UPDATE users SET avatar = ? WHERE id = ?', (avatar_data, user_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Set avatar error: {e}")
            return False
    
    def get_avatar(self, username: str) -> Optional[bytes]:
        conn = self._get_conn()
        cursor = conn.execute('SELECT avatar FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        if row and row['avatar']:
            return row['avatar']
        return None


class ClientSession:
    def __init__(self, sock: socket.socket, addr: tuple):
        self.sock = sock
        self.addr = addr
        self.username: Optional[str] = None
        self.user_id: Optional[int] = None
        self.authenticated = False
        self.lock = threading.Lock()
    
    def send(self, msg: Message) -> bool:
        with self.lock:
            return send_message(self.sock, msg)
    
    def close(self):
        try:
            self.sock.close()
        except:
            pass


class IMServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.db = Database(DATABASE)
        self.clients: Dict[str, ClientSession] = {}
        self.clients_lock = threading.Lock()
        self.server_socket: Optional[socket.socket] = None
    
    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(50)
        
        logger.info(f"QuickIM Server started on {self.host}:{self.port}")
        logger.info("Protocol: QPROTO v1 (with avatars)")
        
        try:
            while True:
                client_sock, addr = self.server_socket.accept()
                logger.info(f"New connection from {addr}")
                session = ClientSession(client_sock, addr)
                threading.Thread(target=self._handle_client, args=(session,), daemon=True).start()
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        finally:
            self.server_socket.close()
    
    def _handle_client(self, session: ClientSession):
        try:
            while True:
                msg = recv_message(session.sock)
                if not msg:
                    break
                
                if isinstance(msg, RegisterMessage):
                    self._handle_register(session, msg)
                elif isinstance(msg, LoginMessage):
                    self._handle_login(session, msg)
                elif isinstance(msg, LogoutMessage):
                    self._handle_logout(session)
                    break
                elif isinstance(msg, SendMsgMessage):
                    self._handle_send_msg(session, msg)
                elif isinstance(msg, AddContactMessage):
                    self._handle_add_contact(session, msg)
                elif isinstance(msg, RemoveContactMessage):
                    self._handle_remove_contact(session, msg)
                elif isinstance(msg, ContactListReqMessage):
                    self._handle_get_contacts(session)
                elif isinstance(msg, UserSearchMessage):
                    self._handle_search_user(session, msg)
                elif isinstance(msg, EarthquakeSendMessage):
                    self._handle_earthquake(session, msg)
                elif isinstance(msg, AvatarSetMessage):
                    self._handle_avatar_set(session, msg)
                elif isinstance(msg, AvatarGetMessage):
                    self._handle_avatar_get(session, msg)
                else:
                    session.send(build_error("Unknown command"))
        except Exception as e:
            logger.error(f"Error handling client {session.addr}: {e}")
        finally:
            self._cleanup_session(session)
    
    def _handle_register(self, session: ClientSession, msg: RegisterMessage):
        username = msg.username.strip()
        password = msg.password
        
        if len(username) < 3 or len(username) > 20:
            session.send(build_response(ActionCode.REGISTER, ResponseCode.FAIL, "Username must be 3-20 characters"))
            return
        if len(password) < 4:
            session.send(build_response(ActionCode.REGISTER, ResponseCode.FAIL, "Password must be at least 4 characters"))
            return
        if not username.isalnum():
            session.send(build_response(ActionCode.REGISTER, ResponseCode.FAIL, "Username must be alphanumeric"))
            return
        
        success, message = self.db.register_user(username, password)
        session.send(build_response(
            ActionCode.REGISTER,
            ResponseCode.SUCCESS if success else ResponseCode.FAIL,
            message
        ))
    
    def _handle_login(self, session: ClientSession, msg: LoginMessage):
        username = msg.username.strip()
        password = msg.password
        
        with self.clients_lock:
            if username in self.clients:
                session.send(build_response(ActionCode.LOGIN, ResponseCode.FAIL, "User already logged in"))
                return
        
        success, message, user_id = self.db.authenticate_user(username, password)
        
        if success:
            session.username = username
            session.user_id = user_id
            session.authenticated = True
            
            with self.clients_lock:
                self.clients[username] = session
            
            session.send(build_response(ActionCode.LOGIN, ResponseCode.SUCCESS, message))
            logger.info(f"User logged in: {username}")
            self._broadcast_presence(session, PresenceStatus.ONLINE)
        else:
            session.send(build_response(ActionCode.LOGIN, ResponseCode.FAIL, message))
    
    def _handle_logout(self, session: ClientSession):
        if session.authenticated:
            session.send(build_response(ActionCode.LOGOUT, ResponseCode.SUCCESS, "Goodbye!"))
            logger.info(f"User logged out: {session.username}")
    
    def _handle_send_msg(self, session: ClientSession, msg: SendMsgMessage):
        if not session.authenticated:
            session.send(build_error("Not authenticated"))
            return
        
        recipient = msg.to.strip()
        content = msg.content
        msg_id = msg.msg_id
        
        if not recipient or not content:
            session.send(build_msg_ack(msg_id, AckStatus.INVALID_MESSAGE))
            return
        
        with self.clients_lock:
            recipient_session = self.clients.get(recipient)
        
        if recipient_session:
            timestamp = datetime.now().isoformat()
            delivered = recipient_session.send(build_receive_msg(session.username, content, msg_id, timestamp))
            session.send(build_msg_ack(msg_id, AckStatus.DELIVERED if delivered else AckStatus.DELIVERY_FAILED))
            if delivered:
                logger.info(f"Message: {session.username} -> {recipient}")
        else:
            session.send(build_msg_ack(msg_id, AckStatus.USER_OFFLINE))
    
    def _handle_add_contact(self, session: ClientSession, msg: AddContactMessage):
        if not session.authenticated:
            session.send(build_error("Not authenticated"))
            return
        
        contact = msg.contact.strip()
        if not contact:
            session.send(build_response(ActionCode.ADD_CONTACT, ResponseCode.FAIL, "Invalid username"))
            return
        
        success, message = self.db.add_contact(session.user_id, contact)
        session.send(build_response(
            ActionCode.ADD_CONTACT,
            ResponseCode.SUCCESS if success else ResponseCode.FAIL,
            message
        ))
        
        if success:
            self._handle_get_contacts(session)
    
    def _handle_remove_contact(self, session: ClientSession, msg: RemoveContactMessage):
        if not session.authenticated:
            session.send(build_error("Not authenticated"))
            return
        
        success, message = self.db.remove_contact(session.user_id, msg.contact.strip())
        session.send(build_response(
            ActionCode.REMOVE_CONTACT,
            ResponseCode.SUCCESS if success else ResponseCode.FAIL,
            message
        ))
        
        if success:
            self._handle_get_contacts(session)
    
    def _handle_get_contacts(self, session: ClientSession):
        if not session.authenticated:
            session.send(build_error("Not authenticated"))
            return
        
        contact_usernames = self.db.get_contacts(session.user_id)
        contacts = []
        
        with self.clients_lock:
            for username in contact_usernames:
                status = PresenceStatus.ONLINE if username in self.clients else PresenceStatus.OFFLINE
                contacts.append(ContactInfo(username, status))
        
        session.send(build_contact_list(contacts))
    
    def _handle_search_user(self, session: ClientSession, msg: UserSearchMessage):
        if not session.authenticated:
            session.send(build_error("Not authenticated"))
            return
        
        query = msg.query.strip()
        if len(query) < 1:
            session.send(build_user_search_result([]))
            return
        
        users = self.db.search_users(query, session.user_id)
        session.send(build_user_search_result(users))
    
    def _handle_earthquake(self, session: ClientSession, msg: EarthquakeSendMessage):
        if not session.authenticated:
            session.send(build_error("Not authenticated"))
            return
        
        recipient = msg.to.strip()
        intensity = max(1, min(10, msg.intensity))
        
        with self.clients_lock:
            recipient_session = self.clients.get(recipient)
        
        if recipient_session:
            delivered = recipient_session.send(build_earthquake_recv(session.username, intensity))
            if delivered:
                logger.info(f"Earthquake: {session.username} -> {recipient} (intensity: {intensity})")
        else:
            session.send(build_error("User is offline"))
    
    def _handle_avatar_set(self, session: ClientSession, msg: AvatarSetMessage):
        if not session.authenticated:
            session.send(build_error("Not authenticated"))
            return
        
        if len(msg.avatar_data) > MAX_AVATAR_SIZE:
            session.send(build_response(ActionCode.AVATAR_SET, ResponseCode.FAIL, "Avatar too large (max 512KB)"))
            return
        
        if self.db.set_avatar(session.user_id, msg.avatar_data):
            session.send(build_response(ActionCode.AVATAR_SET, ResponseCode.SUCCESS, "Avatar updated"))
            logger.info(f"Avatar set: {session.username} ({len(msg.avatar_data)} bytes)")
        else:
            session.send(build_response(ActionCode.AVATAR_SET, ResponseCode.FAIL, "Failed to update avatar"))
    
    def _handle_avatar_get(self, session: ClientSession, msg: AvatarGetMessage):
        if not session.authenticated:
            session.send(build_error("Not authenticated"))
            return
        
        username = msg.username.strip()
        avatar_data = self.db.get_avatar(username)
        session.send(build_avatar_data(username, avatar_data if avatar_data else b''))
    
    def _broadcast_presence(self, session: ClientSession, status: PresenceStatus):
        if not session.authenticated:
            return
        
        presence_msg = build_presence(session.username, status)
        
        with self.clients_lock:
            for username, client_session in self.clients.items():
                if username != session.username:
                    client_session.send(presence_msg)
        
        logger.info(f"Presence: {session.username} is {'online' if status == PresenceStatus.ONLINE else 'offline'}")
    
    def _cleanup_session(self, session: ClientSession):
        if session.authenticated and session.username:
            with self.clients_lock:
                if session.username in self.clients:
                    del self.clients[session.username]
            self._broadcast_presence(session, PresenceStatus.OFFLINE)
            logger.info(f"Disconnected: {session.username}")
        session.close()


if __name__ == '__main__':
    server = IMServer(HOST, PORT)
    server.start()

# protocol.py
"""
QuickIM Binary Protocol
==========================================================
"""

import socket
import struct
from enum import IntEnum
from typing import Optional, List
from dataclasses import dataclass

# Protocol Constants
PROTOCOL_MAGIC = b'QP'
PROTOCOL_VERSION = 0x01
HEADER_SIZE = 9
MAX_MESSAGE_SIZE = 10 * 1024 * 1024
MAX_AVATAR_SIZE = 512 * 1024  # 512 KB max avatar


class Command(IntEnum):
    # Authentication (0x00XX)
    QPROTO_REGISTER         = 0x0001
    QPROTO_LOGIN            = 0x0002
    QPROTO_LOGOUT           = 0x0003
    
    # Messaging (0x01XX)
    QPROTO_MSG_SEND         = 0x0100
    QPROTO_MSG_RECEIVE      = 0x0101
    QPROTO_MSG_ACK          = 0x0102
    
    # Contacts (0x02XX)
    QPROTO_CONTACT_ADD      = 0x0200
    QPROTO_CONTACT_REMOVE   = 0x0201
    QPROTO_CONTACT_LIST_REQ = 0x0202
    QPROTO_CONTACT_LIST     = 0x0203
    
    # Users (0x03XX)
    QPROTO_USER_SEARCH      = 0x0300
    QPROTO_USER_SEARCH_RES  = 0x0301
    QPROTO_USER_LIST_REQ    = 0x0302
    QPROTO_USER_LIST        = 0x0303
    
    # Presence (0x04XX)
    QPROTO_PRESENCE         = 0x0400
    
    # Responses (0x05XX)
    QPROTO_RESPONSE         = 0x0500
    QPROTO_ERROR            = 0x0501
    
    # Fun/Effects (0x06XX)
    QPROTO_EARTHQUAKE_SEND  = 0x0600
    QPROTO_EARTHQUAKE_RECV  = 0x0601
    
    # Avatar (0x07XX)
    QPROTO_AVATAR_SET       = 0x0700
    QPROTO_AVATAR_GET       = 0x0701
    QPROTO_AVATAR_DATA      = 0x0702


class ResponseCode(IntEnum):
    SUCCESS = 0x00
    FAIL = 0x01


class PresenceStatus(IntEnum):
    OFFLINE = 0x00
    ONLINE = 0x01


class AckStatus(IntEnum):
    DELIVERED = 0x00
    USER_OFFLINE = 0x01
    DELIVERY_FAILED = 0x02
    INVALID_MESSAGE = 0x03


class ActionCode(IntEnum):
    REGISTER = 0x01
    LOGIN = 0x02
    LOGOUT = 0x03
    ADD_CONTACT = 0x04
    REMOVE_CONTACT = 0x05
    AVATAR_SET = 0x06


class BinaryWriter:
    def __init__(self):
        self.buffer = bytearray()
    
    def write_uint8(self, value: int):
        self.buffer.extend(struct.pack('>B', value))
        return self
    
    def write_uint16(self, value: int):
        self.buffer.extend(struct.pack('>H', value))
        return self
    
    def write_uint32(self, value: int):
        self.buffer.extend(struct.pack('>I', value))
        return self
    
    def write_string(self, value: str):
        encoded = value.encode('utf-8')
        self.write_uint16(len(encoded))
        self.buffer.extend(encoded)
        return self
    
    def write_bytes(self, value: bytes):
        self.write_uint32(len(value))
        self.buffer.extend(value)
        return self
    
    def get_bytes(self) -> bytes:
        return bytes(self.buffer)


class BinaryReader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0
    
    def read_uint8(self) -> int:
        value = struct.unpack_from('>B', self.data, self.offset)[0]
        self.offset += 1
        return value
    
    def read_uint16(self) -> int:
        value = struct.unpack_from('>H', self.data, self.offset)[0]
        self.offset += 2
        return value
    
    def read_uint32(self) -> int:
        value = struct.unpack_from('>I', self.data, self.offset)[0]
        self.offset += 4
        return value
    
    def read_string(self) -> str:
        length = self.read_uint16()
        value = self.data[self.offset:self.offset + length].decode('utf-8')
        self.offset += length
        return value
    
    def read_bytes(self) -> bytes:
        length = self.read_uint32()
        value = self.data[self.offset:self.offset + length]
        self.offset += length
        return value


# ============== Message Classes ==============

@dataclass
class Message:
    command: Command


@dataclass
class RegisterMessage(Message):
    username: str
    password: str
    
    def __init__(self, username: str, password: str):
        super().__init__(Command.QPROTO_REGISTER)
        self.username = username
        self.password = password


@dataclass
class LoginMessage(Message):
    username: str
    password: str
    
    def __init__(self, username: str, password: str):
        super().__init__(Command.QPROTO_LOGIN)
        self.username = username
        self.password = password


@dataclass
class LogoutMessage(Message):
    def __init__(self):
        super().__init__(Command.QPROTO_LOGOUT)


@dataclass
class SendMsgMessage(Message):
    to: str
    content: str
    msg_id: str
    
    def __init__(self, to: str, content: str, msg_id: str):
        super().__init__(Command.QPROTO_MSG_SEND)
        self.to = to
        self.content = content
        self.msg_id = msg_id


@dataclass
class ReceiveMsgMessage(Message):
    from_user: str
    content: str
    msg_id: str
    timestamp: str
    
    def __init__(self, from_user: str, content: str, msg_id: str, timestamp: str):
        super().__init__(Command.QPROTO_MSG_RECEIVE)
        self.from_user = from_user
        self.content = content
        self.msg_id = msg_id
        self.timestamp = timestamp


@dataclass
class MsgAckMessage(Message):
    msg_id: str
    status: AckStatus
    
    def __init__(self, msg_id: str, status: AckStatus):
        super().__init__(Command.QPROTO_MSG_ACK)
        self.msg_id = msg_id
        self.status = status


@dataclass
class AddContactMessage(Message):
    contact: str
    
    def __init__(self, contact: str):
        super().__init__(Command.QPROTO_CONTACT_ADD)
        self.contact = contact


@dataclass
class RemoveContactMessage(Message):
    contact: str
    
    def __init__(self, contact: str):
        super().__init__(Command.QPROTO_CONTACT_REMOVE)
        self.contact = contact


@dataclass
class ContactListReqMessage(Message):
    def __init__(self):
        super().__init__(Command.QPROTO_CONTACT_LIST_REQ)


@dataclass
class ContactInfo:
    username: str
    status: PresenceStatus


@dataclass
class ContactListMessage(Message):
    contacts: List[ContactInfo]
    
    def __init__(self, contacts: List[ContactInfo]):
        super().__init__(Command.QPROTO_CONTACT_LIST)
        self.contacts = contacts


@dataclass
class UserSearchMessage(Message):
    query: str
    
    def __init__(self, query: str):
        super().__init__(Command.QPROTO_USER_SEARCH)
        self.query = query


@dataclass
class UserSearchResultMessage(Message):
    users: List[str]
    
    def __init__(self, users: List[str]):
        super().__init__(Command.QPROTO_USER_SEARCH_RES)
        self.users = users


@dataclass
class PresenceMessage(Message):
    username: str
    status: PresenceStatus
    
    def __init__(self, username: str, status: PresenceStatus):
        super().__init__(Command.QPROTO_PRESENCE)
        self.username = username
        self.status = status


@dataclass
class ResponseMessage(Message):
    action: ActionCode
    code: ResponseCode
    message: str
    
    def __init__(self, action: ActionCode, code: ResponseCode, message: str):
        super().__init__(Command.QPROTO_RESPONSE)
        self.action = action
        self.code = code
        self.message = message


@dataclass
class ErrorMessage(Message):
    message: str
    
    def __init__(self, message: str):
        super().__init__(Command.QPROTO_ERROR)
        self.message = message


@dataclass
class EarthquakeSendMessage(Message):
    to: str
    intensity: int
    
    def __init__(self, to: str, intensity: int = 5):
        super().__init__(Command.QPROTO_EARTHQUAKE_SEND)
        self.to = to
        self.intensity = intensity


@dataclass
class EarthquakeRecvMessage(Message):
    from_user: str
    intensity: int
    
    def __init__(self, from_user: str, intensity: int):
        super().__init__(Command.QPROTO_EARTHQUAKE_RECV)
        self.from_user = from_user
        self.intensity = intensity


@dataclass
class AvatarSetMessage(Message):
    avatar_data: bytes
    
    def __init__(self, avatar_data: bytes):
        super().__init__(Command.QPROTO_AVATAR_SET)
        self.avatar_data = avatar_data


@dataclass
class AvatarGetMessage(Message):
    username: str
    
    def __init__(self, username: str):
        super().__init__(Command.QPROTO_AVATAR_GET)
        self.username = username


@dataclass
class AvatarDataMessage(Message):
    username: str
    avatar_data: bytes  # Empty if no avatar
    
    def __init__(self, username: str, avatar_data: bytes):
        super().__init__(Command.QPROTO_AVATAR_DATA)
        self.username = username
        self.avatar_data = avatar_data


# ============== Serialization ==============

def encode_message(msg: Message) -> bytes:
    writer = BinaryWriter()
    
    if isinstance(msg, RegisterMessage):
        writer.write_string(msg.username)
        writer.write_string(msg.password)
    
    elif isinstance(msg, LoginMessage):
        writer.write_string(msg.username)
        writer.write_string(msg.password)
    
    elif isinstance(msg, LogoutMessage):
        pass
    
    elif isinstance(msg, SendMsgMessage):
        writer.write_string(msg.to)
        writer.write_string(msg.content)
        writer.write_string(msg.msg_id)
    
    elif isinstance(msg, ReceiveMsgMessage):
        writer.write_string(msg.from_user)
        writer.write_string(msg.content)
        writer.write_string(msg.msg_id)
        writer.write_string(msg.timestamp)
    
    elif isinstance(msg, MsgAckMessage):
        writer.write_string(msg.msg_id)
        writer.write_uint8(msg.status)
    
    elif isinstance(msg, AddContactMessage):
        writer.write_string(msg.contact)
    
    elif isinstance(msg, RemoveContactMessage):
        writer.write_string(msg.contact)
    
    elif isinstance(msg, ContactListReqMessage):
        pass
    
    elif isinstance(msg, ContactListMessage):
        writer.write_uint16(len(msg.contacts))
        for contact in msg.contacts:
            writer.write_string(contact.username)
            writer.write_uint8(contact.status)
    
    elif isinstance(msg, UserSearchMessage):
        writer.write_string(msg.query)
    
    elif isinstance(msg, UserSearchResultMessage):
        writer.write_uint16(len(msg.users))
        for user in msg.users:
            writer.write_string(user)
    
    elif isinstance(msg, PresenceMessage):
        writer.write_string(msg.username)
        writer.write_uint8(msg.status)
    
    elif isinstance(msg, ResponseMessage):
        writer.write_uint8(msg.action)
        writer.write_uint8(msg.code)
        writer.write_string(msg.message)
    
    elif isinstance(msg, ErrorMessage):
        writer.write_string(msg.message)
    
    elif isinstance(msg, EarthquakeSendMessage):
        writer.write_string(msg.to)
        writer.write_uint8(msg.intensity)
    
    elif isinstance(msg, EarthquakeRecvMessage):
        writer.write_string(msg.from_user)
        writer.write_uint8(msg.intensity)
    
    elif isinstance(msg, AvatarSetMessage):
        writer.write_bytes(msg.avatar_data)
    
    elif isinstance(msg, AvatarGetMessage):
        writer.write_string(msg.username)
    
    elif isinstance(msg, AvatarDataMessage):
        writer.write_string(msg.username)
        writer.write_bytes(msg.avatar_data)
    
    else:
        raise ValueError(f"Unknown message type: {type(msg)}")
    
    payload = writer.get_bytes()
    
    frame = bytearray()
    frame.extend(PROTOCOL_MAGIC)
    frame.append(PROTOCOL_VERSION)
    frame.extend(struct.pack('>H', msg.command))
    frame.extend(struct.pack('>I', len(payload)))
    frame.extend(payload)
    
    return bytes(frame)


def decode_message(data: bytes) -> Optional[Message]:
    if len(data) < HEADER_SIZE:
        return None
    
    magic = data[0:2]
    version = data[2]
    command = struct.unpack('>H', data[3:5])[0]
    payload_len = struct.unpack('>I', data[5:9])[0]
    
    if magic != PROTOCOL_MAGIC:
        raise ValueError(f"Invalid magic bytes: {magic}")
    
    if version != PROTOCOL_VERSION:
        raise ValueError(f"Unsupported protocol version: {version}")
    
    payload = data[HEADER_SIZE:HEADER_SIZE + payload_len]
    reader = BinaryReader(payload)
    
    try:
        cmd = Command(command)
    except ValueError:
        raise ValueError(f"Unknown command: {command:#06x}")
    
    if cmd == Command.QPROTO_REGISTER:
        return RegisterMessage(reader.read_string(), reader.read_string())
    
    elif cmd == Command.QPROTO_LOGIN:
        return LoginMessage(reader.read_string(), reader.read_string())
    
    elif cmd == Command.QPROTO_LOGOUT:
        return LogoutMessage()
    
    elif cmd == Command.QPROTO_MSG_SEND:
        return SendMsgMessage(reader.read_string(), reader.read_string(), reader.read_string())
    
    elif cmd == Command.QPROTO_MSG_RECEIVE:
        return ReceiveMsgMessage(reader.read_string(), reader.read_string(), reader.read_string(), reader.read_string())
    
    elif cmd == Command.QPROTO_MSG_ACK:
        return MsgAckMessage(reader.read_string(), AckStatus(reader.read_uint8()))
    
    elif cmd == Command.QPROTO_CONTACT_ADD:
        return AddContactMessage(reader.read_string())
    
    elif cmd == Command.QPROTO_CONTACT_REMOVE:
        return RemoveContactMessage(reader.read_string())
    
    elif cmd == Command.QPROTO_CONTACT_LIST_REQ:
        return ContactListReqMessage()
    
    elif cmd == Command.QPROTO_CONTACT_LIST:
        count = reader.read_uint16()
        contacts = []
        for _ in range(count):
            contacts.append(ContactInfo(reader.read_string(), PresenceStatus(reader.read_uint8())))
        return ContactListMessage(contacts)
    
    elif cmd == Command.QPROTO_USER_SEARCH:
        return UserSearchMessage(reader.read_string())
    
    elif cmd == Command.QPROTO_USER_SEARCH_RES:
        count = reader.read_uint16()
        return UserSearchResultMessage([reader.read_string() for _ in range(count)])
    
    elif cmd == Command.QPROTO_PRESENCE:
        return PresenceMessage(reader.read_string(), PresenceStatus(reader.read_uint8()))
    
    elif cmd == Command.QPROTO_RESPONSE:
        return ResponseMessage(ActionCode(reader.read_uint8()), ResponseCode(reader.read_uint8()), reader.read_string())
    
    elif cmd == Command.QPROTO_ERROR:
        return ErrorMessage(reader.read_string())
    
    elif cmd == Command.QPROTO_EARTHQUAKE_SEND:
        return EarthquakeSendMessage(reader.read_string(), reader.read_uint8())
    
    elif cmd == Command.QPROTO_EARTHQUAKE_RECV:
        return EarthquakeRecvMessage(reader.read_string(), reader.read_uint8())
    
    elif cmd == Command.QPROTO_AVATAR_SET:
        return AvatarSetMessage(reader.read_bytes())
    
    elif cmd == Command.QPROTO_AVATAR_GET:
        return AvatarGetMessage(reader.read_string())
    
    elif cmd == Command.QPROTO_AVATAR_DATA:
        return AvatarDataMessage(reader.read_string(), reader.read_bytes())
    
    else:
        raise ValueError(f"Unhandled command: {cmd}")


def send_message(sock: socket.socket, msg: Message) -> bool:
    try:
        data = encode_message(msg)
        sock.sendall(data)
        return True
    except (socket.error, OSError, BrokenPipeError):
        return False


def recv_message(sock: socket.socket) -> Optional[Message]:
    try:
        header = _recv_exactly(sock, HEADER_SIZE)
        if not header:
            return None
        
        if header[0:2] != PROTOCOL_MAGIC:
            return None
        
        payload_len = struct.unpack('>I', header[5:9])[0]
        
        if payload_len > MAX_MESSAGE_SIZE:
            return None
        
        payload = _recv_exactly(sock, payload_len) if payload_len > 0 else b''
        if payload_len > 0 and not payload:
            return None
        
        return decode_message(header + payload)
    
    except (socket.error, OSError, struct.error, ValueError):
        return None


def _recv_exactly(sock: socket.socket, n: int) -> Optional[bytes]:
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


# Builders
def build_register(username: str, password: str) -> RegisterMessage:
    return RegisterMessage(username, password)

def build_login(username: str, password: str) -> LoginMessage:
    return LoginMessage(username, password)

def build_logout() -> LogoutMessage:
    return LogoutMessage()

def build_send_msg(to: str, content: str, msg_id: str) -> SendMsgMessage:
    return SendMsgMessage(to, content, msg_id)

def build_receive_msg(from_user: str, content: str, msg_id: str, timestamp: str) -> ReceiveMsgMessage:
    return ReceiveMsgMessage(from_user, content, msg_id, timestamp)

def build_msg_ack(msg_id: str, status: AckStatus) -> MsgAckMessage:
    return MsgAckMessage(msg_id, status)

def build_add_contact(contact: str) -> AddContactMessage:
    return AddContactMessage(contact)

def build_remove_contact(contact: str) -> RemoveContactMessage:
    return RemoveContactMessage(contact)

def build_contact_list_req() -> ContactListReqMessage:
    return ContactListReqMessage()

def build_contact_list(contacts: List[ContactInfo]) -> ContactListMessage:
    return ContactListMessage(contacts)

def build_user_search(query: str) -> UserSearchMessage:
    return UserSearchMessage(query)

def build_user_search_result(users: List[str]) -> UserSearchResultMessage:
    return UserSearchResultMessage(users)

def build_presence(username: str, status: PresenceStatus) -> PresenceMessage:
    return PresenceMessage(username, status)

def build_response(action: ActionCode, code: ResponseCode, message: str) -> ResponseMessage:
    return ResponseMessage(action, code, message)

def build_error(message: str) -> ErrorMessage:
    return ErrorMessage(message)

def build_earthquake_send(to: str, intensity: int = 5) -> EarthquakeSendMessage:
    return EarthquakeSendMessage(to, intensity)

def build_earthquake_recv(from_user: str, intensity: int) -> EarthquakeRecvMessage:
    return EarthquakeRecvMessage(from_user, intensity)

def build_avatar_set(avatar_data: bytes) -> AvatarSetMessage:
    return AvatarSetMessage(avatar_data)

def build_avatar_get(username: str) -> AvatarGetMessage:
    return AvatarGetMessage(username)

def build_avatar_data(username: str, avatar_data: bytes) -> AvatarDataMessage:
    return AvatarDataMessage(username, avatar_data)

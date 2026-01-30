> [!IMPORTANT]
> This messenger doesn't have a public instance yet. If someone is willing to host one, email artemchikdornikov@gmail.com


# QuickIM
QuickIM is an self-hostable instant messaging system written in Python with its own binary protocol.

## Features
### Implemented
+ Custom binary messaging protocol
+ TCP-based client/server communication
+ User registration and login
+ Password hashing
+ SQLite database backend
+ Persistent users and contact lists
+ Contact management via username
+ Presence system 
+ Message delivery between users
+ Desktop GUI client using PyQt5

### At some point...
- Encryption via TLS
- Save messages offline
- Save messages **online** (message history)
- Send and receive images and other files
- A mobile client
- Voice calls and video calls

## How to use
First, clone the repository:

```
git clone https://github.com/Artemchik-Studio/QuickIM
cd QuickIM
```
### Server
To start the server, just run `python server.py`
### Client
The official QuickIM client requires PyQt5 to run (compiled client is in releases for Windows)
#### Windows
`pip install PyQt5` or `python -m pip install PyQt5`
#### Linux (Debian-based)
`sudo apt install python3-pyqt5`
#### Linux (Fedora-based)
`sudo dnf install PyQt5`
#### Linux (Arch-based)
`sudo pacman -S python-pyqt5`

Once installed, you can simply just run `python client.py`.

"""LAN Chat Server for VideoLingo"""
import socket
import threading
import json
import time
from typing import Dict, List, Set
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatMessage:
    """Represents a chat message"""
    sender: str
    original_text: str
    original_language: str
    timestamp: float
    message_id: str


class ChatServer:
    """LAN Chat Server that handles multiple clients"""
    
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.clients: Dict[str, socket.socket] = {}
        self.messages: List[ChatMessage] = []
        self.running = False
        self.server_socket = None
        self.lock = threading.Lock()
        
    def start(self):
        """Start the chat server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            print(f"Chat server started on {self.host}:{self.port}")
            
            # Start accepting connections
            accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            accept_thread.start()
            
            return True
        except Exception as e:
            print(f"Failed to start chat server: {e}")
            return False
    
    def stop(self):
        """Stop the chat server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        
        with self.lock:
            for client_socket in self.clients.values():
                try:
                    client_socket.close()
                except:
                    pass
            self.clients.clear()
    
    def _accept_connections(self):
        """Accept incoming client connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"New connection from {address}")
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")
    
    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle individual client connection"""
        client_id = f"{address[0]}:{address[1]}"
        
        with self.lock:
            self.clients[client_id] = client_socket
        
        try:
            while self.running:
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                try:
                    message_data = json.loads(data)
                    self._process_message(client_id, message_data)
                except json.JSONDecodeError:
                    print(f"Invalid JSON from {client_id}")
                    
        except Exception as e:
            print(f"Error handling client {client_id}: {e}")
        finally:
            with self.lock:
                if client_id in self.clients:
                    del self.clients[client_id]
            try:
                client_socket.close()
            except:
                pass
            print(f"Client {client_id} disconnected")
    
    def _process_message(self, client_id: str, message_data: dict):
        """Process incoming message from client"""
        message_type = message_data.get('type')
        
        if message_type == 'chat_message':
            message = ChatMessage(
                sender=message_data.get('sender', 'Unknown'),
                original_text=message_data['text'],
                original_language=message_data.get('language', 'en'),
                timestamp=time.time(),
                message_id=str(len(self.messages))
            )
            
            with self.lock:
                self.messages.append(message)
            
            # Broadcast to all clients
            self._broadcast_message(message_data)
            
            print(f"Message from {message.sender}: {message.original_text}")
        
        elif message_type == 'get_history':
            # Send message history to requesting client
            history_data = {
                'type': 'message_history',
                'messages': [
                    {
                        'sender': msg.sender,
                        'text': msg.original_text,
                        'language': msg.original_language,
                        'timestamp': msg.timestamp,
                        'message_id': msg.message_id
                    }
                    for msg in self.messages[-50:]  # Last 50 messages
                ]
            }
            self._send_to_client(client_id, history_data)
    
    def _broadcast_message(self, message_data: dict):
        """Broadcast message to all connected clients"""
        with self.lock:
            disconnected_clients = []
            
            for client_id, client_socket in self.clients.items():
                try:
                    client_socket.sendall(
                        json.dumps(message_data).encode('utf-8') + b'\n'
                    )
                except:
                    disconnected_clients.append(client_id)
            
            # Remove disconnected clients
            for client_id in disconnected_clients:
                del self.clients[client_id]
    
    def _send_to_client(self, client_id: str, data: dict):
        """Send data to specific client"""
        with self.lock:
            if client_id in self.clients:
                try:
                    self.clients[client_id].sendall(
                        json.dumps(data).encode('utf-8') + b'\n'
                    )
                except:
                    # Remove disconnected client
                    del self.clients[client_id]


if __name__ == "__main__":
    server = ChatServer()
    server.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()
"""VideoLingo GUI launcher for realtime, realtime_player, main scripts, and chat."""
from __future__ import annotations

import os
import sys
import threading
import subprocess
import socket
import json
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime


SCRIPT_DIR = Path(__file__).resolve().parent


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("VideoLingo Launcher")
        self.geometry("860x740")
        self.processes: list[subprocess.Popen] = []
        self.chat_client = None
        self.chat_server = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Configure chat text colors
        self.chat_widget.tag_configure("own_message", foreground="blue", font=("TkDefaultFont", 9, "bold"))
        self.chat_widget.tag_configure("other_message", foreground="black")

    # ---------
    # UI assembly
    # ---------
    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        chat_frame = ttk.Frame(notebook)
        self._build_chat_tab(chat_frame)
        notebook.add(chat_frame, text="LAN Chat")

        realtime_frame = ttk.Frame(notebook)
        self._build_realtime_tab(realtime_frame)
        notebook.add(realtime_frame, text="Realtime")

        player_frame = ttk.Frame(notebook)
        self._build_player_tab(player_frame)
        notebook.add(player_frame, text="Realtime Player")

        main_frame = ttk.Frame(notebook)
        self._build_main_tab(main_frame)
        notebook.add(main_frame, text="Main Pipeline")
        notebook.select(chat_frame)

        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(controls, text="Stop All", command=self._stop_all_processes).pack(side=tk.RIGHT)
        ttk.Button(controls, text="Clear Log", command=self._clear_log).pack(side=tk.RIGHT, padx=(0, 8))

        log_frame = ttk.LabelFrame(self, text="Command Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.log_widget = ScrolledText(log_frame, height=6, state=tk.DISABLED)
        self.log_widget.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # ---------
    # Realtime tab
    # ---------
    def _build_realtime_tab(self, parent: ttk.Frame) -> None:
        defaults = {
            "mode": "file",
            "source": "",
            "camera_spec": "0",
            "audio_device": "default",
            "output": "output",
            "config": "config.yaml",
            "segment_seconds": "300",
            "silence_window": "10.0",
            "silence_db": "-35",
            "silence_min_dur": "0.3",
            "play": False,
            "max_segments": "0",
            "max_concurrency": "2",
        }
        self.realtime_vars = {
            key: (tk.BooleanVar(value=value) if isinstance(value, bool) else tk.StringVar(value=value))
            for key, value in defaults.items()
        }

        row = 0
        ttk.Label(parent, text="Mode").grid(row=row, column=0, sticky=tk.W, pady=4)
        mode_box = ttk.Combobox(
            parent,
            textvariable=self.realtime_vars["mode"],
            values=["file", "camera", "list-cameras", "test-camera"],
            state="readonly",
            width=18,
        )
        mode_box.grid(row=row, column=1, sticky=tk.W)

        row += 1
        ttk.Label(parent, text="Source file").grid(row=row, column=0, sticky=tk.W, pady=4)
        source_entry = ttk.Entry(parent, textvariable=self.realtime_vars["source"], width=50)
        source_entry.grid(row=row, column=1, sticky=tk.W)
        ttk.Button(parent, text="Browse", command=lambda: self._pick_file(self.realtime_vars["source"])).grid(
            row=row, column=2, padx=6
        )

        row += 1
        ttk.Label(parent, text="Camera spec").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=self.realtime_vars["camera_spec"], width=20).grid(row=row, column=1, sticky=tk.W)

        row += 1
        ttk.Label(parent, text="Audio device").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=self.realtime_vars["audio_device"], width=20).grid(row=row, column=1, sticky=tk.W)

        row += 1
        ttk.Label(parent, text="Output dir").grid(row=row, column=0, sticky=tk.W, pady=4)
        output_entry = ttk.Entry(parent, textvariable=self.realtime_vars["output"], width=40)
        output_entry.grid(row=row, column=1, sticky=tk.W)
        ttk.Button(parent, text="Browse", command=lambda: self._pick_directory(self.realtime_vars["output"])).grid(
            row=row, column=2, padx=6
        )

        row += 1
        ttk.Label(parent, text="Config path").grid(row=row, column=0, sticky=tk.W, pady=4)
        config_entry = ttk.Entry(parent, textvariable=self.realtime_vars["config"], width=40)
        config_entry.grid(row=row, column=1, sticky=tk.W)
        ttk.Button(parent, text="Browse", command=lambda: self._pick_file(self.realtime_vars["config"])).grid(
            row=row, column=2, padx=6
        )

        numeric_fields = [
            ("Segment seconds", "segment_seconds"),
            ("Silence window (s)", "silence_window"),
            ("Silence dB", "silence_db"),
            ("Silence min dur", "silence_min_dur"),
            ("Max segments", "max_segments"),
            ("Max concurrency", "max_concurrency"),
        ]

        for label_text, key in numeric_fields:
            row += 1
            ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Entry(parent, textvariable=self.realtime_vars[key], width=20).grid(row=row, column=1, sticky=tk.W)

        row += 1
        ttk.Checkbutton(parent, text="Play segments after processing", variable=self.realtime_vars["play"]).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=6
        )

        row += 1
        ttk.Button(parent, text="Start realtime", command=self._launch_realtime).grid(row=row, column=0, pady=10)

        parent.grid_columnconfigure(1, weight=1)

    # ---------
    # Player tab
    # ---------
    def _build_player_tab(self, parent: ttk.Frame) -> None:
        defaults = {
            "shared_base": "output",
            "session_dir": "",
            "start_index": "0",
            "poll_interval": "1.0",
            "player": "auto",
        }
        self.player_vars = {key: tk.StringVar(value=value) for key, value in defaults.items()}

        row = 0
        ttk.Label(parent, text="Shared base").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=self.player_vars["shared_base"], width=40).grid(row=row, column=1, sticky=tk.W)
        ttk.Button(parent, text="Browse", command=lambda: self._pick_directory(self.player_vars["shared_base"])).grid(
            row=row, column=2, padx=6
        )

        row += 1
        ttk.Label(parent, text="Session dir").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=self.player_vars["session_dir"], width=40).grid(row=row, column=1, sticky=tk.W)
        ttk.Button(parent, text="Browse", command=lambda: self._pick_directory(self.player_vars["session_dir"])).grid(
            row=row, column=2, padx=6
        )

        row += 1
        ttk.Label(parent, text="Start index").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=self.player_vars["start_index"], width=10).grid(row=row, column=1, sticky=tk.W)

        row += 1
        ttk.Label(parent, text="Poll interval (s)").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=self.player_vars["poll_interval"], width=10).grid(row=row, column=1, sticky=tk.W)

        row += 1
        ttk.Label(parent, text="Player").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(
            parent,
            textvariable=self.player_vars["player"],
            values=["auto", "internal", "ffplay", "mpv", "vlc", "default"],
            state="readonly",
            width=18,
        ).grid(row=row, column=1, sticky=tk.W)

        row += 1
        ttk.Button(parent, text="Start player", command=self._launch_player).grid(row=row, column=0, pady=10)

        parent.grid_columnconfigure(1, weight=1)

    # ---------
    # Main tab
    # ---------
    def _build_main_tab(self, parent: ttk.Frame) -> None:
        defaults = {
            "config": "config.yaml",
            "output": "output",
            "command": "subtitle",
            "quality": "1.0",
            "enable_lipsync": False,
        }
        self.main_vars = {
            key: (tk.BooleanVar(value=value) if isinstance(value, bool) else tk.StringVar(value=value))
            for key, value in defaults.items()
        }

        row = 0
        ttk.Label(parent, text="Config path").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=self.main_vars["config"], width=40).grid(row=row, column=1, sticky=tk.W)
        ttk.Button(parent, text="Browse", command=lambda: self._pick_file(self.main_vars["config"])).grid(
            row=row, column=2, padx=6
        )

        row += 1
        ttk.Label(parent, text="Output dir").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=self.main_vars["output"], width=40).grid(row=row, column=1, sticky=tk.W)
        ttk.Button(parent, text="Browse", command=lambda: self._pick_directory(self.main_vars["output"])).grid(
            row=row, column=2, padx=6
        )

        row += 1
        ttk.Label(parent, text="Command").grid(row=row, column=0, sticky=tk.W, pady=4)
        command_box = ttk.Combobox(
            parent,
            textvariable=self.main_vars["command"],
            values=["subtitle", "audio", "all", "lipsync"],
            state="readonly",
            width=18,
        )
        command_box.grid(row=row, column=1, sticky=tk.W)

        row += 1
        ttk.Label(parent, text="Lip-sync quality").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=self.main_vars["quality"], width=10).grid(row=row, column=1, sticky=tk.W)

        row += 1
        ttk.Checkbutton(parent, text="Enable lip-sync (lipsync command)", variable=self.main_vars["enable_lipsync"]).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=6
        )

        row += 1
        ttk.Button(parent, text="Start main", command=self._launch_main).grid(row=row, column=0, pady=10)

        parent.grid_columnconfigure(1, weight=1)

    # ---------
    # Chat tab
    # ---------
    def _build_chat_tab(self, parent: ttk.Frame) -> None:
        # Server settings
        server_frame = ttk.LabelFrame(parent, text="Chat Server")
        server_frame.pack(fill=tk.X, padx=10, pady=5)

        row = 0
        ttk.Label(server_frame, text="Server Host:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.server_host_var = tk.StringVar(value="0.0.0.0")
        ttk.Entry(server_frame, textvariable=self.server_host_var, width=15).grid(row=row, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(server_frame, text="Port:").grid(row=row, column=2, sticky=tk.W, pady=4, padx=(20,0))
        self.server_port_var = tk.StringVar(value="8888")
        ttk.Entry(server_frame, textvariable=self.server_port_var, width=10).grid(row=row, column=3, sticky=tk.W, padx=5)
        
        self.server_status_var = tk.StringVar(value="Server: Stopped")
        ttk.Label(server_frame, textvariable=self.server_status_var).grid(row=row, column=4, sticky=tk.W, padx=20)
        
        row += 1
        ttk.Button(server_frame, text="Start Server", command=self._start_chat_server).grid(row=row, column=0, pady=5)
        ttk.Button(server_frame, text="Stop Server", command=self._stop_chat_server).grid(row=row, column=1, pady=5, padx=5)

        # Client settings
        client_frame = ttk.LabelFrame(parent, text="Chat Client")
        client_frame.pack(fill=tk.X, padx=10, pady=5)

        row = 0
        ttk.Label(client_frame, text="Server Host:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.client_host_var = tk.StringVar(value="localhost")
        ttk.Entry(client_frame, textvariable=self.client_host_var, width=15).grid(row=row, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(client_frame, text="Port:").grid(row=row, column=2, sticky=tk.W, pady=4, padx=(10,0))
        self.client_port_var = tk.StringVar(value="8888")
        ttk.Entry(client_frame, textvariable=self.client_port_var, width=8).grid(row=row, column=3, sticky=tk.W, padx=5)
        
        row += 1
        ttk.Label(client_frame, text="Username:").grid(row=row, column=0, sticky=tk.W, pady=4)
        self.username_var = tk.StringVar(value=f"User_{os.getpid()}")
        ttk.Entry(client_frame, textvariable=self.username_var, width=15).grid(row=row, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(client_frame, text="Language:").grid(row=row, column=2, sticky=tk.W, pady=4, padx=(10,0))
        self.user_language_var = tk.StringVar(value="en")
        language_combo = ttk.Combobox(
            client_frame,
            textvariable=self.user_language_var,
            values=["en", "zh", "ja", "es", "fr", "de", "ru", "it"],
            state="readonly",
            width=10,
        )
        language_combo.grid(row=row, column=3, sticky=tk.W, padx=5)
        
        self.client_status_var = tk.StringVar(value="Client: Disconnected")
        ttk.Label(client_frame, textvariable=self.client_status_var).grid(row=row, column=4, sticky=tk.W, padx=20)
        
        row += 1
        ttk.Button(client_frame, text="Connect", command=self._connect_chat_client).grid(row=row, column=0, pady=5)
        ttk.Button(client_frame, text="Disconnect", command=self._disconnect_chat_client).grid(row=row, column=1, pady=5, padx=5)

        # Chat display
        chat_display_frame = ttk.LabelFrame(parent, text="Chat Messages")
        chat_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.chat_widget = ScrolledText(chat_display_frame, height=15, state=tk.DISABLED)
        self.chat_widget.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Message input
        message_frame = ttk.Frame(parent)
        message_frame.pack(fill=tk.BOTH, padx=10, pady=5)

        ttk.Label(message_frame, text="Message:").grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=(0, 5), pady=(0, 2))
        self.message_input = tk.Text(message_frame, height=4, wrap=tk.WORD)
        self.message_input.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5)
        self.message_input.bind("<Return>", self._on_message_return)
        
        ttk.Button(message_frame, text="Send", command=self._send_chat_message).grid(row=2, column=0, columnspan=3, sticky=tk.E, padx=5, pady=(5, 0))
        message_frame.grid_columnconfigure(0, weight=1)
        message_frame.grid_columnconfigure(1, weight=1)
        message_frame.grid_columnconfigure(2, weight=1)
        message_frame.grid_rowconfigure(1, weight=1)
        self.after_idle(self.message_input.focus_set)

    # ---------
    # Chat handlers
    # ---------
    def _start_chat_server(self) -> None:
        """Start the chat server"""
        try:
            from chat_server import ChatServer
            
            host = self.server_host_var.get().strip()
            port = int(self.server_port_var.get().strip())
            
            self.chat_server = ChatServer(host=host, port=port)
            if self.chat_server.start():
                self.server_status_var.set(f"Server: Running on {host}:{port}")
                self._append_log(f"Chat server started on {host}:{port}\n")
            else:
                self.server_status_var.set("Server: Failed to start")
                messagebox.showerror("Chat Server", "Failed to start chat server")
                
        except Exception as e:
            messagebox.showerror("Chat Server", f"Error starting server: {e}")
            self.server_status_var.set("Server: Error")

    def _stop_chat_server(self) -> None:
        """Stop the chat server"""
        if self.chat_server:
            self.chat_server.stop()
            self.chat_server = None
            self.server_status_var.set("Server: Stopped")
            self._append_log("Chat server stopped\n")

    def _connect_chat_client(self) -> None:
        """Connect to chat server"""
        try:
            from chat_client import ChatClient
            
            host = self.client_host_var.get().strip()
            port = int(self.client_port_var.get().strip())
            
            self.chat_client = ChatClient(server_host=host, server_port=port)
            self.chat_client.set_user_name(self.username_var.get().strip())
            self.chat_client.set_preferred_language(self.user_language_var.get())
            self.chat_client.set_message_callback(self._on_chat_message_received)
            
            if self.chat_client.connect():
                self.client_status_var.set("Client: Connected")
                self._append_log(f"Chat client connected to {host}:{port} as {self.username_var.get()}\n")
                self._append_chat("System", f"Connected to chat as {self.username_var.get()}")
            else:
                self.client_status_var.set("Client: Connection failed")
                messagebox.showerror("Chat Client", f"Failed to connect to {host}:{port}")
                
        except Exception as e:
            messagebox.showerror("Chat Client", f"Error connecting to {self.client_host_var.get()}:{self.client_port_var.get()}: {e}")
            self.client_status_var.set("Client: Error")

    def _disconnect_chat_client(self) -> None:
        """Disconnect from chat server"""
        if self.chat_client:
            self.chat_client.disconnect()
            self.chat_client = None
            self.client_status_var.set("Client: Disconnected")
            self._append_log("Chat client disconnected\n")
            self._append_chat("System", "Disconnected from chat")

    def _send_chat_message(self) -> None:
        """Send a chat message"""
        if not self.chat_client or not self.chat_client.running:
            messagebox.showerror("Chat", "Not connected to chat server")
            return
        
        message = self.message_input.get("1.0", tk.END).strip()
        if not message:
            return
        
        language = self.user_language_var.get()
        if self.chat_client.send_message(message, language):
            self.message_input.delete("1.0", tk.END)
            self.message_input.focus_set()
            # Display own message immediately
            self._append_chat(self.username_var.get(), message, is_own=True)
        else:
            messagebox.showerror("Chat", "Failed to send message")

    def _on_message_return(self, event) -> str | None:
        """Handle Return key in the message box; Shift+Enter inserts newline."""
        if event.state & 0x0001:  # Shift modifier is active
            return None
        self._send_chat_message()
        return "break"

    def _on_chat_message_received(self, message) -> None:
        """Handle incoming chat message"""
        # This runs in a separate thread, so we need to use thread-safe GUI updates
        def update_gui():
            try:
                # Try to translate the message to user's preferred language
                original_text = message.original_text
                original_lang = message.original_language
                user_lang = self.user_language_var.get()
                
                display_text = original_text
                
                # Only translate if languages are different
                if original_lang != user_lang:
                    try:
                        # Use existing translation infrastructure
                        from core.translate_lines import translate_lines
                        translated_text, _ = translate_lines(
                            original_text,
                            previous_content_prompt=None,
                            after_cotent_prompt=None,
                            things_to_note_prompt=None,
                            summary_prompt=None
                        )
                        display_text = f"{original_text}\n[Translated to {user_lang}]: {translated_text}"
                    except Exception as e:
                        print(f"Translation failed: {e}")
                        display_text = f"{original_text}\n[Original in {original_lang}]"
                
                self._append_chat(message.sender, display_text)
                
            except Exception as e:
                print(f"Error processing chat message: {e}")
                self._append_chat(message.sender, message.original_text)
        
        # Schedule GUI update in main thread
        self.after(0, update_gui)

    def _append_chat(self, sender: str, message: str, is_own: bool = False) -> None:
        """Append a message to the chat display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message with colors for own vs others
        if is_own:
            display_text = f"[{timestamp}] {sender}: {message}\n"
            tag = "own_message"
        else:
            display_text = f"[{timestamp}] {sender}: {message}\n"
            tag = "other_message"
        
        self.chat_widget.configure(state=tk.NORMAL)
        self.chat_widget.insert(tk.END, display_text, tag)
        self.chat_widget.see(tk.END)
        self.chat_widget.configure(state=tk.DISABLED)

    # ---------
    # Launch handlers
    # ---------
    def _launch_realtime(self) -> None:
        mode = self.realtime_vars["mode"].get()
        cmd = [sys.executable, str(SCRIPT_DIR / "realtime.py"), mode]

        if mode == "file":
            source = self.realtime_vars["source"].get().strip()
            if not source:
                messagebox.showerror("Missing value", "请选择输入视频文件")
                return
            cmd += ["--source", source]
        elif mode in {"camera", "test-camera"}:
            cmd += ["--camera-spec", self.realtime_vars["camera_spec"].get().strip()]
            if mode == "test-camera":
                cmd += ["--audio-device", self.realtime_vars["audio_device"].get().strip()]
        elif mode == "list-cameras":
            # No extra options needed.
            pass

        if mode in {"file", "camera"}:
            cmd += ["--output", self.realtime_vars["output"].get().strip()]
            cmd += ["--config", self.realtime_vars["config"].get().strip()]

            segment_seconds = self._ensure_int(self.realtime_vars["segment_seconds"].get(), "segment seconds")
            silence_db = self._ensure_int(self.realtime_vars["silence_db"].get(), "silence db")
            max_segments = self._ensure_int(self.realtime_vars["max_segments"].get(), "max segments", allow_zero=True)
            max_concurrency = self._ensure_int(
                self.realtime_vars["max_concurrency"].get(), "max concurrency", allow_zero=False
            )
            silence_window = self._ensure_float(self.realtime_vars["silence_window"].get(), "silence window")
            silence_min_dur = self._ensure_float(self.realtime_vars["silence_min_dur"].get(), "silence min duration")

            if None in {segment_seconds, silence_db, max_segments, max_concurrency, silence_window, silence_min_dur}:
                return

            cmd += ["--segment-seconds", str(segment_seconds)]
            cmd += ["--silence-window", str(silence_window)]
            cmd += ["--silence-db", str(silence_db)]
            cmd += ["--silence-min-dur", str(silence_min_dur)]
            cmd += ["--max-segments", str(max_segments)]
            cmd += ["--max-concurrency", str(max_concurrency)]

            if mode == "camera":
                cmd += ["--audio-device", self.realtime_vars["audio_device"].get().strip()]

            if self.realtime_vars["play"].get():
                cmd.append("--play")

        self._run_command(cmd)

    def _launch_player(self) -> None:
        cmd = [sys.executable, str(SCRIPT_DIR / "realtime_player.py")]

        shared_base = self.player_vars["shared_base"].get().strip()
        session_dir = self.player_vars["session_dir"].get().strip()
        start_index = self._ensure_int(self.player_vars["start_index"].get(), "start index", allow_zero=True)
        poll_interval = self._ensure_float(self.player_vars["poll_interval"].get(), "poll interval")

        if None in {start_index, poll_interval}:
            return

        cmd += ["--shared-base", shared_base]
        if session_dir:
            cmd += ["--session-dir", session_dir]
        cmd += ["--start-index", str(start_index)]
        cmd += ["--poll-interval", str(poll_interval)]
        cmd += ["--player", self.player_vars["player"].get()]

        self._run_command(cmd)

    def _launch_main(self) -> None:
        cmd = [sys.executable, str(SCRIPT_DIR / "main.py")]
        config_path = self.main_vars["config"].get().strip()
        output_dir = self.main_vars["output"].get().strip()
        selected_command = self.main_vars["command"].get()
        quality_val = self._ensure_float(self.main_vars["quality"].get(), "lip-sync quality")
        if quality_val is None:
            return

        cmd += ["--config", config_path, "--output", output_dir]
        cmd.append(selected_command)

        if selected_command == "lipsync":
            if self.main_vars["enable_lipsync"].get():
                cmd.append("--enable")
            cmd += ["--quality", str(quality_val)]

        self._run_command(cmd)

    # ---------
    # Helpers
    # ---------
    def _run_command(self, cmd: list[str]) -> None:
        cmd_display = " ".join(f'"{part}"' if " " in part else part for part in cmd)
        self._append_log(f"启动命令: {cmd_display}\n")

        def _worker() -> None:
            try:
                proc = subprocess.Popen(cmd, cwd=SCRIPT_DIR)
            except FileNotFoundError:
                messagebox.showerror("启动失败", "找不到可执行文件，请确认依赖已安装")
                return
            except Exception as exc:  # pragma: no cover - GUI runtime error path
                messagebox.showerror("启动失败", f"无法启动进程: {exc}")
                return

            self.processes.append(proc)
            ret = proc.wait()
            self._append_log(f"进程结束 (退出码 {ret}): {cmd_display}\n")

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _ensure_int(self, raw: str, field: str, allow_zero: bool = True) -> int | None:
        raw = raw.strip()
        try:
            value = int(raw)
        except ValueError:
            messagebox.showerror("参数错误", f"{field} 需要为整数")
            return None
        if not allow_zero and value <= 0:
            messagebox.showerror("参数错误", f"{field} 需要为正整数")
            return None
        if allow_zero and value < 0:
            messagebox.showerror("参数错误", f"{field} 不能为负数")
            return None
        return value

    def _ensure_float(self, raw: str, field: str) -> float | None:
        raw = raw.strip()
        try:
            value = float(raw)
        except ValueError:
            messagebox.showerror("参数错误", f"{field} 需要为数字")
            return None
        return value

    def _pick_file(self, var: tk.StringVar) -> None:
        initial = var.get() or str(SCRIPT_DIR)
        file_path = filedialog.askopenfilename(initialdir=os.path.dirname(initial) if os.path.exists(initial) else SCRIPT_DIR)
        if file_path:
            var.set(file_path)

    def _pick_directory(self, var: tk.StringVar) -> None:
        initial = var.get() or str(SCRIPT_DIR)
        dir_path = filedialog.askdirectory(initialdir=initial if os.path.isdir(initial) else SCRIPT_DIR)
        if dir_path:
            var.set(dir_path)

    def _append_log(self, text: str) -> None:
        self.log_widget.configure(state=tk.NORMAL)
        self.log_widget.insert(tk.END, text)
        self.log_widget.see(tk.END)
        self.log_widget.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log_widget.configure(state=tk.NORMAL)
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.configure(state=tk.DISABLED)

    def _stop_all_processes(self) -> None:
        still_running: list[subprocess.Popen] = []
        for proc in self.processes:
            if proc.poll() is None:
                proc.terminate()
                still_running.append(proc)
        if still_running:
            self._append_log("发送终止信号到所有运行中的进程\n")
        else:
            self._append_log("当前没有运行中的进程\n")

    def _on_close(self) -> None:
        # Stop chat server and client
        if self.chat_server:
            self.chat_server.stop()
        if self.chat_client:
            self.chat_client.disconnect()
            
        if any(proc.poll() is None for proc in self.processes):
            if not messagebox.askyesno("退出", "仍有进程运行，确定要退出吗？"):
                return
            self._stop_all_processes()
        self.destroy()


def main() -> None:
    app = LauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()

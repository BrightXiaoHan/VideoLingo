# VideoLingo Chat Server + HLS/FRP 部署指南（AWS）

## 架构概览
- `chat_server.py` 在 AWS 服务器上运行，提供 8888 端口的 TCP 聊天服务。
- 本地运行 `realtime_player.py --player hls`，生成 HLS 目录（`playlist.m3u8` + `segment_*.ts`）并自带 HTTP 服务（默认 8080）。
- FRP 充当中继：`frps` 部署在 AWS；`frpc` 部署在本地机器，将本地 8080 端口映射到云端，让外网用户访问 HLS。

## 前提条件
- 一台可 SSH 的 AWS EC2（示例使用 Ubuntu），安全组开放：
  - 22/SSH（管理）
  - 8888/TCP（聊天服务）
  - 7000/TCP（FRP 主控端口）
  - 18080/TCP（示例 HLS 暴露端口，可按需调整）
- 本地环境能运行 `python realtime_player.py` 且已安装 ffmpeg（HLS 转码依赖）。
- 自备 FRP 发布包（https://github.com/fatedier/frp）。

## 在 AWS 上部署 chat_server.py
1) 基础环境
```bash
sudo apt update && sudo apt install -y python3 python3-venv ffmpeg
cd /path/to/VideoLingo
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
> `chat_server.py` 仅依赖标准库，可省略 `pip install`；若后续扩展功能，建议保持虚拟环境。

2) 运行服务（前台验证）
```bash
source /path/to/VideoLingo/.venv/bin/activate
python chat_server.py  # 默认监听 0.0.0.0:8888
```

3) 后台守护（示例 systemd）
```bash
sudo tee /etc/systemd/system/videolingo-chat.service >/dev/null <<'EOF'
[Unit]
Description=VideoLingo Chat Server
After=network.target

[Service]
WorkingDirectory=/path/to/VideoLingo
ExecStart=/path/to/VideoLingo/.venv/bin/python chat_server.py
Restart=always
User=ubuntu
Group=ubuntu

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now videolingo-chat.service
sudo systemctl status videolingo-chat.service
```
确保安全组和本机防火墙允许 8888/TCP。

## 配置 FRP（云端 frps）
1) 上传并解压 FRP 包到服务器（示例 `/opt/frp`）。
2) 创建 `frps.ini`：
```ini
[common]
bind_port = 7000          # frpc 连接端口
token = your-strong-token # 自定义，frpc 要一致
```
3) 启动（前台测试）
```bash
cd /opt/frp
./frps -c frps.ini
```
可类似上文用 systemd 守护，确保 7000/TCP 放通。

## 配置 FRP（本地 frpc，把 HLS 转发到云端）
1) 在生成 HLS 的机器安装/解压 frpc。
2) 配置 `frpc.ini`（假设本地 HLS HTTP 端口 8080，要映射到云端 18080）：
```ini
[common]
server_addr = <AWS 公网 IP 或域名>
server_port = 7000
token = your-strong-token

[hls_http]
type = tcp
local_ip = 127.0.0.1
local_port = 8080
remote_port = 18080   # 访问地址：http://<AWS IP>:18080/playlist.m3u8
```
3) 启动 frpc：
```bash
./frpc -c frpc.ini
```

## 本地启动 realtime_player.py（生成并服务 HLS）
在本地 VideoLingo 目录：
```bash
python realtime_player.py \
  --player hls \
  --hls-output-dir /tmp/videolingo_hls \
  --hls-http-host 0.0.0.0 \
  --hls-http-port 8080
```
- 程序会在新片段生成时输出 `✅ HLS segment ready`，并在 8080 提供 `playlist.m3u8`。
- 如果想用自带 HTTP 服务器之外的方案，可加 `--hls-disable-http`，然后用 Nginx/Apache 自行反向代理 `/tmp/videolingo_hls`。

## 访问与验证
1) 服务器侧验证 FRP 是否映射成功：
```bash
curl -I http://localhost:18080/playlist.m3u8  # 在 AWS 上执行
```
2) 外网客户端播放：
   - 直接在播放器（如 VLC）打开：`http://<AWS IP>:18080/playlist.m3u8`
3) 聊天客户端连接 AWS：
   - 客户端代码指向 `tcp://<AWS IP>:8888`

## 常见问题
- `playlist.m3u8` 404：确认本地 `realtime_player.py` 正在运行，frpc 日志无报错，安全组放通 18080。
- 播放卡顿：增大 `--hls-window-size`（默认 10），或确保本地网络上行带宽充足。
- ffmpeg 未安装：HLS 转码和时长探测依赖 ffmpeg，请在本地和云端都安装。

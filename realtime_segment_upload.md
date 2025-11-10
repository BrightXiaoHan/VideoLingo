# Realtime Translation → Upload → Playback Flow

## 1. Run the Translation Pipeline
- Prereqs: `config.yaml`, source视频、Python依赖都准备好。
- 在仓库根目录执行（路径按需替换）：

```bash
python realtime.py file \
  --source /path/to/source.mp4 \
  --config config_zh.yaml \
  --config config_en.yaml \
  --segment-seconds 300 \
  --output output \
  --max-concurrency 2 \
  --segment-upload-dir /tmp/videolingo_uploads \
  --segment-upload-cmd "rsync -av --rsync-path='mkdir -p /srv/hls/{session_name}/{segment_name} && rsync' {src} user@example.com:/srv/hls/{session_name}/{segment_name}/{filename}"
```

- 多语言/多配置时重复传入 `--config` 即可；每个配置会有独立 session（如 `session_20251101_config-zh`、`session_20251101_config-en`），共享切分后的原始片段。
- `realtime.py` 会循环切分并调用 `main.py` 产出 `output_dub.mp4`，每段完成后自动触发上传。

## 2. 推送文件到服务器
- `--segment-upload-dir`：可选的本地镜像目录（便于调试或本地 HLS 服务），可改或留空。
- `--segment-upload-cmd`：
  - 使用 `rsync` 通过 SSH 把每个 `output_dub.mp4` 推送到远端 `/srv/hls/<session>/<segment>/output_dub.mp4`。
  - `--rsync-path='mkdir -p … && rsync'` 确保目标目录存在。
  - 需提前配置免密 SSH（或把 `-e 'ssh -i /path/to/key'` 加到命令）。
- 上传完成后，服务器上的目录结构与本地 session 一致，方便后续 HLS 处理。

## 3. 浏览器/播放器播放
- 在服务器上运行 HLS 打包：

```bash
python realtime_player.py \
  --player hls \
  --shared-base /srv/hls \
  --session-dir /srv/hls/<session_name> \
  --hls-http-host 0.0.0.0 \
  --hls-http-port 8080
```

- 该脚本会把每个 `seg_xxxx/output_dub.mp4` 转成 `segment_xxxx.ts`，写入 `playlist.m3u8`，并自带 HTTP 服务。
- 浏览器或 VLC 打开 `http://<server>:8080/playlist.m3u8` 即可实时播放；脚本会持续监听新段并更新播放列表。若同时有多种语言，可为每个 session 启动一个 `realtime_player.py`（不同端口）或在 Web 页面列出多个 playlist URL。
- 若已有 Web 服务器，也可直接托管 `hls_stream/playlist.m3u8` 与 TS 文件对外提供 HLS。

## 提示
- 调整 `--segment-seconds` 控制每段时长；`--max-concurrency` 控制同时运行的翻译任务数。
- 如需自定义上传命令，可在模板中使用占位符：`{src}`, `{dest}`, `{session_name}`, `{segment_name}`, `{index}`, `{filename}`, `{session_dir}`, `{segment_dir}`。
- 若要本地预览，可并行运行 `realtime_player.py --player hls --session-dir output/session_xxx` 直接播放。

## clone_voice.py 使用流程

- 前提：`config.yaml` 里已设置 `fish_tts.api_key`、`fish_tts.base_url`。
- 准备一段清晰的参考语音（wav/mp3/m4a 等，10~30 秒即可）。

### 步骤
1) 运行脚本（在项目根目录）：
```bash
python clone_voice.py /path/to/ref.wav --name 我的音色
```
   - `--name`：生成的 YAML 里使用的标签（默认取文件名）。
   - `--title`：上传到 FishTTS 的模型标题，留空自动生成。
   - `--no-wait`：跳过等待训练完成（一般不需要）。

2) 等待上传和训练，脚本会打印 `model_id`，并给出两段可选的配置片段：
   - 方案 A（预设模式）：
```yaml
fish_tts:
  mode: 'preset'
  character: '我的音色'
  character_id_dict:
    '我的音色': '<model_id>'
```
   - 方案 B（保持 clone 模式，强制此模型）：
```yaml
fish_tts:
  mode: 'clone'
  force_model_id: '<model_id>'
```

3) 将其中一段粘到 `config.yaml`，保存即可固定该克隆音色。

### 常见问题
- 报 `Audio file not found`：确认路径正确，可用绝对路径。
- 等待超时：可用 `--no-wait` 跳过，稍后再用相同 `model_id` 配置。

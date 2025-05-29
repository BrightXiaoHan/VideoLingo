# VideoLingo Lip Sync 功能说明

## 概述

VideoLingo 现在支持唇形同步功能！在视频翻译和配音完成后，可以自动调整人物的嘴唇动作，使其与新的配音音频完美同步。

## 功能特点

- 🎭 **智能唇形同步**: 使用先进的 Wav2Lip 技术
- 🎯 **高精度面部检测**: 自动识别视频中的人脸
- ⚡ **可调节质量**: 支持质量与速度的平衡调节
- 🔧 **参数优化**: 提供多种参数调节选项
- 🎬 **无缝集成**: 完美融入现有的视频处理流程

## 安装说明

### 自动安装（推荐）

运行专用的安装脚本：

```bash
python scripts/install_lip_sync.py
```

### 手动安装

1. 安装依赖包：
```bash
pip install torch>=1.9.0 torchvision>=0.10.0 face-alignment>=1.3.5 scipy>=1.7.0 gdown>=4.6.0
```

2. 克隆 Wav2Lip 仓库：
```bash
git clone https://github.com/Rudrabha/Wav2Lip.git _model_cache/Wav2Lip
```

3. 下载模型文件：
```bash
# Wav2Lip GAN 模型
gdown 1JYb65kQA079KBeHbsb_06h-cdQzfuv5R -O _model_cache/Wav2Lip/checkpoints/wav2lip_gan.pth

# 面部检测模型
wget -O _model_cache/Wav2Lip/face_detection/detection/sfd/s3fd.pth \
  https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth
```

## 使用方法

### 在 Streamlit 界面中使用

1. 完成视频翻译和配音处理
2. 在 "d. Lip Synchronization" 部分：
   - 勾选 "Enable Lip Synchronization"
   - 调节 "Quality vs Speed" 滑块（可选）
   - 点击 "Start Lip Synchronization"

### 配置选项

在 `config.yaml` 中可以调节以下参数：

```yaml
## ======================== Lip Sync Settings ======================== ##
# 是否启用唇形同步
enable_lip_sync: false

# 质量调节因子 (0.5-2.0, 数值越小质量越高但速度越慢)
lip_sync_resize_factor: 1.0

# 是否禁用面部检测平滑 (可能有助于减少伪影)
lip_sync_no_smooth: false

# 面部检测边距调节 [上, 下, 左, 右]
lip_sync_pads: [0, 10, 0, 0]
```

### 命令行使用

```python
from core import _13_lip_sync

# 应用唇形同步
_13_lip_sync.apply_lip_sync()
```

## 技术原理

### Wav2Lip 技术

本功能基于 Wav2Lip 技术实现，这是一个先进的唇形同步模型：

- **论文**: "A Lip Sync Expert Is All You Need for Speech to Lip Generation In the Wild"
- **发表**: ACM Multimedia 2020
- **特点**: 高精度、适用于任何身份、语音和语言

### 处理流程

1. **面部检测**: 使用 S3FD 模型检测视频中的人脸
2. **音频预处理**: 将配音音频转换为梅尔频谱图
3. **唇形生成**: 使用 Wav2Lip 模型生成同步的嘴唇动作
4. **视频合成**: 将生成的嘴唇区域融合回原始视频

## 性能优化

### 质量 vs 速度

- **高质量模式** (`resize_factor: 0.5-0.8`): 更好的视觉效果，处理时间较长
- **平衡模式** (`resize_factor: 1.0`): 默认设置，质量和速度的良好平衡
- **快速模式** (`resize_factor: 1.2-2.0`): 更快的处理速度，质量略有下降

### 硬件要求

- **CPU**: 支持 CPU 处理，推荐多核处理器
- **GPU**: 支持 CUDA 加速（如果可用）
- **内存**: 建议至少 8GB RAM
- **存储**: 需要额外 2-3GB 空间存储模型文件

## 故障排除

### 常见问题

1. **模型下载失败**
   - 检查网络连接
   - 尝试手动下载模型文件
   - 使用 VPN 或代理

2. **面部检测失败**
   - 调整 `lip_sync_pads` 参数
   - 确保视频中人脸清晰可见
   - 尝试启用 `lip_sync_no_smooth`

3. **处理速度慢**
   - 增加 `lip_sync_resize_factor` 值
   - 确保有足够的系统资源
   - 考虑使用 GPU 加速

4. **输出质量不佳**
   - 降低 `lip_sync_resize_factor` 值
   - 调整 `lip_sync_pads` 参数
   - 确保输入视频质量良好

### 日志检查

查看详细的处理日志：

```bash
# 运行时会显示详细的处理步骤
# 如果出现错误，会显示具体的错误信息
```

## 限制说明

1. **处理时间**: 唇形同步需要额外的处理时间，特别是对于长视频
2. **视频质量**: 输入视频的质量会影响最终效果
3. **面部角度**: 侧脸或遮挡的面部可能效果不佳
4. **多人场景**: 目前主要针对单人或主要说话者优化

## 更新日志

### v1.0.0
- 初始版本发布
- 集成 Wav2Lip 技术
- 支持自动模型下载
- 提供 Streamlit 界面集成

## 参考资料

- [Wav2Lip 官方仓库](https://github.com/Rudrabha/Wav2Lip)
- [Wav2Lip 论文](http://arxiv.org/abs/2008.10010)
- [面部检测模型](https://github.com/1adrianb/face-alignment)

## 许可证

本功能基于 Wav2Lip 项目，仅供研究和个人使用。商业使用请联系原作者获取许可。 
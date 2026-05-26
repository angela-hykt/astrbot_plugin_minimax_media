# MiniMax Media Generator

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-ff69b4.svg)](https://github.com/SillyTavern/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

<p align="center">
  <b><a href="#zh">🇨🇳 中文</a></b> | <b><a href="#en">🌐 English</a></b>
</p>

---

<div id="zh"></div>

# 🇨🇳 中文

对接 MiniMax Token Plan API，提供文生图、图生图、文生视频、图生视频、音乐生成功能，并注册 LLM 工具供 Agent 调用。

---

## 🎨 功能特性

- **文生图 (t2i)**：基于文本描述生成图片，支持自定义宽高比和数量
- **图生图 (i2i)**：基于参考图片和文本描述生成新图片
- **文生视频 (t2v)**：根据文本描述生成短视频
- **图生视频 (i2v)**：基于参考图片生成动态视频
- **音乐生成**：根据描述生成背景音乐或带歌词的歌曲
- **参考图库**：支持预设人设和参考图库管理，图生图时自动引用

---

## 📦 安装

1. 将 `astrbot_plugin_minimax_media` 文件夹复制到 AstrBot 的插件目录（通常是 `addons/` 或 `data/addons/`）
2. 重启 AstrBot，或在管理面板中重载插件
3. 在「插件配置」中填入必填项

---

## ⚙️ 完整配置

所有配置项均可在 AstrBot 管理面板中填写。

### minimax_config - 基础配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `token_plan_key` | string | **是** | - | Token Plan Key，在 [platform.minimaxi.com](https://platform.minimaxi.com) > 账户管理 > Token Plan 获取 |
| `base_url` | string | 否 | `https://api.minimaxi.com` | API 基础地址，中国大陆用户保持默认；海外用户可改为 `https://api.minimax.io` |

### image_config - 图片配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `image_model` | string | 否 | `image-01` | 文生图模型，当前固定为 image-01 |
| `aspect_ratio` | string | 否 | `16:9` | 默认图片宽高比，可选 `16:9`, `1:1`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `21:9` |
| `width` | int | 否 | `0` | 自定义宽度(像素)，范围 512-2048（需 8 的倍数），设为 0 不启用。`aspect_ratio` 仍优先 |
| `height` | int | 否 | `0` | 自定义高度(像素)，需与 `width` 同时设置，范围 512-2048（需 8 的倍数） |
| `image_n` | int | 否 | `1` | 每次生成图片数量，1-9 张 |

**aspect_ratio 与对应像素尺寸：**

| `aspect_ratio` | 像素尺寸 |
|---------------|---------|
| `1:1` | 1024×1024 |
| `16:9` | 1280×720 |
| `9:16` | 720×1280 |
| `4:3` | 1152×864 |
| `3:4` | 864×1152 |
| `3:2` | 1248×832 |
| `2:3` | 832×1248 |
| `21:9` | 1344×576 |

### video_config - 视频配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `video_model` | string | 否 | `MiniMax-Hailuo-2.3` | 视频模型，可选 `MiniMax-Hailuo-2.3`, `MiniMax-Hailuo-2.3-Fast` |
| `duration` | int | 否 | `6` | 视频时长(秒)，可选 `6` 或 `10` |
| `resolution` | string | 否 | `768P` | 视频分辨率，可选 `768P`, `1080P` |

### music_config - 音乐配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `music_model` | string | 否 | `music-2.6` | 音乐生成模型，可选 `music-2.6`, `music-2.6-free` |
| `lyrics_optimizer` | bool | 否 | `true` | 开启后未提供歌词时由 AI 自动生成 |
| `audio_format` | string | 否 | `mp3` | 音频输出格式，可选 `mp3`, `wav`, `pcm` |
| `sample_rate` | int | 否 | `44100` | 音频采样率，可选 `16000`, `24000`, `32000`, `44100` |
| `bitrate` | int | 否 | `128000` | 音频比特率，可选 `32000`, `64000`, `128000`, `256000` |

### reference_config - 参考图与人设配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `default_persona` | text | 否 | `""` | 默认人设描述，文生图/图生图时自动拼接到提示词前 |
| `default_reference_image` | string | 否 | `""` | 默认参考图 URL，图生图/图生视频无附带图片时自动使用 |
| `reference_images_json` | text | 否 | `[]` | 参考图库，JSON 格式 |
| `uploaded_reference_images` | file | 否 | `[]` | 上传本地图片作为参考图，多个文件 |

**参考图库 JSON 格式示例：**

```json
[
  {
    "name": "角色A",
    "url": "https://example.com/char_a.png",
    "desc": "正面全身照"
  },
  {
    "name": "角色B",
    "url": "https://example.com/char_b.png",
    "desc": "半身像"
  }
]
```

---

## 💬 命令列表

| 命令 | 功能 | 用法 |
|------|------|------|
| `/minimax_t2i <提示词>` | 文生图 | `--no-persona` 跳过人设 |
| `/minimax_i2i <提示词>` | 图生图 | `--ref <图库名>` 指定参考图，`--no-persona` 跳过人设 |
| `/minimax_t2v <提示词>` | 文生视频 | - |
| `/minimax_i2v <提示词>` | 图生视频 | `--ref <图库名>` 指定参考图 |
| `/minimax_music <描述>` | 音乐生成 | `-l <歌词>` 指定歌词，`-inst` 纯音乐模式 |
| `/minimax_refs` | 查看当前人设、默认参考图、图库列表 | - |

---

## 🛠️ LLM 工具

Agent 可自动调用的工具：

| 工具名 | 功能 | 关键参数 |
|--------|------|----------|
| `minimax_t2i` | 文生图 | `prompt`, `aspect_ratio`, `n` |
| `minimax_i2i` | 图生图 | `prompt`, `image` (参考图路径) |
| `minimax_t2v` | 文生视频 | `prompt`, `duration`, `resolution` |
| `minimax_i2v` | 图生视频 | `prompt`, `image` (参考图路径) |
| `minimax_music` | 音乐生成 | `prompt`, `lyrics`, `is_instrumental` |

> **注意**：配置了 `default_persona` 时，文生图和图生图工具会自动拼接到提示词前。

---

## 🖼️ 参考图优先级

图生图/图生视频的参考图优先级（从高到低）：

1. **消息中附带的图片** - 用户在消息中直接发送的图片
2. **`--ref` 指定的图库图片** - 通过命令或工具参数指定图库中的图片
3. **默认参考图 URL** - 在配置中设置的 `default_reference_image`
4. **上传的参考图** - 在配置中上传的本地图片

---

## 📝 注意事项

- 视频生成是异步任务，调用后会轮询等待完成，最长 5 分钟超时
- 生成的图片/视频/音乐会下载到插件目录下的 `downloads/` 文件夹
- `output_format` 固定为 `url`，返回的媒体链接有效期为 24 小时，下载后请及时保存
- 音乐生成模型 `music-2.6-free` 为免费版本可能有调用限制

---

## 📄 许可证

本项目采用 MIT 许可证开源。

**版本**: 1.0.0
**仓库**: [https://github.com/angela-hykt/astrbot_plugin_minimax_media](https://github.com/angela-hykt/astrbot_plugin_minimax_media)

---

<div id="en"></div>

# 🌐 English

Integrate MiniMax Token Plan API to provide text-to-image, image-to-image, text-to-video, image-to-video, and music generation capabilities, with LLM tools registered for Agent invocation.

---

## 🎨 Features

- **Text-to-Image (t2i)**: Generate images from text descriptions, supports custom aspect ratio and batch quantity
- **Image-to-Image (i2i)**: Generate new images based on a reference image and text description
- **Text-to-Video (t2v)**: Generate short videos from text descriptions
- **Image-to-Video (i2v)**: Generate dynamic videos from a reference image
- **Music Generation**: Generate background music or songs with lyrics based on descriptions
- **Reference Library**: Supports preset persona and reference image library management for automatic reference during image generation

---

## 📦 Installation

1. Copy the `astrbot_plugin_minimax_media` folder to AstrBot's plugin directory (usually `addons/` or `data/addons/`)
2. Restart AstrBot, or reload the plugin from the management panel
3. Fill in the required fields in "Plugin Configuration"

---

## ⚙️ Full Configuration

All configuration items can be filled in through the AstrBot management panel.

### minimax_config - Basic Configuration

| Field | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `token_plan_key` | string | **Yes** | - | Token Plan Key, obtained from [platform.minimaxi.com](https://platform.minimaxi.com) > Account Management > Token Plan |
| `base_url` | string | No | `https://api.minimaxi.com` | API base URL, keep default for mainland China users; overseas users can change to `https://api.minimax.io` |

### image_config - Image Configuration

| Field | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `image_model` | string | No | `image-01` | Text-to-image model, currently fixed to image-01 |
| `aspect_ratio` | string | No | `16:9` | Default image aspect ratio, options: `16:9`, `1:1`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `21:9` |
| `width` | int | No | `0` | Custom width in pixels, range 512-2048 (must be multiple of 8), set to 0 to disable. `aspect_ratio` takes priority |
| `height` | int | No | `0` | Custom height in pixels, must be set together with `width`, range 512-2048 (must be multiple of 8) |
| `image_n` | int | No | `1` | Number of images to generate per request, 1-9 |

**aspect_ratio to pixel dimensions:**

| `aspect_ratio` | Pixel Size |
|---------------|------------|
| `1:1` | 1024×1024 |
| `16:9` | 1280×720 |
| `9:16` | 720×1280 |
| `4:3` | 1152×864 |
| `3:4` | 864×1152 |
| `3:2` | 1248×832 |
| `2:3` | 832×1248 |
| `21:9` | 1344×576 |

### video_config - Video Configuration

| Field | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `video_model` | string | No | `MiniMax-Hailuo-2.3` | Video model, options: `MiniMax-Hailuo-2.3`, `MiniMax-Hailuo-2.3-Fast` |
| `duration` | int | No | `6` | Video duration in seconds, options: `6` or `10` |
| `resolution` | string | No | `768P` | Video resolution, options: `768P`, `1080P` |

### music_config - Music Configuration

| Field | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `music_model` | string | No | `music-2.6` | Music generation model, options: `music-2.6`, `music-2.6-free` |
| `lyrics_optimizer` | bool | No | `true` | When enabled, AI auto-generates lyrics if none provided |
| `audio_format` | string | No | `mp3` | Audio output format, options: `mp3`, `wav`, `pcm` |
| `sample_rate` | int | No | `44100` | Audio sample rate, options: `16000`, `24000`, `32000`, `44100` |
| `bitrate` | int | No | `128000` | Audio bitrate, options: `32000`, `64000`, `128000`, `256000` |

### reference_config - Reference Image and Persona Configuration

| Field | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `default_persona` | text | No | `""` | Default persona description, automatically prepended to prompts for text-to-image and image-to-image |
| `default_reference_image` | string | No | `""` | Default reference image URL, used automatically when image-to-image/video has no attached image |
| `reference_images_json` | text | No | `[]` | Reference image library in JSON format |
| `uploaded_reference_images` | file | No | `[]` | Upload local images as reference, multiple files supported |

**Reference Image Library JSON Format Example:**

```json
[
  {
    "name": "CharacterA",
    "url": "https://example.com/char_a.png",
    "desc": "Full body front view"
  },
  {
    "name": "CharacterB",
    "url": "https://example.com/char_b.png",
    "desc": "Half body portrait"
  }
]
```

---

## 💬 Commands

| Command | Function | Usage |
|---------|----------|-------|
| `/minimax_t2i <prompt>` | Text-to-Image | `--no-persona` to skip persona |
| `/minimax_i2i <prompt>` | Image-to-Image | `--ref <library_name>` to specify reference image, `--no-persona` to skip persona |
| `/minimax_t2v <prompt>` | Text-to-Video | - |
| `/minimax_i2v <prompt>` | Image-to-Video | `--ref <library_name>` to specify reference image |
| `/minimax_music <description>` | Music Generation | `-l <lyrics>` to specify lyrics, `-inst` for instrumental mode |
| `/minimax_refs` | View current persona, default reference image, and library list | - |

---

## 🛠️ LLM Tools

Tools available for automatic invocation by Agent:

| Tool Name | Function | Key Parameters |
|-----------|----------|----------------|
| `minimax_t2i` | Text-to-Image | `prompt`, `aspect_ratio`, `n` |
| `minimax_i2i` | Image-to-Image | `prompt`, `image` (reference image path) |
| `minimax_t2v` | Text-to-Video | `prompt`, `duration`, `resolution` |
| `minimax_i2v` | Image-to-Video | `prompt`, `image` (reference image path) |
| `minimax_music` | Music Generation | `prompt`, `lyrics`, `is_instrumental` |

> **Note**: When `default_persona` is configured, text-to-image and image-to-image tools will automatically prepend it to the prompt.

---

## 🖼️ Reference Image Priority

Reference image priority for image-to-image / image-to-video (highest to lowest):

1. **Images attached in message** - Images sent directly by user in the message
2. **Reference image specified by `--ref`** - Images from library specified via command or tool parameter
3. **Default reference image URL** - Configured as `default_reference_image` in settings
4. **Uploaded reference images** - Local images uploaded in configuration

---

## 📝 Notes

- Video generation is an asynchronous task, the plugin will poll for completion after calling, with a maximum timeout of 5 minutes
- Generated images/videos/music will be downloaded to the `downloads/` folder under the plugin directory
- `output_format` is fixed to `url`, the returned media link is valid for 24 hours, please save promptly after downloading
- The music generation model `music-2.6-free` is a free version and may have usage limits

---

## 📄 License

This project is open source under the MIT License.

**Version**: 1.0.0
**Repository**: [https://github.com/angela-hykt/astrbot_plugin_minimax_media](https://github.com/angela-hykt/astrbot_plugin_minimax_media)

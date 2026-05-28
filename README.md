# 🎭 AstrBot TTS 情绪路由插件

[![Version](https://img.shields.io/badge/version-3.1.5-blue.svg)](https://github.com/muyouzhi6/astrbot_plugin_tts_emotion_router)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

面向中文场景的 TTS 插件：支持三服务商、情绪路由、UMO 黑白名单策略、分段语音、概率触发，以及 LLM 工具按需语音。

---

## ✨ 功能概览

- **三 TTS 服务商**：`siliconflow` / `minimax` / `mimo`
- **情绪路由**：`happy` / `sad` / `angry` / `neutral` → 自动切换音色和语速
- **四种独立策略**（均支持 UMO 黑白名单）：
  | 策略 | 说明 | 默认 |
  |------|------|------|
  | `voice_output` | 自动语音输出 | 开启，黑名单模式 |
  | `text_voice_output` | 文字 + 语音同时输出 | 关闭，白名单模式 |
  | `segmented_output` | 长文本分段语音 | 关闭，黑名单模式 |
  | `probability_output` | 概率触发语音 | 开启，黑名单模式 |
- **关闭自动语音后按需触发**：
  - 命令 `tts_say [文本]`
  - LLM 工具 `tts_speak(text)`
- **情绪标记注入**：自动向 LLM 注入提示，获取带情绪标记的回复
- **MiMo 高级功能**：语音设计描述、音色克隆、唱歌模式
- **分段语音**：支持固定间隔 / 自适应间隔两种模式

---

## 🚀 快速开始

1. 在 AstrBot 插件市场安装并启用本插件。
2. 系统安装 `ffmpeg`（命令行可直接调用 `ffmpeg -version`）。
3. 在插件配置面板填写 TTS 参数：
   - **推荐先用 SiliconFlow**：只需要 `key` 和 `voice_map.neutral` 即可跑通。
4. 在群聊或私聊发送以下命令验证：
   - `/sid` — 获取当前会话 UMO
   - `tts_status` — 查看插件状态
   - `tts_say 你好` — 测试语音输出

配置成功示例：

![配置示例](https://github.com/user-attachments/assets/cabc39be-e80d-4e1d-8792-7434606a8031)

---

## ⚙️ 核心配置

### TTS 服务商

在 `tts_engine.provider` 中选择：

| 值 | 服务商 | 接口 | 特点 |
|----|--------|------|------|
| `siliconflow` | 硅基流动 | `POST /v1/audio/speech` | 简单易用，推荐入门 |
| `minimax` | MiniMax | `POST /v1/t2a_v2` | 丰富参数，表情语音标签 |
| `mimo` | 小米MiMo | `POST /chat/completions` | 语音克隆，唱歌模式 |

### UMO 与黑白名单

- 在聊天中发送 `/sid` 获取当前会话的 UMO 码。
- 所有黑白名单字段均填写 UMO。
- 策略的 `mode` 字段：
  - `blacklist`：默认对所有 UMO 开启，列表中 UMO 被关闭。
  - `whitelist`：默认对所有 UMO 关闭，仅列表中 UMO 开启。
- 会话级命令 `tts_on` / `tts_off` 会影响当前 UMO 在 `voice_output` 策略中的黑白名单。

### 情绪路由配置

`emotion_route.enable = true` 时，按以下映射为不同情绪选择不同音色和语速：

```yaml
emotion_route:
  enable: true
  voice_map:
    neutral: "FunAudioLLM/CosyVoice2-0.5B:anna"
    happy: "FunAudioLLM/CosyVoice2-0.5B:cheerful"
    sad: "FunAudioLLM/CosyVoice2-0.5B:gentle"
    angry: "FunAudioLLM/CosyVoice2-0.5B:serious"
  speed_map:
    neutral: 1.0
    happy: 1.2
    sad: 0.85
    angry: 1.1
  marker:
    enable: true
    tag: "EMO"
  keywords:
    happy: ["happy", "great", "awesome", "lol"]
    sad: ["sad", "sorry", "upset", "cry"]
    angry: ["angry", "mad", "annoyed", "rage"]
```

**情绪检测优先级**（从高到低）：
1. 手动设定的待处理情绪（`tts_emote` 命令）
2. LLM 回复中的 `[EMO:happy]` 等隐藏标记
3. 基于关键词的启发式分类

**标记格式**：`[EMO:happy]` `[EMO:sad]` `[EMO:angry]` `[EMO:neutral]`
系统会向 LLM 注入指令，让模型自动在回复开头插入情绪标记。

### 语音触发条件

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `text_min_limit` | `5` | 文本最短长度，低于此值不触发 TTS |
| `text_limit` | `200` | 文本最长长度，超过此值不触发 TTS |
| `cooldown` | `0` | TTS 冷却时间（秒），0 = 不限制 |
| `allow_mixed` | `false` | 是否允许含代码/链接的混合内容触发 TTS |
| `probability.prob` | `0.8` | 触发概率（0~1） |
| `show_references` | `true` | 是否在文本输出中保留链接和代码块 |

### 分段语音参数

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `segmented_tts.enable` | `false` | 是否启用分段 |
| `segmented_tts.interval_mode` | `fixed` | `fixed` = 固定间隔，`adaptive` = 根据音频时长自适应 |
| `segmented_tts.fixed_interval` | `1.5` | 固定间隔秒数 |
| `segmented_tts.adaptive_buffer` | `0.5` | 自适应模式下的额外缓冲秒数 |
| `segmented_tts.max_segments` | `10` | 最大分段数 |
| `segmented_tts.min_segment_chars` | `50` | 文本总长度低于此值不触发分段 |
| `segmented_tts.min_segment_length` | `5` | 单个片段最小字数 |
| `segmented_tts.split_pattern` | `[。？！!?\n…]+` | 分割正则 |

---

## 🧩 命令

| 命令 | 说明 |
|------|------|
| `/sid` | 获取当前会话 UMO |
| `tts_on` | 开启当前 UMO 语音输出 |
| `tts_off` | 关闭当前 UMO 语音输出 |
| `tts_all_on` | 开启全局自动语音输出 |
| `tts_all_off` | 关闭全局自动语音输出（保留按需语音） |
| `tts_status` | 查看当前 UMO 状态（UMO、策略命中情况） |
| `tts_say [文本]` | 手动合成并发送语音（默认测试文本） |
| `tts_emote <happy\|sad\|angry\|neutral>` | 设定下一条消息的情绪 |
| `tts_prob <0~1>` | 设置 TTS 触发概率 |
| `tts_limit <int>` | 设置最大文本长度限制 |
| `tts_cooldown <int>` | 设置冷却时间（秒） |
| `tts_gain <-10~10>` | 设置音频增益（dB） |
| `tts_segment_on` / `tts_segment_off` | 开关分段语音 |
| `tts_segment_mode <fixed\|adaptive>` | 设置分段间隔模式 |
| `tts_segment_interval <秒>` | 设置分段间隔时间 |
| `tts_segment_status` | 查看分段语音状态 |
| `tts_references_on` / `tts_references_off` | 开关链接/代码块显示 |
| `tts_debug` | 显示调试信息 |
| `tts_test [文本]` | 带诊断信息的 TTS 测试 |

### LLM 工具（函数调用）

| 工具名 | 签名 | 说明 |
|--------|------|------|
| `tts_speak` | `text: str` → `string` | 由模型主动调用的按需语音输出，不受自动语音开关影响 |

---

## 🏗 服务商详解

### SiliconFlow（硅基流动）

接口：`POST {api_url}/audio/speech`

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `url` | `https://api.siliconflow.cn/v1` | API 地址 |
| `key` | — | API Key |
| `model` | `gpt-tts-pro` | 模型 |
| `format` | `mp3` | 输出格式（mp3/wav/opus/pcm） |
| `speed` | `1.0` | 语速 |
| `gain` | `0` | 增益（dB） |
| `sample_rate` | `44100` | 采样率 |
| `default_voice` | — | 默认音色 ID |

### MiniMax

接口：`POST {api_url}`（JSON）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `url` | `https://api.minimaxi.com/v1/t2a_v2` | API 地址 |
| `key` | — | API Key |
| `model` | `speech-2.8-hd` | 模型 |
| `voice_id` | `male-qn-qingse` | 默认音色 ID |
| `speed` | `1.0` | 语速 |
| `vol` | `1.0` | 音量 |
| `pitch` | `0` | 音高 |
| `emotion` | `neutral` | 默认情绪 |
| `audio_format` | `mp3` | 格式（mp3/wav/pcm/flac） |
| `sample_rate` | `32000` | 采样率 |
| `bitrate` | `128000` | 比特率 |
| `channel` | `1` | 声道数 |
| `output_format` | `hex` | 响应格式（hex/url） |
| `language_boost` | — | 语言增强 |
| `proxy` | — | HTTP/HTTPS 代理地址 |
| `voice_modify` | `{}` | 声音修改参数 |
| `timbre_weights` | `[]` | 音色混合权重 |
| `subtitle_enable` | `false` | 启用字幕 |
| `pronunciation_dict` | `{}` | 自定义发音字典 |
| `aigc_watermark` | `false` | AIGC 水印 |

### MiMo（小米）

接口：`POST {api_url}/chat/completions`（OpenAI 兼容格式）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `url` | `https://api.xiaomimimo.com/v1` | API 地址 |
| `key` | — | API Key |
| `model` | `mimo-v2.5-tts` | 模型 |
| `voice_id` | `mimo_default` | 默认音色 ID |
| `voice_description` | — | 语音设计描述（voicedesign 模型） |
| `optimize_text_preview` | `false` | 智能文本优化 |
| `clone_audio_path` | — | 克隆参考音频路径 |
| `speed` | `1.0` | 语速 |
| `emotion` | `neutral` | 默认情绪 |
| `style_instruction` | — | 自定义风格指令 |
| `singing_mode` | `false` | 唱歌模式 |
| `audio_format` | `wav` | 格式（wav/mp3/pcm16） |
| `sample_rate` | `24000` | 采样率 |

**MiMo 模型选择**：
- `mimo-v2.5-tts` — 内置音色，支持内联风格标签、唱歌模式
- `mimo-v2.5-tts-voicedesign` — 通过文字描述生成音色
- `mimo-v2.5-tts-voiceclone` — 根据参考音频克隆音色
- `mimo-v2-tts` — 旧版模型

**内置音色**：
| 模型 | 可用音色 ID |
|------|------------|
| `mimo-v2.5-tts` | `mimo_default`、`冰糖`(中/女)、`茉莉`(中/女)、`苏打`(中/男)、`白桦`(中/男)、`Mia`(英/女)、`Chloe`(英/女)、`Milo`(英/男)、`Dean`(英/男) |
| `mimo-v2-tts` | `mimo_default`、`default_zh`(中/女)、`default_en`(英/女) |

---

## 🎙 音色克隆与上传

### SiliconFlow 音色上传

1. 准备清晰人声音频（10 秒左右，尽量纯净）。
2. 上传并生成可用音色 ID。
3. 将音色 ID 填入 `voice_map`（至少配置 `neutral`）。
4. 用 `tts_say` 验证。

推荐工具：

- 一键上传站点：<https://voice.gbkgov.cn/>
- 上传工具压缩包：  
  [硅基音色一键上传.zip](https://github.com/user-attachments/files/22064355/default.zip)

### MiMo 音色克隆

使用 `mimo-v2.5-tts-voiceclone` 模型，将参考音频文件路径填入 `clone_audio_path` 即可。音频会被自动缓存，后续请求直接复用。

### MiMo 语音设计

使用 `mimo-v2.5-tts-voicedesign` 模型，在 `voice_description` 中用自然语言描述音色特征，例如 `"年轻女性，温柔甜美，语速适中"`。

---

## 🔄 与 STT 插件配合

可配合以下 STT 插件实现完整语音交互：

<https://github.com/NickCharlie/Astrbot-Voice-To-Text-Plugin>

流程：语音输入 → 文本理解 → 情绪路由 TTS 输出

---

## 🛠 常见排查

### 没有语音输出

1. 发送 `tts_status` 确认 UMO 是否命中黑白名单策略。
2. 检查 `tts_engine.provider` 对应的 `key` 是否填写。
3. 确认至少配置了 `voice_map.neutral` 或对应的 `default_voice` / `voice_id`。
4. 命令行执行 `ffmpeg -version`，确认 ffmpeg 可调用。
5. 检查网络和 API 可用性。

### 情绪没有切换

1. 确认 `emotion_route.enable = true`。
2. 确认 `voice_map` 至少配置了 `neutral`，建议 `happy` / `sad` / `angry` 都配。
3. 检查 `speed_map` 有无异常值。

### 关闭自动语音后如何让 Bot 说话

1. `tts_all_off` 关闭全局自动语音。
2. 需要时发送 `tts_say <文本>` 手动触发。
3. 或让模型通过 LLM 工具 `tts_speak` 主动调用语音。

### 分段不生效

1. 确认 `segmented_tts.enable = true`。
2. 确认当前会话命中了 `segmented_output` 策略。
3. 确认消息文本长度 ≥ `segmented_tts.min_segment_chars`（默认 50）。

---

## 💬 交流与展示

插件开发交流群：

- QQ 群：`215532038`

<img width="1284" height="2289" alt="qrcode" src="https://github.com/user-attachments/assets/113ccf60-044a-47f3-ac8f-432ae05f89ee" />

<img width="580" height="1368" alt="配置流程" src="https://github.com/user-attachments/assets/6cd57fb9-9b39-4dae-80e4-c9bd0c3400de" />

---

## 📌 项目信息

- **作者**：木有知（muyouzhi6）
- **版本**：3.1.5
- **仓库**：<https://github.com/muyouzhi6/astrbot_plugin_tts_emotion_router>
- **协议**：MIT

---

如果这个插件对你有帮助，欢迎点个 Star。

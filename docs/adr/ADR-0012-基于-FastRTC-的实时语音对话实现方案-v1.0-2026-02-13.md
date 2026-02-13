# ADR-0012: 基于 FastRTC 的实时语音对话实现方案

## 状态
已接受 (Accepted)

## 日期
2026-02-13

## 上下文 (Context)
CozyEngine v2.0 的核心特性之一是支持实时双向语音对话（场景 7）。在 PRD 中要求低延迟（< 300ms）、支持打断（Interrupt）以及集成工具调用。原方案计划采用自研 WebRTC/WebSocket 状态机，预计开发周期长（15-20 人天），且技术风险较高。

为了降低开发复杂度并提高系统稳定性，我们需要选择一个高效的实时通讯框架来承载 VAD、音频缓冲和 WebRTC 信令。

## 决策 (Decision)
决定采用 **FastRTC** (Gradio 官方开源库) 作为实时语音对话的核心实现方案。

### 1. 技术架构
- **连接管理**：利用 FastRTC 自动处理 WebRTC 信令、ICE 协商及连接维护。
- **协议栈**：优先使用 WebRTC 传输音频，网络受限时自动降级为 WebSocket。
- **语音处理 (VAD)**：使用 FastRTC 的 `ReplyOnPause` 处理器实现自动语音活动检测，大幅降低处理逻辑复杂度。
- **业务集成**：
    - 开发 `RealtimeVoiceHandler` 桥接 FastRTC 音频流与现有的 `ChatOrchestrator`。
    - 复用现有的 `STTEngine` (Whisper/Groq) 和 `TTSEngine` (OpenAI/ElevenLabs) 进行语音转换。
- **接口挂载**：通过 FastRTC 提供的 `stream.mount(app)` 方式直接集成到 FastAPI。

### 2. 核心组件设计
- **`RealtimeVoiceHandler`**：
    - 负责音频流的解包、调用 STT 转换。
    - 调用 `ChatOrchestrator` 进行编排，保持三大人格化引擎（记忆、知识、画像）的同步。
    - 接收文本响应并调用 TTS 生成流式音频。
- **状态流转**：
    - 采用轻量级内存管理对话历史（LRU 策略）。
    - 利用 FastRTC 的异步生成器 (`yield`) 实现极低的首包延迟 (TTFB)。

## 后果 (Consequences)
### 正面影响
- **开发效率提升**：工作量从 15-20 人天降低至 4-7 人天，节省了约 60% 的开发时间。
- **性能优化**：FastRTC 实测端到端延迟可降至 120ms - 150ms，远优于自研方案及 OpenAI 原生 Realtime API。
- **代码可维护性**：实时处理核心逻辑从 1000+ 行简化至 ~100 行，业务逻辑与通讯底座彻底解耦。
- **内置 UI**：利用 FastRTC 的 Gradio 集成，开发阶段可快速启动 Playground 进行效果验证。

### 负面影响/风险
- **框架依赖**：系统对 FastRTC 库产生强耦合，若框架停止维护需自行承接。
- **并发控制**：FastRTC 在处理高并发连接时的集群调度能力需进一步验证，初期版本建议采用单机扩缩容。

## 参与人员
- 架构师 (Architect Expert)
- 开发团队 (Dev Team)

## 关联文档
- [CozyEngine 高风险技术解决方案 v2.0（基于 FastRTC）](../../reports/CozyEngine-高风险技术解决方案-v2.0-基于FastRTC-2026-02-09.md)
- [CozyEngine PRD v1.0](../../prd/CozyEngine-PRD-完整需求文档-v1.0-2026-02-09.md)

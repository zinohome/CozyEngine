# Product Spec (产品规格说明书)

> **版本**: 2.0.0
> **状态**: Draft
> **最后更新**: 2026-02-14

## 1. 项目概述

CozyEngine 是一个**插件化、人格驱动的后端聊天引擎**，作为 CozyChat 的核心动力源，旨在解耦对话能力与前端业务。它通过标准化 API（兼容 OpenAI）提供稳定、可扩展的对话服务，并支持实时语音交互。

## 2. 目标用户

- **前端开发者 (CozyChat Dev)**：需要稳定、易用的 API 来构建聊天界面。
- **系统管理员 (Admin)**：需要管理多个人格、配置插件、监控系统运行状态。
- **最终用户 (End User)**：通过前端界面体验低延迟、高情商、多模态的 AI 对话。

## 3. 核心功能

### 3.1 标准对话 (Chat Completions)
- **描述**：兼容 OpenAI `v1/chat/completions` 的文本对话能力。
- **输入**：`messages` (List), `model` (String), `stream` (Bool), `cozy.personality_id` (String)。
- **输出**：JSON (非流式) 或 SSE Delta (流式)。
- **规则**：
    - 必须支持工具调用 (Tool Calls)。
    - 必须并行加载人设、记忆、知识库。
    - 必须记录审计日志。
- **优先级**：P0

### 3.2 实时语音对话 (Realtime Voice)
- **描述**：基于 WebSocket/WebRTC 的双向实时语音通话。
- **输入**：音频流 (PCM/Opus)。
- **输出**：音频流 (PCM/Opus) + 文本事件。
- **规则**：
    - **协议变更注意**：原 PRD 定义为 OpenAI Realtime API 格式 (WebSocket)，现行架构 (ADR-0012) 采用 **FastRTC (Gradio)** 协议。这是一个重大协议变更，前端需适配 Gradio Client。
    - 支持 VAD (语音活动检测) 自动断句。
    - 支持会话中简单的工具调用。
- **优先级**：P0

### 3.3 人格化引擎 (Personalization)
- **描述**：三维人格增强（长期记忆 + 知识库 + 用户画像）。
- **输入**：`cozy.use_personalization=true`。
- **输出**：增强后的 Prompt 上下文。
- **规则**：
    - 记忆/画像的更新必须异步执行，不阻塞主链路。
    - 单个引擎失败不得导致整个对话失败（自动降级）。
- **优先级**：P1

### 3.4 语音转译服务 (STT/TTS)
- **描述**：独立的语音转文字和文字转语音 API。
- **输入/输出**：Audio File <-> Text。
- **规则**：
    - TTS 支持流式输出 (Streaming Response) 以降低 TTFB。
    - STT 支持多种音频格式 (MP3/WAV/M4A)。
- **优先级**：P2

## 4. 功能优先级

| 功能 | 优先级 | 状态 | 说明 |
| :--- | :--- | :--- | :--- |
| Core Chat Pipeline | High (P0) | ✅ Done | 核心价值 |
| Realtime Voice (FastRTC) | High (P0) | ✅ Done | 差异化竞争力 |
| API Compatibility | High (P1) | 🚧 90% | 兼容层已就绪，灰度待配置 |
| Admin API | Medium (P2) | ✅ Done | 用于配置管理 |
| Streaming STT (Standalone) | Low (P3) | ❌ Missing | 目前仅有 HTTP 上传，无独立 WebSocket STT |

## 5. AI 增强功能

- **Prompt 优化**：系统自动根据用户简短输入优化 System Prompt (规划中)。
- **知识库自动清洗**：利用 LLM 在写入知识库前清洗脏数据 (规划中)。

## 6. 非功能性需求

- **延迟**：Chat P50 < 500ms; Realtime P50 < 300ms。
- **并发**：单机支持 50+ 并发 Realtime 连接。
- **兼容性**：前端必须处理 FastRTC 协议与 OpenAI 协议的差异。

## 7. 技术栈建议列表

- **Runtime**: Python 3.11+
- **Framework**: FastAPI (HTTP), FastRTC (Realtime)
- **Storage**: Postgres (Data), Redis (Cache/Queue)
- **AI Ops**: Langfuse/LangSmith (Optional for tracing)


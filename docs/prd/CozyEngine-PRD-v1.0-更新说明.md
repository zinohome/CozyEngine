# CozyEngine PRD v1.0 更新说明

> **文档版本**: v1.0  
> **更新日期**: 2026-02-09  
> **更新人**: AI Assistant  

---

## 📋 更新概览

本次 PRD 更新基于用户反馈，**将 CozyEngine 定位为 CozyChat 2.0 版本**，在技术架构上更进一步，重点增强了 **Voice Engine (语音引擎)** 能力。

---

## 🎯 核心更新

### 1. Voice Engine 技术方案升级

**从**：简单的 HTTP POST API（可选）  
**改为**：**高性能协议优先，HTTP POST 向下兼容**

#### 1.1 STT (语音转文字)

| 方案 | 协议 | 优先级 | 用途 |
|------|------|--------|------|
| **主方案** | **WebSocket 流式** | ⭐⭐⭐ | 实时转录，边说边转 |
| 兼容方案 | HTTP POST | ⭐⭐ | 录音上传，离线场景 |

**技术要点**：
- WebSocket 双向通信
- 支持 partial/final 转录结果
- VAD (Voice Activity Detection) 可选集成
- TTFR (Time To First Result) < 200ms

#### 1.2 TTS (文字转语音)

| 方案 | 协议 | 优先级 | 用途 |
|------|------|--------|------|
| **主方案** | **SSE 流式** | ⭐⭐⭐ | 边生成边播放，降低延迟 |
| 兼容方案 | HTTP POST | ⭐⭐ | 完整生成，支持缓存 |

**技术要点**：
- SSE (Server-Sent Events) 音频流
- 文本分块策略（200字/块）
- 预取优化（prefetch 2 chunks）
- TTFB (Time To First Byte) < 500ms

#### 1.3 Realtime 双向语音对话（🌟 v1.0 新增）

| 方案 | 协议 | 优先级 | 说明 |
|------|------|--------|------|
| **主方案** | **WebSocket** | ⭐⭐⭐ | 事件驱动架构，v1.0 实现 |
| 可选方案 | WebRTC | ⭐ | 更低延迟，v1.0 仅预留接口 |

**核心能力**：
- ✅ 实时双向语音对话（类似电话通话）
- ✅ 用户可打断 AI 说话
- ✅ 支持语音中调用工具
- ✅ 事件驱动架构（session/audio/text/function_call events）
- ⏸️ WebRTC 接口预留（`supports_webrtc = False`）

**性能指标**：
- 端到端延迟：< 300ms
- 打断响应：< 100ms
- 会话稳定性：99%

---

### 2. 业务场景新增

新增两个核心业务场景：

**场景 6：语音交互（STT + TTS）**
- 离线模式：录音上传 → 转文字 → 对话 → 生成语音
- 在线模式：实时转录 → 对话 → 流式语音（高性能）

**场景 7：Realtime 双向语音对话⭐**
- 实时双向通信
- 打断机制
- 工具调用支持
- 语音 + 文本混合模式

---

### 3. API 设计更新

#### 3.1 新增 Voice API 端点

```
# STT
WebSocket /v1/audio/stt/stream       (主方案)
POST      /v1/audio/stt              (兼容方案)

# TTS
POST      /v1/audio/tts/stream       (主方案，SSE)
POST      /v1/audio/tts              (兼容方案)

# Realtime ⭐
WebSocket /v1/realtime               (v1.0 新增)
POST      /v1/realtime/webrtc/session (预留)
```

#### 3.2 Voice Engine 接口规范

新增完整的 `VoiceEngine` 基类和 `RealtimeSession` 类：
- `transcribe_stream()` - WebSocket 流式 STT
- `transcribe()` - HTTP POST STT
- `speak_stream()` - SSE 流式 TTS
- `speak()` - HTTP POST TTS
- `create_realtime_session()` - 创建 Realtime 会话
- 能力声明：`supports_stream_stt/tts/realtime/webrtc`

---

### 4. 实施计划调整

新增 **Phase 4.5：Voice Engine 开发（7-12 天）**

**分为三个阶段**：
1. **阶段 1: STT 实现**（2-3 天）
   - HTTP POST + WebSocket 流式
   
2. **阶段 2: TTS 实现**（2-3 天）
   - HTTP POST + SSE 流式
   
3. **阶段 3: Realtime 实现**（3-6 天）⭐
   - WebSocket 双向通信
   - 事件驱动架构
   - 工具调用集成
   - WebRTC 接口预留

**工作量估算**：8-14 人天（建议预留 10-12 天）

---

### 5. 交付清单更新

#### 5.1 功能交付
新增语音能力板块：
- ✅ STT (HTTP POST + WebSocket)
- ✅ TTS (HTTP POST + SSE)
- ✅ Realtime (WebSocket + WebRTC 预留)

#### 5.2 质量交付
新增语音测试要求：
- Voice Engine 协议测试
- Realtime 会话/事件/断线重连测试
- 音频格式转换测试

新增性能指标：
- STT WebSocket TTFR < 200ms
- TTS SSE TTFB < 500ms
- Realtime 端到端延迟 < 300ms

---

### 6. 非目标调整

**从**：
```
❌ Realtime 语音对话后端代理（保持前端直连）
```

**改为**：
```
❌ Realtime 前端实现（后端实现 API，前端由 CozyChat 负责）
```

**说明**：
- CozyEngine 2.0 **必须实现** Realtime 后端 API
- 前端实现由 CozyChat 项目负责
- 这符合"后端引擎化"的核心目标

---

## 📊 技术决策

### ADR-005: Voice Engine 高性能协议优先

**背景**：
- CozyEngine 作为 CozyChat 2.0，应在技术上有所突破
- 传统 HTTP POST 延迟高，用户体验差
- 现代语音应用需要实时性

**决策**：
1. STT 主方案：WebSocket 流式
2. TTS 主方案：SSE 流式
3. Realtime：WebSocket（v1.0）+ WebRTC 预留
4. 同时保留 HTTP POST 向下兼容

**收益**：
- 首字节延迟降低 60-80%
- 用户体验大幅提升
- 为未来 WebRTC 优化留出空间

**风险与对策**：
- WebSocket 连接管理（中等）→ FastAPI WebSocket + 心跳
- 音频流处理（中等）→ 参考 OpenAI 官方文档
- Realtime 事件复杂性（高）→ 先核心后边缘
- WebRTC 复杂度（高）→ v1.0 仅预留接口

---

## 🎯 重点关注

### 对开发的影响

1. **工作量增加**：
   - 原计划：Phase 0-5
   - 新计划：Phase 0-5（含 4.5 Voice Engine）
   - 增量：7-12 天

2. **技术栈扩展**：
   - WebSocket 双向通信
   - SSE 流式传输
   - 音频流处理
   - 事件驱动架构（Realtime）

3. **测试复杂度提升**：
   - 增加协议兼容性测试
   - 增加音频处理测试
   - 增加 Realtime 会话测试

### 对价值的提升

1. **产品竞争力**⭐：
   - 支持实时语音对话
   - 性能领先竞品
   - 完整 OpenAI 兼容

2. **技术前瞻性**：
   - WebSocket/SSE 高性能架构
   - WebRTC 预留升级路径
   - 事件驱动可扩展

3. **用户体验**：
   - 首字节延迟降低 60-80%
   - 支持打断、实时交互
   - 流畅的语音对话

---

## ✅ 验收标准更新

除原有标准外，新增：

### Voice Engine 验收
- [ ] STT HTTP 可用（音频上传转文字）
- [ ] STT WebSocket 可用（实时流式转录，TTFR < 200ms）
- [ ] TTS HTTP 可用（文字生成音频）
- [ ] TTS SSE 可用（流式音频，TTFB < 500ms）
- [ ] Realtime WebSocket 可用（双向对话，延迟 < 300ms）
- [ ] Realtime 支持打断（< 100ms 响应）
- [ ] Realtime 支持工具调用
- [ ] 所有语音 API 可观测（日志/指标）
- [ ] WebRTC 接口预留（`supports_webrtc = False`）

---

## 📝 文档清单

本次更新涉及文档：

1. **主文档**：`CozyEngine-PRD-完整需求文档-v1.0-2026-02-09.md`
   - ✅ 更新"非目标"部分
   - ✅ 新增场景 6-7（语音交互）
   - ✅ 更新 Voice API 详细规范
   - ✅ 新增 Voice Engine 接口定义
   - ✅ 新增 Voice Engine 配置示例
   - ✅ 新增 Phase 4.5 实施计划
   - ✅ 更新交付清单

2. **本文档**：`CozyEngine-PRD-v1.0-更新说明.md`
   - 概览所有更新
   - 技术决策说明
   - 验收标准清单

---

## 🚀 下一步行动

1. **评审 PRD**：团队评审更新后的 PRD
2. **技术预研**：
   - FastAPI WebSocket 最佳实践
   - SSE 音频流传输方案
   - OpenAI Realtime API 官方文档
3. **环境准备**：
   - OpenAI API 密钥
   - 音频测试文件
   - WebSocket 测试工具
4. **启动开发**：按 Phase 0-5 计划执行

---

**文档维护者**：CozyEngine Team  
**最后更新**：2026-02-09  
**下次评审**：待定

# Product Spec Changelog

## [2.0.0] - 2026-02-14

### Added
- **Product-Spec.md**: 初始化标准化产品文档。
- **Realtime Voice**: 明确采用 FastRTC (Gradio) 协议，替代原 PRD 定义的 OpenAI Realtime WebSocket 协议。

### Changed
- **STT/TTS**: 降级 "Streaming STT (Standalone)" 优先级为 P3，目前仅 HTTP 上传模式满足 MVP 需求。
- **Realtime Protocol**: 标注前端集成风险，需使用 Gradio Client SDK。

### Deprecated
- **Native WebSocket Realtime**: 废弃原定自研 WebSocket 状态机方案 (ADR-0012)。

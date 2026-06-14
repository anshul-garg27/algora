# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# model
- Use Opus 4.8 (1M context) as the default model for all Algora modes. Sonnet 4.6 and Haiku 4.5 are secondary options. Confidence: 0.85

# workflow
- Use ultracode effort level (xhigh + dynamic workflow orchestration) for all Algora development sessions. Confidence: 0.85

# communication
- When explaining complex technical concepts (segment trees, DSU rollback, etc.), include a Hinglish block alongside English — plain Hindi-English mix that makes the concept grokkable fast. Confidence: 0.70

# architecture
- For live-interview modes, the speakable opener must stream within 30s–1min (the time a candidate takes to read a problem). Extended thinking before the opener defeats the purpose. Confidence: 0.75
- Use self-signed HTTPS certs for local dev so the Web Speech API (mic) works on iPhone/iPad over hotspot — secure context is required. Confidence: 0.70
- Per-session workspace isolation: each session writes to its own workspace/<session-slug>/ directory to prevent concurrent file collisions. Confidence: 0.70

# integration
- The Algora app runs on laptop as server and is accessible from iPhone/iPad on the same network via the laptop's local IP. History should sync across all devices accessing the same server. Confidence: 0.70


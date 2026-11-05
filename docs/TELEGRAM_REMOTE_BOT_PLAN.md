# 📱 Blueprint & Architecture Plan: Telegram Remote Control & Mobile Notification

> **Tài liệu quy hoạch kỹ thuật**: Cầu nối điều khiển từ xa (Remote Ops Bridge) và thông báo di động hai chiều cho Antigravity Multi-Agent Studio.  
> **Phiên bản kế hoạch**: v1.0 (Lưu trữ để triển khai trong pha tiếp theo).

---

## 1. Tổng Quan Kiến Trúc (Architecture Overview)

Hệ thống cho phép người dùng giám sát tiến độ của Multi-Agent Studio, nhận báo cáo kiểm thử QA tức thì từ điện thoại thông qua **Telegram Bot**, và gửi lệnh phản hồi (Chấp thuận, Từ chối, hoặc gửi Prompt mới) trực tiếp tới Lead Architect mà không cần ngồi trước máy tính.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   📱 NGƯỜI DÙNG TRÊN ĐIỆN THOẠI                        │
│   (App Telegram iOS / Android hoặc Nocode PWA qua Firebase Firestore)   │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
                   HTTPS Polling / Webhook / Realtime
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     🤖 TELEGRAM BOT / CLOUD API                         │
│               (Miễn phí 100% vĩnh viễn, bảo mật Chat ID)                │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
                        Long Polling (Không mở port)
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│             💻 ANTIGRAVITY MULTI-AGENT STUDIO (DESKTOP)                 │
│                                                                        │
│  ┌───────────────────────┐          ┌───────────────────────────────┐  │
│  │ RemoteOpsBridgeThread │ ───────> │ AgentOrchestrator             │  │
│  │ (Background QThread)  │ <─────── │ (Leader, Devs, Review, Tester)│  │
│  └───────────────────────┘          └───────────────────────────────┘  │
│             │                                                          │
│             ▼                                                          │
│   [ reports/qa_report_latest.md ]                                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Hướng Dẫn Thiết Lập Telegram Bot (100% Miễn Phí, Mất 2 Phút)

### Bước 1: Tạo Telegram Bot cá nhân
1. Mở ứng dụng **Telegram** trên điện thoại hoặc máy tính.
2. Tìm kiếm bot chính thức của Telegram: `@BotFather`.
3. Gửi lệnh `/newbot`.
4. Đặt tên hiển thị cho bot (ví dụ: `My Antigravity Studio Bot`).
5. Đặt username kết thúc bằng `bot` (ví dụ: `antigravity_studio_my_bot`).
6. `@BotFather` sẽ gửi lại một **HTTP API Token** có dạng:
   ```text
   7182938472:AAFlw91kL8kZ9Q... (Giữ bí mật token này)
   ```

### Bước 2: Lấy Chat ID cá nhân của bạn
1. Tìm bot `@userinfobot` trên Telegram và bấm `/start`.
2. Bot sẽ trả về **Id** của bạn (ví dụ: `123456789`).
3. Gửi 1 tin nhắn bất kỳ (ví dụ `/start`) tới Bot bạn vừa tạo ở Bước 1 để kích hoạt cuộc trò chuyện.

---

## 3. Đặc Tả Tính Năng Hai Chiều (Bi-directional Capabilities)

### 3.1. Chiều Xuôi (Desktop -> Mobile): Báo Cáo Tức Thì (Push Notification)
Khi Agent Tester (`David Kim` hoặc `Ethan Cole`) hoàn thành kiểm thử:
1. Desktop App trích xuất **Executive Verdict** và các chỉ số cốt lõi.
2. Định dạng tin nhắn Telegram HTML/Markdown:
   ```text
   🛡️ [QA CERTIFICATE: 100% PASS]
   ━━━━━━━━━━━━━━━━━━━━━━
   🏢 Squad: Software Engineering (Dev)
   🎯 Task: "Triển khai Dark OLED Theme & Playwright E2E"
   👨‍🔬 Tester: David Kim (Runtime QA)
   👨‍💼 To Lead: Alexander Vance

   📊 Kết Quả Kiểm Thử:
   • Unit Tests: 8/8 Passed (5.5s)
   • Playwright E2E: 3/3 Scenarios Validated
   • Chrome DevTools MCP: 0 Errors, 0 Warnings
   • Độ ổn định: 99.8% (Approved for Merge)
   ━━━━━━━━━━━━━━━━━━━━━━
   ```
3. Đính kèm **Inline Keyboard Buttons** ngay dưới tin nhắn:
   ```text
   ┌───────────────────────┬────────────────────────┐
   │  ✅ Accept & Deploy   │  ❌ Request Re-work    │
   └───────────────────────┴────────────────────────┘
   │            📄 View Full Report Link            │
   └────────────────────────────────────────────────┘
   ```

### 3.2. Chiều Ngược (Mobile -> Desktop): Điều Khiển Từ Xa
1. **Bấm Nút `[ ✅ Accept & Deploy ]`**:
   - Telegram Callback Query gửi sự kiện về `RemoteOpsBridgeThread`.
   - Desktop App kích hoạt Lead Architect thực hiện bước đóng gói hoặc kết thúc pipeline.
2. **Gõ Lệnh / Prompt Trực Tiếp (Reply Message)**:
   - Người dùng chỉ cần **Reply tin nhắn của Bot** trên điện thoại:
     *"Alexander Vance ơi, bổ sung thêm xuất file CSV cho bảng báo cáo nhé!"*
   - Desktop App nhận text, tự động nạp vào:
     ```python
     orchestrator.dispatch_hierarchical_pipeline(reply_text)
     ```
   - Lead Architect tiếp nhận prompt và bắt đầu chu trình phân rã task mới!

---

## 4. Thiết Kế Module Kỹ Thuật Dự Kiến (`src/core/remote_bridge.py`)

```python
class TelegramRemoteBridge(QThread):
    """Background worker polling Telegram Bot API for incoming commands."""
    command_received = pyqtSignal(str, str)  # (action, payload)

    def __init__(self, bot_token: str, chat_id: str, orchestrator: AgentOrchestrator):
        super().__init__()
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.orchestrator = orchestrator
        self._running = True

    def send_report_notification(self, report_summary: str, report_file_path: str):
        """Sends formatted Telegram message with inline action buttons."""
        ...

    def run(self):
        """Long-polling Telegram getUpdates loop without exposing local ports."""
        ...
```

---

## 5. Phương Án Dự Phòng: Firebase Spark Tier (Cho Nocode Mobile App)

Nếu người dùng muốn tự xây dựng giao diện ứng dụng di động riêng (bằng FlutterFlow, Glide, AppSheet hoặc MIT App Inventor):

1. **Firebase Firestore Schema**:
   - Collection `reports`:
     - Document: `{ timestamp, department, task_prompt, status: "APPROVED", score: 99.8, markdown_url }`
   - Collection `commands`:
     - Document: `{ timestamp, action: "ACCEPT" | "PROMPT", prompt_text: "...", status: "PENDING" }`
2. **Cơ chế Desktop App**:
   - Sử dụng Firebase REST API hoặc thư viện `firebase-admin` (chạy hoàn toàn miễn phí dưới hạn mức 50,000 reads/ngày của gói Spark).
   - Desktop App lắng nghe sự kiện thay đổi của collection `commands` -> Tự động kích hoạt Leader!

---

*Kế hoạch này đã được lưu trữ an toàn trong repository và sẽ sẵn sàng triển khai ngay khi có yêu cầu tiếp theo.*

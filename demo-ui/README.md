# Lab demo — realtime workflow UI

Đây là frontend demo của Lab 3, dùng Next.js App Router + TypeScript + Tailwind CSS.
Frontend chỉ làm ba việc: gửi `CustomerRequirement`, đọc `WorkflowTopology`, rồi fold
`WorkflowEvent` để hiển thị graph/timeline/inspector. Sizing, pricing, evidence resolution
và validation vẫn nằm ở backend deterministic workflow.

## Chạy local

Terminal 1 — FastAPI:

```bash
uvicorn lab3_workflow.runtime.http.app:app --reload --port 8000
```

Terminal 2 — frontend:

```bash
npm install
npm run dev
```

Mở `http://localhost:3000`. Next rewrite `/api/backend/*` sang `BACKEND_URL`
(mặc định `http://127.0.0.1:8000`) để browser dùng cùng một origin; không cần mở CORS rộng.

## Các luồng demo

1. Nhập model size, usage, concurrent users, ngân sách và storage.
2. Bấm **Start workflow** → `POST /runs` trả `run_id`.
3. UI mở SSE `/runs/{run_id}/events` và cập nhật node theo event server.
4. Bấm một event trong timeline để xem payload quan sát được ở inspector.
5. Khi workflow terminal, UI đọc snapshot `/runs/{run_id}` để hiện final state và proposal summary.

Không copy Waku runtime, branding hay design assets vào frontend.

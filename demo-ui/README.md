# Lab demo — realtime workflow UI

Đây là dashboard quan sát Lab 3, dùng Next.js App Router + TypeScript + Tailwind CSS.
Giao diện gửi `CustomerRequirement`, đọc `WorkflowTopology` và hiển thị các
`WorkflowEvent` theo thời gian thực. Sizing, pricing, evidence resolution và
validation vẫn do backend deterministic workflow quyết định.

## Bố cục

- **Graph** là sơ đồ SVG xếp lớp từ `/workflow/topology`. Các nhánh và mũi tên
  lấy từ `edge.source` / `edge.target`; chỉ đường đã có cặp `state.started`
  tương ứng mới sáng. Node có trạng thái, duration và chọn được bằng bàn phím.
- **Trace** cho biết thứ tự, offset và duration của từng event. Chọn event để
  xem dữ liệu có cấu trúc tại **Inspector** và tua graph về thời điểm đó.
  Nút **Latest** đưa graph trở lại trạng thái mới nhất.
- **Chat** hiển thị request và trạng thái workflow có nguồn từ event. Ô ghi chú
  mở bảng **New run**; ghi chú chỉ hiển thị ở UI, không được gửi vào backend hay
  giả làm phản hồi AI. Hiện chưa có stream tin nhắn OpenClaw.
- **Proposal** dùng dữ liệu từ terminal snapshot; nếu workflow không tạo
  proposal thì panel hiển thị outcome thật, không tự dựng nội dung.
- Theme mặc định **dark**, có thể chuyển **light/system**; lựa chọn được lưu trong
  `localStorage` và áp dụng trước khi trang hiển thị.

## Chạy local

Terminal 1 — FastAPI:

```bash
uvicorn lab3_workflow.runtime.http.app:app --reload --port 8000
```

Terminal 2 — frontend:

```bash
npm ci
npm run lint
npm run typecheck
npm test
npm run dev
```

Mở `http://localhost:3000`. Next rewrite `/api/backend/*` sang `BACKEND_URL`
(mặc định `http://127.0.0.1:8000`) để browser dùng cùng một origin; không cần mở CORS rộng.

## Các luồng demo

1. Bấm **New run** (hoặc nút gửi ở khung Chat) rồi nhập năm thông số workload.
2. Bấm **Start workflow** → `POST /runs` trả `run_id`; bảng thiết lập tự đóng.
3. UI mở SSE `/runs/{run_id}/events`; node, route, trace và inspector cập nhật
   bằng event server. Các nhánh không đi qua vẫn ở trạng thái chờ.
4. Chọn node hoặc event để xem trạng thái, timing, validation/evidence nếu
   backend có phát thông tin tương ứng.
5. Khi workflow terminal, UI đọc snapshot `/runs/{run_id}` với retry giới hạn
   để hiển thị final state và proposal summary. Callback của run cũ không
   được phép ghi đè run mới.

Không copy Waku runtime, branding hay design assets vào frontend.

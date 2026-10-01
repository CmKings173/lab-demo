"""Benchmark-only question recipes; independent of expansion wording."""

from __future__ import annotations

# Benchmark questions are kept as complete Vietnamese sentences for review.
# ruff: noqa: E501

RECIPES: dict[str, tuple[tuple[str, tuple[str, str]], ...]] = {
    "eval_solution_design": (
        ("deployment", (
            "Bộ phận {domain} cần triển khai model {model}B cho {users} người; cách dùng là {usage}, ngữ cảnh {context} token và trần chi {budget} triệu. Hãy ước tính tài nguyên.",
            "Với {budget} triệu, bên mình muốn phục vụ {users} người ở mảng {domain} bằng model {model}B ({usage}, context {context}). Cần chuẩn bị RAM, VRAM thế nào?",
        )),
        ("capacity", (
            "Nếu {users} người cùng sử dụng model {model}B cho {domain}, context {context} và {usage}, mức tài nguyên sơ bộ trong khoản {budget} triệu là bao nhiêu?",
            "Team {domain} dự kiến {usage} model {model}B, mỗi lượt có thể tới {context} token; {users} người dùng và ngân sách {budget} triệu. Nhờ tính nhu cầu máy ban đầu.",
        )),
        ("decision", (
            "Trước khi chọn máy cho {domain}, xin đánh giá nhu cầu bộ nhớ của model {model}B chạy {usage}: {users} người, context {context}, ngân sách {budget} triệu.",
            "Mình đang lập phương án {domain} với {users} tài khoản dùng model {model}B. Nếu {usage} ở context {context} và có {budget} triệu, nên ước lượng tài nguyên ra sao?",
        )),
        ("risk", (
            "Phương án {domain} dùng model {model}B cho {users} người, {usage}, context {context}; giới hạn tài chính {budget} triệu. Hãy nêu mức RAM/VRAM ước tính và giả định.",
            "Đội mình cần kiểm tra tính khả thi trước khi mua: {model}B cho {domain}, {users} người, {usage}, ngữ cảnh {context}, mức chi {budget} triệu. Tính tài nguyên giúp.",
        )),
        ("planning", (
            "Để dự trù máy cho {domain}, bên mình có model {model}B, {users} người truy cập, tác vụ {usage}, context {context} và {budget} triệu. Cho mình con số tài nguyên định hướng.",
            "Chưa cần SKU; chỉ cần sizing sơ bộ cho bài toán {domain}: model {model}B, {usage}, {users} người dùng, cửa sổ {context} token, ngân sách {budget} triệu.",
        )),
    ),
    "eval_novice": (
        ("starting_point", (
            "Công ty muốn dùng AI cho {domain} với khoảng {users} người nhưng mình chưa biết cần chuẩn bị thông tin gì. Bắt đầu từ đâu?",
            "Mình được giao tìm máy phục vụ {domain} cho nhóm {users} người; chưa rành AI hay phần cứng. Bạn hỏi mình những điều cần làm rõ trước nhé.",
        )),
        ("requirements", (
            "Nếu chỉ biết mục tiêu là {domain} và có {users} người sử dụng, bạn sẽ hỏi thêm những gì trước khi tư vấn cấu hình?",
            "Nhóm {users} người muốn thử AI cho {domain}. Mình chưa chốt mô hình hay cách triển khai; nên xác định yêu cầu theo thứ tự nào?",
        )),
        ("plain_language", (
            "Giải thích đơn giản giúp mình: để làm AI hỗ trợ {domain} cho {users} người, công ty phải làm rõ điều gì đầu tiên?",
            "Mình không chuyên kỹ thuật. Bên mình định dùng AI cho {domain}, cỡ {users} người; cần trao đổi với team về những điểm nào?",
        )),
        ("procurement", (
            "Trước khi xin mua máy cho dự án AI {domain} có {users} người dùng, mình cần thu thập các thông tin nào từ bộ phận sử dụng?",
            "Sếp hỏi cần mua thiết bị gì cho AI phục vụ {domain}, khoảng {users} người. Mình chưa có đủ yêu cầu; nên hỏi lại ra sao?",
        )),
        ("discovery", (
            "Dự án AI cho {domain} mới ở giai đoạn ý tưởng, dự kiến {users} người dùng. Bạn giúp mình nhận diện các câu hỏi còn thiếu được không?",
            "Bên mình muốn nội bộ hóa công việc {domain} bằng AI cho {users} người, nhưng chưa biết chọn model nào. Những thông tin nền cần chốt là gì?",
        )),
    ),
    "eval_product_search": (
        ("ceiling_first", (
            "Giới hạn cho phần máy cơ bản là {ceiling} triệu, chưa tính GPU/RAM. Hãy tìm {product_type} nào trong danh mục đáp ứng mức này.",
            "Tìm {product_type} có giá nền không vượt {ceiling} triệu; chi phí cấu hình hoàn chỉnh mình sẽ hỏi báo giá riêng.",
        )),
        ("catalog_first", (
            "Trong danh mục hiện có {product_type} nào mà giá platform tối đa {ceiling} triệu không? Đây chưa phải giá lắp đủ linh kiện.",
            "Lọc nhóm {product_type} theo trần {ceiling} triệu cho chassis cơ bản, bỏ qua giá GPU và bộ nhớ ở bước này.",
        )),
        ("quotation", (
            "Mình cần danh sách {product_type} để xin báo giá tiếp. Điều kiện ban đầu: giá máy nền cao nhất {ceiling} triệu, chưa cộng option.",
            "Trước khi báo giá cấu hình, kiểm tra giúp {product_type} nào có giá cơ bản dưới hoặc bằng {ceiling} triệu.",
        )),
        ("budget_semantics", (
            "Với khoản {ceiling} triệu dành riêng cho platform, có {product_type} nào phù hợp? Đừng coi đây là giá cả bộ máy.",
            "Chỉ đối chiếu giá chassis của {product_type}, ngưỡng {ceiling} triệu; GPU, RAM và ổ cứng chưa nằm trong khoản này.",
        )),
        ("selection", (
            "Hãy tra sản phẩm loại {product_type} có giá niêm yết cho máy cơ bản không quá {ceiling} triệu để mình chọn ứng viên.",
            "Bên mua hàng muốn sàng lọc {product_type}: mức giá phần thân máy {ceiling} triệu trở xuống, cấu hình chi tiết tính sau.",
        )),
    ),
    "eval_comparison": (
        ("targets_first", (
            "So sánh {id_a} với {id_b} về RAM tối đa, khe GPU và giá máy cơ bản; phần nào chưa có dữ liệu thì nêu rõ.",
            "Giữa hai mã {id_a} và {id_b}, sản phẩm nào có dư địa mở rộng RAM/GPU hơn theo thông tin đã có?",
        )),
        ("decision", (
            "Để chọn một trong {id_a} hoặc {id_b}, bạn đối chiếu khả năng nâng cấp và giá nền giúp mình, chưa chốt cấu hình đầy đủ.",
            "Bên mình phân vân {id_a} với {id_b}; xin nêu trade-off về bộ nhớ, số GPU và chi phí platform.",
        )),
        ("procurement", (
            "Trước khi hỏi báo giá hoàn chỉnh cho {id_a} và {id_b}, cần bảng khác biệt về thông số cơ bản của hai mã này.",
            "Phòng mua hàng cần đối chiếu {id_a}/{id_b}: RAM hỗ trợ, chỗ lắp GPU, giá máy cơ bản; chỉ dùng dữ liệu công cụ.",
        )),
        ("evidence", (
            "Bạn có thể đối chiếu {id_a} và {id_b} theo các trường được xác nhận trong danh mục, tránh đoán hiệu năng không?",
            "Với {id_a} cùng {id_b}, hãy chỉ ra dữ liệu nào đủ để so sánh và dữ liệu nào cần kiểm tra thêm.",
        )),
        ("capacity", (
            "Tôi muốn xem hai sản phẩm {id_a}, {id_b} khác nhau ra sao ở khả năng mở rộng RAM và GPU trước khi chọn.",
            "Nếu ưu tiên dư địa nâng cấp, hãy đặt {id_a} cạnh {id_b} và giải thích các giới hạn phần cứng đã biết.",
        )),
    ),
    "eval_multi_tool": (
        ("catalog_to_docs", (
            "Tìm máy loại {product_type} đáp ứng ít nhất {min_ram}GB RAM, lấy chi tiết mã {product_id} rồi kiểm tra tài liệu xác nhận RAM tối đa.",
            "Với {product_id}, tôi muốn đi từ kết quả lọc {product_type} theo RAM {min_ram}GB sang hồ sơ sản phẩm và cuối cùng là bằng chứng tài liệu về mức RAM cao nhất.",
        )),
        ("evidence_path", (
            "Đừng chỉ đọc danh mục: hãy tìm {product_type} hỗ trợ từ {min_ram}GB RAM, xem chi tiết {product_id}, rồi đối chiếu thông số RAM với tài liệu.",
            "Mã {product_id} có xuất hiện trong nhóm {product_type} đạt ngưỡng {min_ram}GB không? Sau khi lấy sản phẩm, kiểm chứng trần RAM bằng tài liệu giúp mình.",
        )),
        ("procurement_check", (
            "Trước khi đề xuất {product_id}, phòng mua hàng cần bước lọc {product_type} tối thiểu {min_ram}GB, bước xem SKU và bước đọc tài liệu về RAM tối đa.",
            "Có thể xác minh {product_id} theo chuỗi danh mục → chi tiết → datasheet không? Điều kiện sàng lọc là {product_type}, RAM ít nhất {min_ram}GB.",
        )),
        ("capacity", (
            "Hãy bắt đầu từ các {product_type} có sức chứa RAM trên {min_ram}GB; với kết quả {product_id}, lấy hồ sơ và tìm bằng chứng mức RAM cực đại.",
            "Team hạ tầng cần biết {product_id} có thể nâng RAM tới đâu. Trước hết lọc {product_type} theo {min_ram}GB, sau đó đọc chi tiết và tài liệu của đúng mã này.",
        )),
        ("traceability", (
            "Tôi cần đường kiểm chứng cho {product_id}: danh mục {product_type} đạt {min_ram}GB, bản ghi chi tiết, rồi đoạn tài liệu nêu RAM tối đa.",
            "Lọc ứng viên {product_type} với ngưỡng RAM {min_ram}GB; sau khi chọn {product_id}, hãy lấy dữ liệu sản phẩm và đối chiếu giới hạn RAM ở tài liệu nguồn.",
        )),
    ),
    "eval_technical": (
        ("context_growth", (
            "Model {model}B cần context dài tới {context}K thay vì 4K; tại sao lượng VRAM sử dụng thường tăng?",
            "Nếu mở cửa sổ ngữ cảnh từ 4K lên {context}K cho model {model}B, bộ nhớ GPU tăng chủ yếu ở phần nào?",
        )),
        ("kv_cache", (
            "KV cache có vai trò gì trong mức VRAM khi model {model}B xử lý yêu cầu dài {context}K token?",
            "Tại sao cùng model {model}B nhưng request context {context}K có thể tốn nhiều VRAM hơn request 4K?",
        )),
        ("serving_capacity", (
            "Với model {model}B, ngữ cảnh {context}K ảnh hưởng ra sao tới bộ nhớ còn lại để phục vụ thêm request đồng thời?",
            "Khi giữ nguyên trọng số {model}B mà tăng context lên {context}K, phần áp lực VRAM phát sinh từ đâu?",
        )),
        ("memory_budget", (
            "Để dự trù VRAM cho model {model}B ở context {context}K, cần xét bộ nhớ nào ngoài trọng số model?",
            "Tôi thấy model {model}B vẫn vậy nhưng chuyển từ context 4K sang {context}K thì báo thiếu VRAM; giải thích cơ chế giúp.",
        )),
        ("comparison", (
            "So với 4K, một lượt sinh ở context {context}K của model {model}B làm thay đổi nhu cầu VRAM vì sao?",
            "Có phải chỉ kích thước model {model}B quyết định VRAM, hay độ dài context {context}K cũng làm bộ nhớ tăng?",
        )),
    ),
    "eval_lora": (
        ("training_plan", (
            "Team ML cần tinh chỉnh model {model}B bằng LoRA trên dữ liệu nội bộ, context {context}K. Hãy tính tài nguyên GPU/RAM sơ bộ.",
            "Nếu chạy LoRA cho model {model}B với cửa sổ {context}K, mình cần dự trù VRAM và bộ nhớ hệ thống ở mức nào?",
        )),
        ("resource_budget", (
            "Trước khi đặt máy cho đợt LoRA model {model}B, xin ước lượng tài nguyên khi chuỗi huấn luyện dài {context}K token.",
            "Bài toán là fine-tune nội bộ model {model}B theo LoRA, ngữ cảnh {context}K; bạn giúp tính giới hạn phần cứng định hướng.",
        )),
        ("method", (
            "Không huấn luyện toàn bộ trọng số: nhóm dùng LoRA với model {model}B, context {context}K. Cần RAM/VRAM ước tính bao nhiêu?",
            "Mình muốn biết phương pháp LoRA thay đổi nhu cầu bộ nhớ ra sao khi tinh chỉnh model {model}B ở {context}K token.",
        )),
        ("capacity", (
            "Ước tính cấu hình phục vụ đợt tinh chỉnh LoRA cho model {model}B; dữ liệu có các mẫu dài khoảng {context}K token.",
            "Với bộ dữ liệu nội bộ và context {context}K, kế hoạch LoRA trên model {model}B cần dự phòng tài nguyên gì?",
        )),
        ("risk", (
            "Đội nghiên cứu định LoRA model {model}B ở context {context}K. Trước khi chốt GPU, hãy nêu mức tài nguyên cùng giả định cần benchmark.",
            "Đừng đưa con số phần cứng tuyệt đối: hãy sizing ban đầu cho fine-tune LoRA model {model}B, cửa sổ {context}K, và lưu ý rủi ro bộ nhớ.",
        )),
    ),
    "eval_requirement_change": (
        ("explicit_update", (
            "Thay phương án 7B trước đó: giờ dùng model {model}B để inference cho {users} người; ngân sách mới {budget} triệu. Tính lại giúp.",
            "Mình cần cập nhật yêu cầu cũ. Model mới là {model}B, chỉ chạy inference với {users} người cùng lúc, mức chi đã đổi thành {budget} triệu.",
        )),
        ("team_decision", (
            "Team vừa đổi từ 7B lên {model}B và quyết định phục vụ {users} người bằng inference. Khoản tiền mới {budget} triệu; tính lại tài nguyên nhé.",
            "Lãnh đạo không dùng kế hoạch ban đầu nữa: hãy lấy {model}B, {users} người, inference và trần {budget} triệu làm yêu cầu hiện hành.",
        )),
        ("supersession", (
            "Bỏ các con số cũ trong hội thoại; cấu hình cần ước tính lại cho model {model}B, inference {users} người, ngân sách {budget} triệu.",
            "Sau cuộc họp, ba giá trị đã thay đổi: model {model}B, quy mô {users} người dùng inference, và ngân sách {budget} triệu. Xin cập nhật phương án.",
        )),
        ("correction", (
            "Mình đính chính phương án trước: không còn 7B/160 triệu. Giờ inference model {model}B cho {users} người, với {budget} triệu.",
            "Yêu cầu hôm qua đã lỗi thời; team chuyển sang {model}B, {users} người truy cập inference và ngân sách {budget} triệu. Hãy tính theo bản mới.",
        )),
        ("reestimate", (
            "Nhờ tính lại từ đầu theo dữ kiện cập nhật: model {model}B, chạy inference, {users} người đồng thời, mức dự toán {budget} triệu.",
            "Nếu thay model cũ bằng {model}B và tăng thành {users} người dùng inference với {budget} triệu, ước tính tài nguyên cần sửa thế nào?",
        )),
    ),
    "eval_contradiction": (
        ("constraints_first", (
            "Chỉ có một GPU {gpu}GB nhưng muốn chạy model {model}B ở context 64K. Có đủ cơ sở chốt máy ngay không?",
            "Model {model}B, ngữ cảnh 64K, giới hạn duy nhất một card {gpu}GB: hãy chỉ ra ràng buộc nào cần kiểm chứng trước khi chọn cấu hình.",
        )),
        ("feasibility", (
            "Bên mình đề nghị model {model}B trên đúng một GPU {gpu}GB, lại cần 64K token. Đánh giá xung đột tài nguyên này giúp.",
            "Với một GPU dung lượng {gpu}GB, kế hoạch phục vụ model {model}B ở cửa sổ 64K có thể xác nhận khả thi ngay không?",
        )),
        ("procurement_risk", (
            "Trước khi đặt mua một GPU {gpu}GB cho model {model}B/context 64K, cần nêu các giả định nào để tránh chốt sai?",
            "Phòng mua hàng muốn khóa phương án 1 GPU {gpu}GB, model {model}B và ngữ cảnh 64K. Bạn có thể xác minh chắc chắn không?",
        )),
        ("memory_tension", (
            "Yêu cầu giữ model {model}B với 64K token nhưng chỉ cấp một card {gpu}GB. Mình nên làm rõ precision/quantization trước chứ?",
            "Tài nguyên bị cố định ở 1 GPU {gpu}GB, còn bài toán đòi model {model}B và context 64K; hãy chỉ ra chỗ căng thẳng cần kiểm thử.",
        )),
        ("decision", (
            "Nếu chưa biết precision, có nên cam kết model {model}B chạy context 64K trên duy nhất GPU {gpu}GB hay phải tạm dừng quyết định?",
            "Mình cần câu trả lời thận trọng cho ràng buộc model {model}B + 64K context + một GPU {gpu}GB trước khi chốt cấu hình.",
        )),
    ),
    "eval_failure": (
        ("datasheet", (
            "Đọc datasheet của {product_id} để xác nhận máy nâng RAM tối đa tới mức nào.",
            "Giới hạn bộ nhớ của mã {product_id} theo tài liệu hãng là bao nhiêu? Xin kiểm tra nguồn trước khi trả lời.",
        )),
        ("evidence", (
            "Tôi cần bằng chứng trong tài liệu cho thông số RAM cực đại của {product_id}, không dùng trí nhớ về sản phẩm.",
            "Có thể tra tài liệu kỹ thuật của {product_id} và cho biết mức RAM cao nhất được ghi nhận không?",
        )),
        ("procurement", (
            "Phòng mua hàng hỏi liệu {product_id} hỗ trợ bao nhiêu GB RAM tối đa; hãy đối chiếu tài liệu gốc giúp.",
            "Trước khi báo khách về RAM của {product_id}, xin xác minh con số giới hạn qua tài liệu sản phẩm.",
        )),
        ("capacity", (
            "Nếu muốn mở rộng RAM cho {product_id}, mức trần được datasheet xác nhận là gì?",
            "Team hạ tầng cần biết giới hạn nâng cấp bộ nhớ của {product_id}; chỉ trả lời sau khi tìm được tài liệu.",
        )),
        ("uncertainty", (
            "Mình chưa có thông số RAM cực đại của {product_id}; bạn kiểm tra nguồn tài liệu rồi mới kết luận nhé.",
            "Đừng đoán giới hạn RAM của {product_id}. Hãy thử tìm trang tài liệu chứng minh mức hỗ trợ tối đa.",
        )),
    ),
    "eval_out_of_scope": (
        ("network_design", (
            "Văn phòng {desks} bàn làm việc cần thiết kế hệ thống switch mạng; bạn chọn giúp sơ đồ kết nối nhé.",
            "Tư vấn số lượng và vị trí switch cho mạng nội bộ phục vụ {desks} chỗ ngồi được không?",
        )),
        ("procurement", (
            "Bên mua hàng cần danh sách switch mạng cho văn phòng {desks} bàn, không phải máy chạy AI.",
            "Hãy lập phương án thiết bị chuyển mạch cho {desks} nhân viên ngồi tại văn phòng.",
        )),
        ("topology", (
            "Nếu có {desks} điểm mạng ở công ty, nên vẽ topology switch và uplink ra sao?",
            "Mình muốn phân tầng access/distribution switch cho mặt bằng {desks} bàn làm việc.",
        )),
        ("operations", (
            "Đội IT đang thay switch cho khu làm việc {desks} người; cần hướng dẫn cấu hình VLAN và cổng mạng.",
            "Với văn phòng {desks} bàn, bạn tính giúp số cổng switch và dự phòng kết nối nhé.",
        )),
        ("scope", (
            "Dự án này chỉ là thiết kế mạng LAN cho {desks} chỗ, gồm switch và dây kết nối; bạn nhận tư vấn được không?",
            "Không hỏi về AI server: tôi cần phương án switch cho {desks} bàn và đường mạng nội bộ.",
        )),
    ),
}


def render_eval_prompt(family: str, variant: int, **facts: object) -> str:
    recipes = RECIPES[family]
    _, forms = recipes[(variant % 10) // 2]
    return forms[variant % 2].format(**facts)

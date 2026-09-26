"""Persona-aware Vietnamese wording recipes for expansion examples."""

# ruff: noqa: E501

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

from lab1_finetune.data.expansion.personas import PersonaProfile
from lab1_finetune.data.expansion.scenarios import ScenarioContext
from lab1_finetune.data.expansion.semantic_specs import (
    ComparisonSpec,
    ContradictionSpec,
    MultiToolFlow,
    MultiToolFlowSpec,
    RequirementChangeSpec,
    TechnicalFactSpec,
)
from lab1_finetune.data.frozen_contracts import ProductFilter, ProductType
from lab1_finetune.data.schema import ScenarioType


@dataclass(frozen=True)
class RenderedPrompt:
    text: str
    recipe_id: str


def product_type_label(product_type: ProductType) -> str:
    return "AI Server" if product_type == ProductType.AI_SERVER else "AI Workstation"


def persona_lead(
    profile: PersonaProfile, variant: int, *, include_role_clause: bool = True
) -> str:
    leads = {
        "non_technical": (
            "Mình chưa rành phần cứng",
            "Bạn giải thích dễ hiểu giúp mình",
            "Mình mới bắt đầu tìm hiểu AI",
            "Mình chưa biết nên nhìn vào thông số nào",
            "Bạn hướng dẫn từng bước giúp mình",
        ),
        "business": (
            "Mình cần phương án để trình lãnh đạo",
            "Bên mình ưu tiên kiểm soát chi phí",
            "Mình cần thấy rõ rủi ro của lựa chọn",
            "Bạn tách giúp phần đáp ứng và phần đánh đổi",
            "Phương án này cần giải thích được với ban giám đốc",
        ),
        "commercial": (
            "Bên mua sắm cần thông tin rõ để lấy báo giá",
            "Mình muốn tách từng khoản chi phí",
            "Bạn ghi rõ phần nào là giá máy cơ bản",
            "Mình cần dữ liệu có thể đối chiếu theo SKU",
            "Bên mình đang chuẩn bị hồ sơ mua sắm",
        ),
        "intermediate": (
            "Mình phụ trách vận hành hệ thống",
            "Bên mình chạy nội bộ nên quan tâm độ ổn định",
            "Mình muốn tính cả khả năng mở rộng",
            "Bạn giúp mình rà phần vận hành thực tế",
            "Mình cần phương án dễ bàn giao cho đội IT",
        ),
        "technical": (
            "Mình đang tích hợp dịch vụ này",
            "Bên mình cần kiểm tra tải API",
            "Mình quan tâm độ trễ và số người dùng đồng thời",
            "Bạn nêu rõ giả định kỹ thuật giúp mình",
            "Mình muốn biết giới hạn trước khi triển khai",
        ),
        "advanced": (
            "Mình cần chốt theo nhu cầu xử lý và bằng chứng",
            "Team ML muốn kiểm tra trade-off tài nguyên",
            "Bạn nêu rõ constraint nào đang chi phối",
            "Mình muốn tách số liệu đã xác minh khỏi giả định",
            "Phương án cần đủ cơ sở để benchmark lại",
        ),
    }
    choices = leads.get(profile.technical_level, leads["intermediate"])
    if not include_role_clause:
        return choices[variant % len(choices)]
    role_clauses = {
        "NON_TECHNICAL_USER": "mình cần cách giải thích dễ hiểu",
        "MANAGER": "mình sẽ dùng thông tin này để chốt phương án",
        "PURCHASING": "mình cần dữ liệu đủ rõ để lấy báo giá",
        "IT_GENERALIST": "mình cần bàn giao được cho đội vận hành",
        "DEVELOPER": "mình sẽ tích hợp kết quả vào API nội bộ",
        "ML_ENGINEER": "team ML sẽ benchmark lại các giả định",
        "SOLUTION_ARCHITECT": "mình cần nhìn rõ trade-off và bằng chứng",
    }
    return f"{choices[variant % len(choices)]}; {role_clauses.get(profile.persona_id, 'mình cần thông tin có thể kiểm chứng')}"


def variant_index(seed: int, family: str, index: int, count: int) -> int:
    digest = hashlib.sha256(f"{seed}:{family}:{index}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % count


def _compose_persona_prompt(
    profile: PersonaProfile,
    variant: int,
    body: str,
) -> str:
    lead_variant = variant
    if profile.persona_id == "SOLUTION_ARCHITECT":
        # This profile shares the advanced lead set with ML_ENGINEER. Rotate
        # among its architecture-relevant phrases to retain persona variation.
        lead_variant = (2, 3, 4, 0, 2)[variant % 5]
    prefix = persona_lead(profile, lead_variant, include_role_clause=False)
    return f"{prefix}. {body}"


def _solution_goal_first(context: ScenarioContext) -> str:
    return (
        f"Mục tiêu là triển khai {context.domain} với {context.model_name}, dự kiến phục vụ "
        f"{context.concurrent_users} người dùng đồng thời. Ngân sách tham chiếu khoảng "
        f"{context.budget_vnd // 1_000_000} triệu, độ dài ngữ cảnh {context.context_length} token "
        f"và lưu trữ {context.storage_gb}GB; hãy ước tính tài nguyên ban đầu và nêu giả định."
    )


def _solution_model_first(context: ScenarioContext) -> str:
    return (
        f"Với {context.model_name}, bên mình muốn triển khai {context.domain} cho "
        f"{context.concurrent_users} người dùng đồng thời. Hãy tính theo độ dài ngữ cảnh "
        f"{context.context_length} token, lưu trữ {context.storage_gb}GB và ngân sách khoảng "
        f"{context.budget_vnd // 1_000_000} triệu; trước mắt cần ước tính tài nguyên, chưa chốt SKU."
    )


def _solution_budget_first(context: ScenarioContext) -> str:
    return (
        f"Trong mức ngân sách khoảng {context.budget_vnd // 1_000_000} triệu, bên mình muốn "
        f"chạy {context.model_name} cho {context.domain}, với {context.concurrent_users} người "
        f"dùng đồng thời, ngữ cảnh {context.context_length} token và lưu trữ {context.storage_gb}GB. "
        "Bạn ước tính tài nguyên cần chuẩn bị và nêu rõ giả định giúp mình."
    )


def _solution_capacity_first(context: ScenarioContext) -> str:
    return (
        f"Hệ thống cần phục vụ {context.concurrent_users} người dùng đồng thời cho {context.domain}; "
        f"model dự kiến là {context.model_name}. Hãy ước tính tài nguyên với ngữ cảnh "
        f"{context.context_length} token, lưu trữ {context.storage_gb}GB và ngân sách tham chiếu "
        f"{context.budget_vnd // 1_000_000} triệu."
    )


def _solution_context_first(context: ScenarioContext) -> str:
    return (
        f"Bên mình dự kiến dùng ngữ cảnh {context.context_length} token và lưu trữ {context.storage_gb}GB "
        f"cho {context.domain}, chạy {context.model_name} với khoảng {context.concurrent_users} "
        f"người dùng đồng thời. Ngân sách khoảng {context.budget_vnd // 1_000_000} triệu; hãy "
        "ước tính tài nguyên ban đầu, chưa cần chọn mã máy."
    )


def _solution_resource_first(context: ScenarioContext) -> str:
    return (
        f"Để ước tính phần cứng cho {context.model_name} phục vụ {context.domain}, hãy xét "
        f"{context.concurrent_users} người dùng đồng thời, ngữ cảnh {context.context_length} token "
        f"và lưu trữ {context.storage_gb}GB. Mức ngân sách tham chiếu là "
        f"{context.budget_vnd // 1_000_000} triệu; xin nêu rõ giả định thay vì chốt SKU."
    )


_SOLUTION_RECIPES: tuple[tuple[str, Callable[[ScenarioContext], str]], ...] = (
    ("goal_first", _solution_goal_first),
    ("model_first", _solution_model_first),
    ("budget_first", _solution_budget_first),
    ("capacity_first", _solution_capacity_first),
    ("context_first", _solution_context_first),
    ("resource_first", _solution_resource_first),
)


def solution_prompt(
    profile: PersonaProfile, context: ScenarioContext, variant: int
) -> RenderedPrompt:
    recipe_id, render_body = _SOLUTION_RECIPES[variant % len(_SOLUTION_RECIPES)]
    return RenderedPrompt(
        text=_compose_persona_prompt(profile, variant, render_body(context)),
        recipe_id=recipe_id,
    )


def _known_missing_values(context: ScenarioContext, missing: set[str]) -> str:
    values: list[str] = []
    if "model_size_b" not in missing:
        values.append(f"model {context.model_name}")
    if "usage" not in missing:
        usage = "tinh chỉnh model" if context.usage.value == "fine_tune" else "chạy model"
        values.append(f"nhu cầu là {usage}")
    if "budget_vnd" not in missing:
        values.append(f"ngân sách khoảng {context.budget_vnd // 1_000_000} triệu")
    return ", ".join(values)


def _missing_fields_label(missing: set[str]) -> str:
    labels = {
        "model_size_b": "quy mô model cần dùng",
        "usage": "cách dùng (chỉ chạy model hay còn huấn luyện)",
        "budget_vnd": "mức ngân sách",
    }
    ordered = [field for field in ("model_size_b", "usage", "budget_vnd") if field in missing]
    return ", ".join(labels[field] for field in ordered) or "thông tin yêu cầu còn thiếu"


MissingBodyRenderer = Callable[[ScenarioContext, str, str], str]


def _missing_status_first(
    context: ScenarioContext, known_values: str, missing_label: str
) -> str:
    if not known_values:
        return (
            f"Nhu cầu là {context.domain}; phần cần bổ sung gồm {missing_label}. "
            "Bạn cung cấp thêm để mình có thể ước tính cấu hình."
        )
    return (
        f"Nhu cầu là {context.domain}; hiện đã rõ {known_values}, còn thiếu {missing_label}. "
        "Bạn bổ sung giúp để mình có thể ước tính cấu hình."
    )


def _missing_first(context: ScenarioContext, known_values: str, missing_label: str) -> str:
    prompt = f"Để tư vấn cho {context.domain}, trước hết cần làm rõ {missing_label}."
    return f"{prompt} Thông tin đã biết: {known_values}." if known_values else prompt


def _missing_clarification_first(
    context: ScenarioContext, known_values: str, missing_label: str
) -> str:
    return f"Bạn cho biết thêm {missing_label} để mình tư vấn phù hợp cho {context.domain} nhé."


def _missing_known_values_first(
    context: ScenarioContext, known_values: str, missing_label: str
) -> str:
    if not known_values:
        return (
            f"Hiện mình mới xác định nhu cầu {context.domain}; phần cần xác nhận tiếp là "
            f"{missing_label}."
        )
    return (
        f"Hiện mình có {known_values} cho nhu cầu {context.domain}; phần cần xác nhận tiếp là "
        f"{missing_label}."
    )


def _missing_procurement_first(
    context: ScenarioContext, known_values: str, missing_label: str
) -> str:
    prompt = f"Để chuẩn bị phương án {context.domain}, cần xác nhận {missing_label} trước."
    if known_values:
        return f"{prompt} Thông tin hiện có: {known_values}."
    return f"{prompt} Hiện mới có mục tiêu triển khai."


_MISSING_RECIPES: tuple[tuple[str, MissingBodyRenderer], ...] = (
    ("status_first", _missing_status_first),
    ("missing_first", _missing_first),
    ("clarification_first", _missing_clarification_first),
    ("known_values_first", _missing_known_values_first),
    ("procurement_first", _missing_procurement_first),
)


def missing_prompt(
    profile: PersonaProfile,
    context: ScenarioContext,
    missing: list[str],
    variant: int,
) -> RenderedPrompt:
    missing_set = set(missing)
    recipe_id, render_body = _MISSING_RECIPES[variant % len(_MISSING_RECIPES)]
    body = render_body(
        context,
        _known_missing_values(context, missing_set),
        _missing_fields_label(missing_set),
    )
    return RenderedPrompt(
        text=_compose_persona_prompt(profile, variant, body),
        recipe_id=recipe_id,
    )


def _novice_goal_only(context: ScenarioContext) -> str:
    return f"Bên mình muốn dùng AI cho {context.domain}, nhưng chưa rõ nên bắt đầu từ đâu."


def _novice_how_to_start(context: ScenarioContext) -> str:
    return (
        f"Công ty đang tìm hiểu việc dùng AI cho {context.domain}; mình nên làm rõ điều gì "
        "trước khi chọn máy?"
    )


def _novice_hardware_uncertain(context: ScenarioContext) -> str:
    return (
        f"Mình chưa biết nên chuẩn bị phần cứng ra sao cho AI dùng trong {context.domain}; "
        "bạn hướng dẫn từng bước nhé."
    )


def _novice_requirements_discovery(context: ScenarioContext) -> str:
    return (
        f"Để chuẩn bị dự án AI cho {context.domain}, mình cần cung cấp thông tin nào "
        "trước tiên?"
    )


def _novice_nontechnical_guidance(context: ScenarioContext) -> str:
    return (
        f"Mình mới tìm hiểu AI cho {context.domain}; hãy cho mình biết những điều cần làm rõ "
        "trước khi chọn máy."
    )


_NOVICE_RECIPES: tuple[tuple[str, Callable[[ScenarioContext], str]], ...] = (
    ("goal_only", _novice_goal_only),
    ("how_to_start", _novice_how_to_start),
    ("hardware_uncertain", _novice_hardware_uncertain),
    ("requirements_discovery", _novice_requirements_discovery),
    ("nontechnical_guidance", _novice_nontechnical_guidance),
)


def novice_prompt(
    profile: PersonaProfile, context: ScenarioContext, variant: int
) -> RenderedPrompt:
    recipe_id, render_body = _NOVICE_RECIPES[variant % len(_NOVICE_RECIPES)]
    return RenderedPrompt(
        text=_compose_persona_prompt(profile, variant, render_body(context)),
        recipe_id=recipe_id,
    )


SearchBodyRenderer = Callable[[str, str, str], str]


def _find_body(product_type: str, constraint: str, domain: str) -> str:
    return f"Tìm {product_type} với {constraint} để phục vụ {domain}."


def _catalog_body(product_type: str, constraint: str, domain: str) -> str:
    return f"Trong danh mục {product_type}, lọc máy có {constraint} cho {domain}."


def _quotation_body(product_type: str, constraint: str, domain: str) -> str:
    return f"Bên mình cần báo giá sơ bộ cho {product_type} phục vụ {domain}; chỉ xét {constraint}."


def _use_case_body(product_type: str, constraint: str, domain: str) -> str:
    return f"Để triển khai {domain}, bên mình cần {product_type} với {constraint}."


def _filter_body(product_type: str, constraint: str, domain: str) -> str:
    return f"Hãy lọc {product_type} có {constraint} cho {domain}."


def _question_body(product_type: str, constraint: str, domain: str) -> str:
    return f"Có {product_type} nào đáp ứng {constraint} để phục vụ {domain} không?"


_BUDGET_RECIPES: tuple[tuple[str, SearchBodyRenderer], ...] = (
    ("price_limit_first", _find_body),
    ("catalog_filter_first", _catalog_body),
    ("quotation_first", _quotation_body),
    ("use_case_first", _use_case_body),
)
_RAM_RECIPES: tuple[tuple[str, SearchBodyRenderer], ...] = (
    ("ram_constraint_first", _find_body),
    ("catalog_lookup_first", _catalog_body),
    ("use_case_first", _use_case_body),
    ("filter_first", _filter_body),
)
_GPU_RECIPES: tuple[tuple[str, SearchBodyRenderer], ...] = (
    ("gpu_constraint_first", _find_body),
    ("use_case_first", _use_case_body),
    ("catalog_filter_first", _catalog_body),
    ("filter_first", _filter_body),
)
_NO_PRODUCT_RECIPES: tuple[tuple[str, SearchBodyRenderer], ...] = (
    ("constraints_first", _find_body),
    ("use_case_first", _use_case_body),
    ("catalog_lookup_first", _catalog_body),
    ("question_first", _question_body),
)


def _render_search_prompt(
    profile: PersonaProfile,
    context: ScenarioContext,
    variant: int,
    filters: ProductFilter,
    constraint: str,
    recipes: tuple[tuple[str, SearchBodyRenderer], ...],
    tail: str = "",
) -> RenderedPrompt:
    if filters.product_type is None:
        raise ValueError("Product search requires product type")
    recipe_id, render_body = recipes[variant % len(recipes)]
    body = render_body(product_type_label(filters.product_type), constraint, context.domain)
    prefix = persona_lead(profile, variant, include_role_clause=False)
    return RenderedPrompt(f"{prefix}. {body}{tail}", recipe_id)


def search_by_budget_prompt(
    profile: PersonaProfile, context: ScenarioContext, variant: int, filters: ProductFilter
) -> RenderedPrompt:
    if filters.max_base_price_vnd is None:
        raise ValueError("Budget search requires base-price ceiling")
    constraint = f"giá máy cơ bản không quá {filters.max_base_price_vnd // 1_000_000} triệu"
    tail = (
        " Giá này chưa gồm cấu hình đầy đủ."
        f" Nhu cầu tham chiếu là {context.concurrent_users} người."
    )
    return _render_search_prompt(profile, context, variant, filters, constraint, _BUDGET_RECIPES, tail)


def search_workstation_ram_prompt(
    profile: PersonaProfile, context: ScenarioContext, variant: int, filters: ProductFilter
) -> RenderedPrompt:
    if filters.product_type != ProductType.AI_WORKSTATION or filters.min_ram_gb is None:
        raise ValueError("Workstation search requires workstation type and RAM constraint")
    constraint = f"khả năng hỗ trợ ít nhất {filters.min_ram_gb}GB RAM"
    tail = f" Dự kiến phục vụ {context.concurrent_users} người dùng."
    return _render_search_prompt(profile, context, variant, filters, constraint, _RAM_RECIPES, tail)


def search_server_gpu_prompt(
    profile: PersonaProfile, context: ScenarioContext, variant: int, filters: ProductFilter
) -> RenderedPrompt:
    if filters.product_type != ProductType.AI_SERVER or filters.min_gpu_count is None:
        raise ValueError("Server search requires server type and GPU-slot constraint")
    constraint = f"ít nhất {filters.min_gpu_count} khe GPU"
    tail = f" Dự kiến phục vụ {context.concurrent_users} người dùng."
    return _render_search_prompt(profile, context, variant, filters, constraint, _GPU_RECIPES, tail)


def no_product_found_prompt(
    profile: PersonaProfile, context: ScenarioContext, variant: int, filters: ProductFilter
) -> RenderedPrompt:
    if filters.min_ram_gb is None or filters.min_gpu_count is None:
        raise ValueError("No-product search requires RAM and GPU-slot constraints")
    constraint = f"ít nhất {filters.min_ram_gb}GB RAM và {filters.min_gpu_count} khe GPU"
    return _render_search_prompt(profile, context, variant, filters, constraint, _NO_PRODUCT_RECIPES)


def contradictory_prompt(
    profile: PersonaProfile,
    spec: ContradictionSpec,
    variant: int,
) -> RenderedPrompt:
    context = spec.context
    if spec.subtype == "large_model_low_budget":
        constraint = (
            f"{context.model_name} nhưng ngân sách tối đa cho toàn bộ cấu hình chỉ "
            f"{context.budget_vnd // 1_000_000} triệu, không được tăng ngân sách; "
            f"dự kiến {context.concurrent_users} người dùng và context {context.context_length} token"
        )
        question = "Hãy ước tính tài nguyên và nêu rõ chưa thể xác nhận giá cấu hình đầy đủ."
    else:
        constraint = (
            f"{context.model_name} full precision trên đúng một GPU "
            f"{spec.gpu_memory_gb}GB VRAM"
        )
        if spec.subtype == "context_vram_constraint":
            constraint += f" với context {context.context_length} token"
        question = "Ràng buộc này có đáp ứng được không; cần thay đổi điều kiện nào?"
    recipes = (
        ("constraint_first", f"Bên mình yêu cầu {constraint}. {question}"),
        ("feasibility_first", f"Kiểm tra tính khả thi của {constraint}. {question}"),
        ("risk_first", f"Trước khi chọn máy, hãy xem xét giới hạn {constraint}. {question}"),
    )
    recipe_id, body = recipes[variant % len(recipes)]
    return RenderedPrompt(_compose_persona_prompt(profile, variant, body), recipe_id)


def failure_prompt(
    profile: PersonaProfile,
    context: ScenarioContext,
    variant: int,
    scenario_type: str,
    product_id: str,
) -> str:
    if scenario_type == "tool_failure":
        return f"{persona_lead(profile, variant)}. Kiểm tra giúp thông số RAM tối đa của {product_id} từ tài liệu chính thức."
    return f"{persona_lead(profile, variant)}. Cho mình biết số khe GPU tối đa của {product_id} nếu tài liệu có nêu."


def _failure_direct_verification(product_id: str) -> str:
    return f"Tra tài liệu kỹ thuật để xác minh RAM tối đa của {product_id}; nếu không truy cập được nguồn, hãy nói rõ."


def _failure_evidence_first(product_id: str) -> str:
    return f"Với {product_id}, mình chỉ muốn số RAM tối đa có bằng chứng trong tài liệu; khi nguồn không phản hồi thì đừng kết luận."


def _failure_service_dependency(product_id: str) -> str:
    return f"Mình cần biết {product_id} hỗ trợ RAM đến mức nào. Hãy kiểm tra dịch vụ tài liệu trước khi trả lời."


def _failure_risk_first(product_id: str) -> str:
    return f"Để tránh ghi sai thông số của {product_id} vào hồ sơ, hãy đối chiếu tài liệu về giới hạn RAM và nêu tình trạng xác minh."


_TOOL_FAILURE_RECIPES: tuple[tuple[str, Callable[[str], str]], ...] = (
    ("direct_verification", _failure_direct_verification),
    ("evidence_first", _failure_evidence_first),
    ("service_dependency", _failure_service_dependency),
    ("risk_first", _failure_risk_first),
)


def tool_failure_prompt(
    profile: PersonaProfile, product_id: str, variant: int
) -> RenderedPrompt:
    recipe_id, render_body = _TOOL_FAILURE_RECIPES[variant % len(_TOOL_FAILURE_RECIPES)]
    return RenderedPrompt(
        text=_compose_persona_prompt(profile, variant, render_body(product_id)),
        recipe_id=recipe_id,
    )


def out_of_scope_prompt(
    profile: PersonaProfile, context: ScenarioContext, variant: int, scenario_type: str
) -> str:
    if scenario_type == "out_scope_laptop":
        return f"{persona_lead(profile, variant)}. Tư vấn giúp mình laptop gaming mỏng nhẹ để đi công tác."
    return f"{persona_lead(profile, variant)}. Bên mình cần thiết kế switch mạng cho văn phòng {context.domain}."


def _comparison_objects(spec: ComparisonSpec) -> str:
    left, right = spec.target_ids
    noun = "sản phẩm" if spec.target_type == "product" else "cấu hình"
    return f"{noun} {left} và {right}"


def _comparison_targets_first(context: ScenarioContext, spec: ComparisonSpec) -> str:
    return f"So sánh {_comparison_objects(spec)} cho nhu cầu {context.domain}."


def _comparison_criteria_first(context: ScenarioContext, spec: ComparisonSpec) -> str:
    return f"Theo các tiêu chí RAM, GPU và dữ liệu giá, hãy đối chiếu {_comparison_objects(spec)}."


def _comparison_decision_first(context: ScenarioContext, spec: ComparisonSpec) -> str:
    return f"Để chọn phương án phù hợp cho {context.domain}, hãy nêu khác biệt giữa {_comparison_objects(spec)}."


def _comparison_evidence_first(context: ScenarioContext, spec: ComparisonSpec) -> str:
    return f"Chỉ dựa trên dữ liệu có thể kiểm chứng, đánh giá {_comparison_objects(spec)} cho {context.domain}."


def _comparison_tradeoff_first(context: ScenarioContext, spec: ComparisonSpec) -> str:
    return f"Nêu ưu điểm và điểm đánh đổi giữa {_comparison_objects(spec)} theo RAM, GPU và khả năng mở rộng."


_COMPARISON_RECIPES: tuple[tuple[str, Callable[[ScenarioContext, ComparisonSpec], str]], ...] = (
    ("targets_first", _comparison_targets_first),
    ("criteria_first", _comparison_criteria_first),
    ("decision_first", _comparison_decision_first),
    ("evidence_first", _comparison_evidence_first),
    ("tradeoff_first", _comparison_tradeoff_first),
)


def comparison_prompt(
    profile: PersonaProfile,
    context: ScenarioContext,
    variant: int,
    spec: ComparisonSpec,
) -> RenderedPrompt:
    recipe_id, render_body = _COMPARISON_RECIPES[variant % len(_COMPARISON_RECIPES)]
    return RenderedPrompt(
        _compose_persona_prompt(profile, variant, render_body(context, spec)),
        recipe_id,
    )


MultiToolBodyRenderer = Callable[[ScenarioContext, MultiToolFlowSpec], str]


def _multi_tool_filters(spec: MultiToolFlowSpec) -> ProductFilter:
    if spec.filters is None or spec.filters.product_type != spec.product_type:
        raise ValueError("Multi-tool catalog flows require matching product filters")
    return spec.filters


def _multi_tool_field_label(spec: MultiToolFlowSpec) -> str:
    if spec.document_field is None:
        raise ValueError("Get-then-document flow requires a document field")
    return _TECHNICAL_FACT_LABELS[spec.document_field]


def _multi_tool_search_target(spec: MultiToolFlowSpec) -> str:
    filters = _multi_tool_filters(spec)
    if filters.min_ram_gb is None:
        raise ValueError("Search-then-get requires a visible minimum-RAM constraint")
    return (
        f"{product_type_label(spec.product_type)} hỗ trợ ít nhất "
        f"{filters.min_ram_gb}GB RAM"
    )


def _multi_tool_estimate_requirements(
    context: ScenarioContext,
    spec: MultiToolFlowSpec,
) -> str:
    filters = _multi_tool_filters(spec)
    if filters.max_base_price_vnd is None:
        raise ValueError("Estimate-then-search requires an explicit price constraint")
    budget_vnd = f"{filters.max_base_price_vnd:,}".replace(",", ".")
    usage = "chạy inference" if context.usage.value == "inference" else "fine-tune bằng LoRA"
    return (
        f"{context.model_name} để {usage}, context {context.context_length} token, "
        f"{context.concurrent_users} người dùng đồng thời, ngân sách tối đa "
        f"{budget_vnd} VND"
    )


def _multi_tool_flow_first(context: ScenarioContext, spec: MultiToolFlowSpec) -> str:
    if spec.flow == MultiToolFlow.ESTIMATE_THEN_SEARCH:
        details = _multi_tool_estimate_requirements(context, spec)
        return (
            f"Ước tính tài nguyên cho {details} trước, rồi tìm "
            f"{product_type_label(spec.product_type)} bằng mức RAM được đề xuất, "
            "trong giới hạn giá đã nêu."
        )
    if spec.flow == MultiToolFlow.SEARCH_THEN_GET_THEN_DOCUMENT:
        return (
            f"Tìm {_multi_tool_search_target(spec)} trước, mở chi tiết sản phẩm vừa tìm được, "
            "rồi đối chiếu tài liệu để xác nhận RAM tối đa."
        )
    if spec.flow == MultiToolFlow.SEARCH_THEN_GET:
        return f"Tìm {_multi_tool_search_target(spec)} trước, rồi lấy chi tiết của kết quả tìm được."
    return f"Kiểm tra {spec.product_id} trong danh mục trước, rồi đọc tài liệu xác minh {_multi_tool_field_label(spec)}."


def _multi_tool_goal_first(context: ScenarioContext, spec: MultiToolFlowSpec) -> str:
    if spec.flow == MultiToolFlow.ESTIMATE_THEN_SEARCH:
        details = _multi_tool_estimate_requirements(context, spec)
        return (
            f"Để triển khai {context.domain}, bên mình cần {details}; hãy ước tính trước, "
            f"sau đó dùng mức RAM được đề xuất để tìm {product_type_label(spec.product_type)} "
            "không vượt trần giá đã nêu."
        )
    if spec.flow == MultiToolFlow.SEARCH_THEN_GET_THEN_DOCUMENT:
        return (
            f"Để chọn máy cho {context.domain}, hãy lọc {_multi_tool_search_target(spec)}; "
            "sau đó lấy chi tiết của kết quả và dùng tài liệu kiểm chứng RAM tối đa."
        )
    if spec.flow == MultiToolFlow.SEARCH_THEN_GET:
        return f"Cho nhu cầu {context.domain}, tìm {_multi_tool_search_target(spec)} rồi mở chi tiết sản phẩm trong kết quả."
    return f"Để xác minh {_multi_tool_field_label(spec)} của {spec.product_id}, hãy lấy thông tin sản phẩm rồi tra tài liệu tương ứng."


def _multi_tool_evidence_first(context: ScenarioContext, spec: MultiToolFlowSpec) -> str:
    if spec.flow == MultiToolFlow.ESTIMATE_THEN_SEARCH:
        details = _multi_tool_estimate_requirements(context, spec)
        return (
            f"Dựa trên nhu cầu {details}, hãy ước tính tài nguyên rồi tìm và chỉ lấy "
            f"{product_type_label(spec.product_type)} theo mức RAM được đề xuất, "
            "trong phạm vi ngân sách đã nêu."
        )
    if spec.flow == MultiToolFlow.SEARCH_THEN_GET_THEN_DOCUMENT:
        return (
            f"Ưu tiên căn cứ nguồn: tìm {_multi_tool_search_target(spec)}, đọc chi tiết "
            "bản ghi được chọn, rồi đối chiếu tài liệu sản phẩm về RAM tối đa."
        )
    if spec.flow == MultiToolFlow.SEARCH_THEN_GET:
        return f"Tìm {_multi_tool_search_target(spec)} cho {context.domain}, rồi lấy thông tin chi tiết từ bản ghi danh mục."
    return f"Dùng tài liệu để xác minh {_multi_tool_field_label(spec)} của {spec.product_id}, sau khi kiểm tra bản ghi danh mục."


def _multi_tool_decision_first(context: ScenarioContext, spec: MultiToolFlowSpec) -> str:
    if spec.flow == MultiToolFlow.ESTIMATE_THEN_SEARCH:
        details = _multi_tool_estimate_requirements(context, spec)
        return (
            f"Trước khi chọn máy cho {context.domain}, hãy ước tính {details}; sau đó tìm "
            f"{product_type_label(spec.product_type)} theo mức RAM được đề xuất, "
            "không vượt trần giá đã nêu."
        )
    if spec.flow == MultiToolFlow.SEARCH_THEN_GET_THEN_DOCUMENT:
        return (
            f"Trước khi quyết định cho {context.domain}, tìm {_multi_tool_search_target(spec)}, "
            "mở chi tiết sản phẩm tìm được và kiểm tra RAM tối đa trong tài liệu."
        )
    if spec.flow == MultiToolFlow.SEARCH_THEN_GET:
        return f"Để xem lựa chọn cho {context.domain}, hãy tìm {_multi_tool_search_target(spec)} rồi lấy chi tiết kết quả."
    return f"Trước khi kết luận về {_multi_tool_field_label(spec)}, kiểm tra {spec.product_id} rồi đối chiếu tài liệu của sản phẩm."


_MULTI_TOOL_RECIPES: tuple[tuple[str, MultiToolBodyRenderer], ...] = (
    ("flow_first", _multi_tool_flow_first),
    ("goal_first", _multi_tool_goal_first),
    ("evidence_first", _multi_tool_evidence_first),
    ("decision_first", _multi_tool_decision_first),
)


def multi_tool_prompt(
    profile: PersonaProfile,
    context: ScenarioContext,
    variant: int,
    spec: MultiToolFlowSpec,
) -> RenderedPrompt:
    recipe_id, render_body = _MULTI_TOOL_RECIPES[variant % len(_MULTI_TOOL_RECIPES)]
    return RenderedPrompt(
        _compose_persona_prompt(profile, variant, render_body(context, spec)),
        recipe_id,
    )


_TECHNICAL_FACT_LABELS = {
    "max_ram_gb": "RAM tối đa",
    "max_gpu_slots": "số khe GPU tối đa",
}


def _technical_vram_context(context: ScenarioContext) -> str:
    return f"Vì sao context {context.context_length} token khi chạy {context.model_name} thường làm nhu cầu VRAM tăng?"


def _technical_vram_kv_cache(context: ScenarioContext) -> str:
    return f"KV cache của {context.model_name} thay đổi thế nào khi context dài hơn và có {context.concurrent_users} người dùng đồng thời?"


def _technical_vram_memory(context: ScenarioContext) -> str:
    return f"Khi phục vụ {context.concurrent_users} người cùng lúc bằng {context.model_name}, những phần bộ nhớ nào làm mức VRAM cần thiết tăng lên?"


def _technical_vram_concurrency(context: ScenarioContext) -> str:
    return f"Với context {context.context_length} token, số phiên chạy đồng thời ảnh hưởng ra sao đến VRAM của {context.model_name}?"


_GENERAL_VRAM_RECIPES: tuple[tuple[str, Callable[[ScenarioContext], str]], ...] = (
    ("context_effect", _technical_vram_context),
    ("kv_cache_reasoning", _technical_vram_kv_cache),
    ("memory_growth", _technical_vram_memory),
    ("concurrency_context", _technical_vram_concurrency),
)


def _technical_inference_definition(context: ScenarioContext) -> str:
    return f"Inference là gì khi đưa {context.model_name} vào phục vụ yêu cầu trong {context.domain}?"


def _technical_inference_training_contrast(context: ScenarioContext) -> str:
    return f"Inference khác huấn luyện model như thế nào khi triển khai {context.model_name}?"


def _technical_inference_weight_updates(context: ScenarioContext) -> str:
    return f"Khi {context.model_name} trả lời yêu cầu ở giai đoạn inference, trọng số model có được cập nhật không?"


def _technical_inference_serving(context: ScenarioContext) -> str:
    return f"Trong hệ thống {context.domain}, việc model đã huấn luyện tạo câu trả lời cho người dùng có phải là inference không?"


_GENERAL_INFERENCE_RECIPES: tuple[tuple[str, Callable[[ScenarioContext], str]], ...] = (
    ("definition_first", _technical_inference_definition),
    ("training_contrast", _technical_inference_training_contrast),
    ("weight_update_contrast", _technical_inference_weight_updates),
    ("serving_first", _technical_inference_serving),
)


TechnicalFactBodyRenderer = Callable[[ScenarioContext, TechnicalFactSpec], str]


def _technical_fact_product_first(context: ScenarioContext, fact: TechnicalFactSpec) -> str:
    return f"Tra tài liệu của {fact.product_id} để xác minh {_TECHNICAL_FACT_LABELS[fact.field_name]} theo dữ liệu công bố."


def _technical_fact_field_first(context: ScenarioContext, fact: TechnicalFactSpec) -> str:
    return f"Mình cần biết {_TECHNICAL_FACT_LABELS[fact.field_name]} của {fact.product_id}; chỉ dùng bằng chứng trong tài liệu kỹ thuật."


def _technical_fact_evidence_first(context: ScenarioContext, fact: TechnicalFactSpec) -> str:
    return f"Chỉ dựa trên tài liệu, hãy kiểm chứng {_TECHNICAL_FACT_LABELS[fact.field_name]} của sản phẩm {fact.product_id}."


def _technical_fact_decision_first(context: ScenarioContext, fact: TechnicalFactSpec) -> str:
    return f"Trước khi chốt phương án, tra tài liệu của {fact.product_id} xem {_TECHNICAL_FACT_LABELS[fact.field_name]} là bao nhiêu."


_TECHNICAL_FACT_RECIPES: tuple[tuple[str, TechnicalFactBodyRenderer], ...] = (
    ("product_first", _technical_fact_product_first),
    ("field_first", _technical_fact_field_first),
    ("evidence_first", _technical_fact_evidence_first),
    ("decision_first", _technical_fact_decision_first),
)


def technical_prompt(
    profile: PersonaProfile,
    context: ScenarioContext,
    variant: int,
    scenario_type: ScenarioType,
    *,
    fact: TechnicalFactSpec | None = None,
) -> RenderedPrompt:
    if scenario_type == ScenarioType.GENERAL_VRAM:
        recipes = _GENERAL_VRAM_RECIPES
        if fact is not None:
            raise ValueError("General VRAM question cannot include a product fact")
        recipe_id, render_body = recipes[variant % len(recipes)]
        body = render_body(context)
    elif scenario_type == ScenarioType.GENERAL_INFERENCE:
        recipes = _GENERAL_INFERENCE_RECIPES
        if fact is not None:
            raise ValueError("General inference question cannot include a product fact")
        recipe_id, render_body = recipes[variant % len(recipes)]
        body = render_body(context)
    elif scenario_type in {
        ScenarioType.TECHNICAL_MAX_RAM,
        ScenarioType.TECHNICAL_MAX_GPU,
        ScenarioType.UNKNOWN_PRODUCT_SPEC,
    }:
        if fact is None:
            raise ValueError("Product-spec question requires a product ID and field")
        expected_field = (
            "max_ram_gb"
            if scenario_type == ScenarioType.TECHNICAL_MAX_RAM
            else "max_gpu_slots"
        )
        if fact.field_name != expected_field:
            raise ValueError("Technical scenario and requested product field do not match")
        recipe_id, render_body = _TECHNICAL_FACT_RECIPES[variant % len(_TECHNICAL_FACT_RECIPES)]
        body = render_body(context, fact)
    else:
        raise ValueError(f"Unsupported technical scenario: {scenario_type}")
    return RenderedPrompt(_compose_persona_prompt(profile, variant, body), recipe_id)


def lora_prompt(
    profile: PersonaProfile,
    context: ScenarioContext,
    variant: int,
    scenario_type: ScenarioType,
) -> RenderedPrompt:
    if scenario_type == ScenarioType.GENERAL_LORA:
        bodies = (
            ("concept_first", f"LoRA khác fine-tune toàn bộ {context.model_name} ở điểm nào?"),
            ("memory_first", f"Vì sao LoRA thường tiết kiệm VRAM hơn khi tinh chỉnh {context.model_name}?"),
            ("adapter_first", f"Adapter LoRA hoạt động ra sao khi huấn luyện thêm {context.model_name}?"),
            ("tradeoff_first", f"Với {context.model_name}, nên cân nhắc gì giữa LoRA và fine-tune đầy đủ?"),
            ("beginner_first", f"Giải thích ngắn gọn LoRA là gì trước khi tinh chỉnh {context.model_name}."),
        )
    elif scenario_type in {ScenarioType.FINETUNE_32B_SOLUTION, ScenarioType.SOLUTION_COMPLETE}:
        basis = (
            f"fine-tune {context.model_name} bằng LoRA cho {context.domain}, "
            f"{context.concurrent_users} người dùng, context {context.context_length} token "
            f"và lưu trữ {context.storage_gb}GB"
        )
        bodies = (
            ("goal_first", f"Bên mình cần {basis}; hãy ước tính RAM và VRAM."),
            ("model_first", f"Với mô hình đã chọn, hãy tính tài nguyên để {basis}."),
            ("resource_first", f"Cần chuẩn bị bộ nhớ thế nào nếu muốn {basis}?"),
            ("context_first", f"Hãy tính tác động của context lên tài nguyên khi {basis}."),
            ("planning_first", f"Trước khi chốt máy, hãy nêu giả định và tài nguyên cho phương án {basis}."),
        )
    else:
        raise ValueError(f"Unsupported LoRA scenario: {scenario_type}")
    recipe_id, body = bodies[variant % len(bodies)]
    return RenderedPrompt(_compose_persona_prompt(profile, variant, body), recipe_id)


def requirement_change_prompt(
    profile: PersonaProfile,
    spec: RequirementChangeSpec,
    variant: int,
) -> RenderedPrompt:
    old, new = spec.old, spec.new
    changes = []
    if "model_size_b" in spec.changed_fields:
        changes.append(f"model từ {old.model_name} sang {new.model_name}")
    if "usage" in spec.changed_fields:
        old_usage = "fine-tune bằng LoRA" if old.usage.value == "fine_tune" else "chỉ chạy inference"
        new_usage = "fine-tune bằng LoRA" if new.usage.value == "fine_tune" else "chỉ chạy inference"
        changes.append(f"cách dùng từ {old_usage} sang {new_usage}")
    if "budget_vnd" in spec.changed_fields:
        changes.append(
            f"ngân sách từ {old.budget_vnd // 1_000_000} sang {new.budget_vnd // 1_000_000} triệu"
        )
    if "concurrent_users" in spec.changed_fields:
        changes.append(f"số người dùng đồng thời từ {old.concurrent_users} sang {new.concurrent_users}")
    if not changes:
        raise ValueError("Requirement-change prompt needs a real delta")
    detail = ", ".join(changes)
    recipes = (
        ("delta_first", f"Yêu cầu vừa đổi {detail}; tính lại tài nguyên theo thông tin mới."),
        ("planning_first", f"Sau khi bàn lại kế hoạch, bên mình đổi {detail}. Hãy cập nhật ước tính."),
        ("recalculate_first", f"Đừng dùng yêu cầu cũ nữa: thay {detail}. Nhờ bạn tính lại."),
    )
    recipe_id, body = recipes[variant % len(recipes)]
    return RenderedPrompt(_compose_persona_prompt(profile, variant, body), recipe_id)


def history_recipe(
    context: ScenarioContext,
    variant: int,
    *,
    unavailable_fields: frozenset[str] = frozenset(),
) -> list[dict[str, str]]:
    histories = (
        (
            frozenset({"model_size_b", "usage"}),
            [
                {
                    "role": "user",
                    "content": f"Ban đầu bên mình tính dùng {context.model_name} cho {context.domain}.",
                },
                {
                    "role": "assistant",
                    "content": "Mình đã ghi nhận phương án ban đầu; khi requirement đổi sẽ tính lại.",
                },
            ],
        ),
        (
            frozenset({"budget_vnd"}),
            [
                {
                    "role": "user",
                    "content": (
                        f"Lúc trước ngân sách dự kiến khoảng "
                        f"{context.budget_vnd // 1_000_000} triệu."
                    ),
                },
                {
                    "role": "assistant",
                    "content": "Mình sẽ tách giá máy cơ bản khỏi giá cấu hình hoàn chỉnh.",
                },
            ],
        ),
        (
            frozenset({"model_size_b", "usage"}),
            [
                {
                    "role": "user",
                    "content": f"Team vừa chọn hướng chạy {context.model_name}.",
                },
                {
                    "role": "assistant",
                    "content": (
                        "Mình sẽ cần thêm nhu cầu xử lý và số người dùng để tính tài nguyên."
                    ),
                },
            ],
        ),
        (
            frozenset(),
            [
                {
                    "role": "user",
                    "content": f"Trước đó mình nói hệ thống chỉ dùng cho {context.domain}.",
                },
                {
                    "role": "assistant",
                    "content": (
                        "Nếu có huấn luyện hoặc tinh chỉnh thì tài nguyên sẽ cần tính lại."
                    ),
                },
            ],
        ),
    )
    compatible = [
        messages
        for required_fields, messages in histories
        if required_fields.isdisjoint(unavailable_fields)
    ]
    selected = compatible[variant % len(compatible)]
    return [dict(message) for message in selected]

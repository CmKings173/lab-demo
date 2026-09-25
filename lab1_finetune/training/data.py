"""Read frozen Lab 1 exports without depending on evolving shared contracts."""

import json
from pathlib import Path
from typing import Any


def normalize_qwen_record(record: dict[str, Any]) -> dict[str, Any]:
    """Convert the frozen export to Transformers' conversational tool format."""
    if not isinstance(record, dict):
        raise ValueError("Qwen export row must be an object")
    source_messages = record.get("messages")
    source_tools = record.get("tools")
    if not isinstance(source_messages, list) or not source_messages:
        raise ValueError("Qwen export row requires messages")
    if not isinstance(source_tools, list):
        raise ValueError("Qwen export row requires a tools list")

    tools = []
    tool_names = set()
    for tool in source_tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise ValueError("Invalid tool definition")
        if not isinstance(tool.get("description"), str) or not isinstance(
            tool.get("parameters"), dict
        ):
            raise ValueError("Invalid tool definition")
        if tool["name"] in tool_names:
            raise ValueError(f"Duplicate tool definition: {tool['name']}")
        tool_names.add(tool["name"])
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
        )

    messages = []
    pending_calls: dict[str, str] = {}
    for message in source_messages:
        if not isinstance(message, dict):
            raise ValueError("Invalid message")
        role = message.get("role")
        content = message.get("content")
        calls = message.get("tool_calls", [])
        if role not in {"system", "user", "assistant", "tool"} or not isinstance(calls, list):
            raise ValueError("Invalid message role or tool_calls")
        if content is not None and not isinstance(content, str):
            raise ValueError("Message content must be text or null")
        if role != "assistant" and calls:
            raise ValueError("Only assistant messages may call tools")
        if role == "tool":
            call_id = message.get("tool_call_id")
            if call_id not in pending_calls:
                raise ValueError(f"Tool result has unknown tool_call_id: {call_id}")
            if content is None:
                raise ValueError("Tool result requires content")
            messages.append(
                {"role": "tool", "name": pending_calls.pop(call_id), "content": content}
            )
            continue
        if content is None and not (role == "assistant" and calls):
            raise ValueError(f"{role} message requires content")
        normalized: dict[str, Any] = {"role": role, "content": content or ""}
        if calls:
            normalized_calls = []
            for call in calls:
                if not isinstance(call, dict):
                    raise ValueError("Invalid tool call")
                call_id = call.get("id")
                name = call.get("name")
                arguments = call.get("arguments")
                if not isinstance(call_id, str) or not call_id or call_id in pending_calls:
                    raise ValueError("Invalid or duplicate tool call ID")
                if name not in tool_names or not isinstance(arguments, dict):
                    raise ValueError(
                        f"Tool call references unknown tool or invalid arguments: {name}"
                    )
                pending_calls[call_id] = name
                normalized_calls.append(
                    {"type": "function", "function": {"name": name, "arguments": arguments}}
                )
            normalized["tool_calls"] = normalized_calls
        messages.append(normalized)

    if pending_calls:
        raise ValueError(f"Tool calls without results: {', '.join(sorted(pending_calls))}")
    if messages[-1]["role"] != "assistant" or not messages[-1]["content"]:
        raise ValueError("Qwen export row must end with a final assistant answer")
    return {"messages": messages, "tools": tools}


def load_qwen_export(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                rows.append(normalize_qwen_record(json.loads(line)))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    if not rows:
        raise ValueError(f"Qwen export is empty: {path}")
    return rows

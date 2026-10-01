from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lab2_rag_agent.ingestion import cli
from lab2_rag_agent.runtime.settings import RuntimeSettings


def settings() -> RuntimeSettings:
    return RuntimeSettings(
        postgres_dsn="postgresql://operator:db-secret@localhost/lab2",
        weknora_base_url="http://127.0.0.1:8080",
        weknora_api_key="provider-secret",
        weknora_knowledge_base_id="configured-kb",
    )


def test_cli_requires_both_explicit_product_and_file_arguments() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(["--product-id", "product-1"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--file", "datasheet.pdf"])


def test_cli_passes_only_the_explicit_product_and_single_file_to_service(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    document = tmp_path / "manufacturer-datasheet.pdf"
    document.write_bytes(b"selected file")
    settings_value = settings()
    captured: dict = {}

    monkeypatch.setattr(
        cli.RuntimeSettings,
        "from_env",
        classmethod(lambda _cls: settings_value),
    )

    class FakeProducts:
        def __init__(self, dsn):
            captured["product_dsn"] = dsn

    class FakeDocuments:
        def __init__(self, dsn):
            captured["document_dsn"] = dsn

    class FakeIngestion:
        def __init__(self, **kwargs):
            captured["service_config"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ingest_file(self, product_id, file_path):
            captured["call"] = (product_id, file_path)
            return SimpleNamespace(
                product_id=product_id,
                knowledge_id="knowledge-1",
                provider_parse_status="completed",
            )

    monkeypatch.setattr(cli, "PostgresProductRepository", FakeProducts)
    monkeypatch.setattr(cli, "PostgresProductDocumentRepository", FakeDocuments)
    monkeypatch.setattr(cli, "WeKnoraDocumentIngestion", FakeIngestion)

    exit_code = cli.main(["--product-id", "product-1", "--file", str(document)])

    assert exit_code == 0
    assert captured["call"] == ("product-1", document)
    assert captured["product_dsn"] == captured["document_dsn"] == (
        "postgresql://operator:db-secret@localhost/lab2"
    )
    assert captured["service_config"]["knowledge_base_id"] == "configured-kb"
    assert "provider-secret" not in capsys.readouterr().out


def test_cli_hides_unexpected_local_runtime_exception_details(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli.RuntimeSettings,
        "from_env",
        classmethod(lambda _cls: settings()),
    )

    class BrokenProducts:
        def __init__(self, _dsn):
            raise RuntimeError("postgresql://operator:db-secret@localhost/lab2")

    monkeypatch.setattr(cli, "PostgresProductRepository", BrokenProducts)

    exit_code = cli.main(["--product-id", "product-1", "--file", "datasheet.pdf"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == "Document ingestion failed due to a local runtime error.\n"
    assert "db-secret" not in captured.err

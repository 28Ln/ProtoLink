from pathlib import Path

from protolink.core.documents.atomic_io import load_json_object_file, write_json_document


def test_load_json_object_file_backs_up_invalid_json(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("{not-json", encoding="utf-8")

    result = load_json_object_file(
        target,
        empty_error_message="config file is empty",
        non_object_error_message="config file must contain a JSON object",
    )

    assert result.payload is None
    assert result.error_type == "JSONDecodeError"
    assert result.backup_file is not None
    assert not target.exists()
    assert result.backup_file.read_text(encoding="utf-8") == "{not-json"


def test_load_json_object_file_rejects_non_object_payload(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("[]", encoding="utf-8")

    result = load_json_object_file(
        target,
        empty_error_message="config file is empty",
        non_object_error_message="config file must contain a JSON object",
    )

    assert result.payload is None
    assert result.error_type == "ValueError"
    assert result.backup_file is not None
    assert not target.exists()


def test_write_json_document_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text('{"old": true}', encoding="utf-8")

    write_json_document(target, {"new": 1, "label": "ProtoLink"})

    text = target.read_text(encoding="utf-8")
    assert '"new": 1' in text
    assert '"label": "ProtoLink"' in text

"""Tests for AdvisoryAuditLog."""

import json
from frontier_advisor.audit import AdvisoryAuditLog


class TestAdvisoryAuditLog:
    def test_log_creates_file(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        log = AdvisoryAuditLog(path=path)
        log.log({"event": "test", "question_preview": "hello"})
        assert path.exists()

    def test_log_appends_entries(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        log = AdvisoryAuditLog(path=path)
        log.log({"event": "first"})
        log.log({"event": "second"})
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_log_adds_timestamp(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        log = AdvisoryAuditLog(path=path)
        log.log({"event": "test"})
        entry = json.loads(path.read_text().strip())
        assert "logged_at" in entry

    def test_log_adds_question_hash(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        log = AdvisoryAuditLog(path=path)
        log.log({"event": "test", "question_preview": "what is X?"})
        entry = json.loads(path.read_text().strip())
        assert "question_hash" in entry
        assert len(entry["question_hash"]) == 16

    def test_log_no_hash_without_preview(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        log = AdvisoryAuditLog(path=path)
        log.log({"event": "test"})
        entry = json.loads(path.read_text().strip())
        assert "question_hash" not in entry

    def test_recent_returns_last_n(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        log = AdvisoryAuditLog(path=path)
        for i in range(10):
            log.log({"event": f"entry_{i}"})
        recent = log.recent(3)
        assert len(recent) == 3
        assert recent[0]["event"] == "entry_7"
        assert recent[2]["event"] == "entry_9"

    def test_recent_empty_log(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        log = AdvisoryAuditLog(path=path)
        assert log.recent() == []

    def test_recent_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.jsonl"
        log = AdvisoryAuditLog(path=path)
        assert log.recent() == []

    def test_same_question_same_hash(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        log = AdvisoryAuditLog(path=path)
        log.log({"question_preview": "what is X?"})
        log.log({"question_preview": "what is X?"})
        lines = path.read_text().strip().split("\n")
        e1, e2 = json.loads(lines[0]), json.loads(lines[1])
        assert e1["question_hash"] == e2["question_hash"]

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "audit.jsonl"
        log = AdvisoryAuditLog(path=path)
        log.log({"event": "test"})
        assert path.exists()

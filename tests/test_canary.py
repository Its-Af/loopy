"""Canary integrity: baseline capture, clean verify, tamper detection."""

from __future__ import annotations

from tools import canary


def test_manifest_covers_hot_files():
    m = canary.compute_manifest()
    # Every protocol + agent markdown file should be hashed.
    assert any("protocol/RULES.md" in k for k in m)
    assert any("agents/execs.md" in k for k in m)
    assert all(len(h) == 64 for h in m.values())   # sha256 hex


def test_verify_clean_after_baseline():
    canary.write_manifest()
    result = canary.verify()
    assert result.ok
    assert not result.drift


def test_verify_detects_modification(monkeypatch):
    canary.write_manifest()
    # Simulate a hot file changing by perturbing the recomputed hash for one key.
    real = canary.compute_manifest()
    victim = next(iter(real))
    tampered = dict(real)
    tampered[victim] = "0" * 64
    monkeypatch.setattr(canary, "compute_manifest", lambda: tampered)
    result = canary.verify()
    assert not result.ok
    assert victim in result.modified


def test_verify_without_baseline_is_untrusted():
    # No manifest written -> everything counts as "added" (not yet trusted).
    result = canary.verify()
    assert not result.ok
    assert result.added

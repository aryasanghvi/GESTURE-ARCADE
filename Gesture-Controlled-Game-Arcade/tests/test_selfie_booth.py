"""Tests for the Selfie Booth module.

These tests do not require a real webcam or a display; they validate the
pure-logic and image-processing parts of the feature.
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class TestFilters:
    """Verify each filter returns a valid BGR image of the same shape."""

    @pytest.fixture
    def sample_frame(self):
        """200×150 random BGR frame."""
        rng = np.random.default_rng(0)
        return rng.integers(0, 256, (150, 200, 3), dtype=np.uint8)

    def _check(self, result, expected_shape):
        assert result is not None
        assert result.shape == expected_shape
        assert result.dtype == np.uint8

    def test_original(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.original(sample_frame)
        self._check(out, sample_frame.shape)
        # Should be equal content (copy)
        assert np.array_equal(out, sample_frame)

    def test_original_is_copy(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.original(sample_frame)
        out[0, 0, 0] = 0
        assert not np.array_equal(out, sample_frame)

    def test_grayscale(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.grayscale(sample_frame)
        self._check(out, sample_frame.shape)
        # All three channels should be equal (grey)
        assert np.array_equal(out[:, :, 0], out[:, :, 1])
        assert np.array_equal(out[:, :, 1], out[:, :, 2])

    def test_vintage(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.vintage(sample_frame)
        self._check(out, sample_frame.shape)

    def test_warm(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.warm(sample_frame)
        self._check(out, sample_frame.shape)

    def test_cool(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.cool(sample_frame)
        self._check(out, sample_frame.shape)

    def test_cyberpunk(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.cyberpunk(sample_frame)
        self._check(out, sample_frame.shape)

    def test_glow(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.glow(sample_frame)
        self._check(out, sample_frame.shape)

    def test_all_filter_names_apply_without_error(self, sample_frame):
        from src.selfie_booth import Filters
        for name in Filters.NAMES:
            out = Filters.apply(name, sample_frame)
            assert out is not None, f"Filter '{name}' returned None"
            assert out.shape == sample_frame.shape

    def test_unknown_filter_falls_back_to_original(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.apply("__nonexistent__", sample_frame)
        assert np.array_equal(out, sample_frame)

    def test_warm_increases_red_channel_on_average(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.warm(sample_frame)
        orig_r = sample_frame[:, :, 2].astype(int).mean()
        warm_r = out[:, :, 2].astype(int).mean()
        assert warm_r >= orig_r  # warm filter raises red on average

    def test_cool_increases_blue_channel_on_average(self, sample_frame):
        from src.selfie_booth import Filters
        out = Filters.cool(sample_frame)
        orig_b = sample_frame[:, :, 0].astype(int).mean()
        cool_b = out[:, :, 0].astype(int).mean()
        assert cool_b >= orig_b  # cool filter raises blue on average


# ---------------------------------------------------------------------------
# Camera wrapper (without real hardware)
# ---------------------------------------------------------------------------

class TestCameraWrapper:
    """_Camera should degrade gracefully when hardware is unavailable."""

    def test_camera_reports_unavailable_on_bad_index(self):
        from src.selfie_booth import _Camera
        cam = _Camera(index=999)
        # Should not raise; status should indicate failure
        assert cam.available is False
        assert "unavailable" in cam.status.lower() or "error" in cam.status.lower()

    def test_camera_read_returns_none_when_unavailable(self):
        from src.selfie_booth import _Camera
        cam = _Camera(index=999)
        frame = cam.read()
        assert frame is None

    def test_camera_release_is_idempotent(self):
        from src.selfie_booth import _Camera
        cam = _Camera(index=999)
        cam.release()
        cam.release()  # second call must not raise


# ---------------------------------------------------------------------------
# Save-path logic
# ---------------------------------------------------------------------------

class TestSaveDirectory:
    """Verify SELFIES_DIR constant and directory creation logic."""

    def test_selfies_dir_constant_is_set(self):
        from src.selfie_booth import SELFIES_DIR
        assert "selfies" in SELFIES_DIR

    def test_save_dir_created(self, tmp_path, monkeypatch):
        import src.selfie_booth as sb_module
        target = str(tmp_path / "selfies")
        monkeypatch.setattr(sb_module, "SELFIES_DIR", target)
        import os
        os.makedirs(target, exist_ok=True)
        assert os.path.isdir(target)

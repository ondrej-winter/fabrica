"""Tests for the pinned-ripgrep package public API."""

from fabrica.features.workspace_searching.adapters.outbound import pinned_ripgrep


def test_pinned_ripgrep_package_exports_the_curated_public_api() -> None:
    assert set(pinned_ripgrep.__all__) == {
        "AsyncioPinnedRipgrepCommandRunner",
        "PinnedRipgrepCommandResult",
        "PinnedRipgrepUnavailableError",
        "PinnedRipgrepWorkspaceSearchBackend",
        "PosixWorkspaceSourceLoader",
        "RipgrepJsonEventError",
        "build_pinned_ripgrep_command",
        "parse_ripgrep_json_events",
        "verified_pinned_ripgrep_executable",
    }

    for exported_name in pinned_ripgrep.__all__:
        assert hasattr(pinned_ripgrep, exported_name)

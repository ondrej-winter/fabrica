"""Tests for evidence-first commit-message orchestration."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field

import pytest

from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageEvidenceBundle,
    CommitMessageRecommendation,
    CommitMessageWorkflowResult,
    DeveloperWorkflowStatus,
    GenerateCommitMessageCommand,
    GenerateCommitMessageResult,
    GitStagedChangesFailureCategory,
    GitStagedDiff,
    GitStagedFile,
    GitStagedFileList,
    GitStagedFileStatus,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    CommitMessageAnalysisError,
    CommitMessageSkillContextLoadError,
    CommitMessageSynthesisError,
    GitStagedChangesLoadError,
)
from fabrica.features.developer_workflow.application.use_cases import (
    CommitMessageWorkflow,
    GenerateCommitMessage,
    GenerateCommitMessageError,
    GenerateCommitMessageOptions,
)
from fabrica.shared_kernel.model_usage import ModelUsageEvidence


@dataclass
class FakeStagedChangesLoader:
    staged_files: GitStagedFileList
    diffs: dict[str, GitStagedDiff]
    list_error: GitStagedChangesLoadError | None = None
    diff_error_by_path: dict[str, GitStagedChangesLoadError] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    def load_diff(self) -> GitStagedDiff:
        msg = "full staged diff loading is not used by multi-call generation"
        raise AssertionError(msg)

    def list_files(self) -> GitStagedFileList:
        self.events.append("list_files")
        if self.list_error is not None:
            raise self.list_error
        return self.staged_files

    async def list_files_async(self) -> GitStagedFileList:
        return self.list_files()

    def load_file_diff(self, path: str) -> GitStagedDiff:
        self.events.append(f"load_file_diff:{path}")
        if path in self.diff_error_by_path:
            raise self.diff_error_by_path[path]
        return self.diffs[path]

    async def load_file_diff_async(self, path: str) -> GitStagedDiff:
        return self.load_file_diff(path)


@dataclass
class FakeAnalyzer:
    events: list[str]
    error_by_path: dict[str, CommitMessageAnalysisError] = field(default_factory=dict)
    summary_by_path: dict[str, str] = field(default_factory=dict)
    calls: list[AnalyzeStagedFileForCommitMessageCommand] = field(default_factory=list)

    def analyze(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        self.calls.append(command)
        path = command.staged_file.path
        self.events.append(f"analyze:{path}")
        if path in self.error_by_path:
            raise self.error_by_path[path]
        return _evidence(command.staged_file, summary=self.summary_by_path.get(path, f"Analyzed {path}."))

    async def analyze_async(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        return self.analyze(command)


@dataclass
class FakeSynthesizer:
    events: list[str]
    error: CommitMessageSynthesisError | None = None
    calls: list[SynthesizeCommitMessageCommand] = field(default_factory=list)

    def synthesize(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        self.calls.append(command)
        self.events.append("synthesize")
        if self.error is not None:
            raise self.error
        return CommitMessageRecommendation(
            summary="Adds multi-call evidence-first commit-message generation.",
            rationale="The staged evidence is collected per file before final synthesis.",
            commit_message="feat(developer-workflow): generate commit messages from per-file evidence",
        )

    async def synthesize_async(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        return self.synthesize(command)


@dataclass
class RecordingQueryExecutor:
    """Fake async fanout executor that records concurrency and preserves input order."""

    max_concurrency_values: list[int] = field(default_factory=list)
    execution_order: list[int] = field(default_factory=list)

    async def gather_ordered[T](
        self, operations: Sequence[Callable[[], Awaitable[T]]], *, max_concurrency: int
    ) -> tuple[T, ...]:
        self.max_concurrency_values.append(max_concurrency)
        indexed_results: dict[int, T] = {}
        for index in reversed(range(len(operations))):
            self.execution_order.append(index)
            indexed_results[index] = await operations[index]()
        return tuple(indexed_results[index] for index in range(len(operations)))


@dataclass
class FakeCommitMessageGenerator:
    result: GenerateCommitMessageResult | Exception
    skill_ids: list[str] = field(default_factory=list)

    async def generate_async(self, *, skill_id: str) -> GenerateCommitMessageResult:
        self.skill_ids.append(skill_id)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass
class FakeEvidenceRecorder:
    usage_evidence: tuple[ModelUsageEvidence, ...] = ()
    reset_count: int = 0

    @property
    def cost_evidence(self) -> tuple[()]:
        return ()

    def reset(self) -> None:
        self.reset_count += 1


def test_generate_commit_message_lists_files_before_loading_and_preserves_evidence_order() -> None:
    events: list[str] = []
    first = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)
    second = GitStagedFile(path="tests/test_file.py", status=GitStagedFileStatus.ADDED)
    loader = FakeStagedChangesLoader(
        staged_files=GitStagedFileList(files=(first, second)),
        diffs={
            first.path: GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n+change\n"),
            second.path: GitStagedDiff(text="diff --git a/tests/test_file.py b/tests/test_file.py\n+test\n"),
        },
        events=events,
    )
    analyzer = FakeAnalyzer(events=events)
    synthesizer = FakeSynthesizer(events=events)

    result = GenerateCommitMessage(
        staged_changes_loader=loader,
        analyzer=analyzer,
        synthesizer=synthesizer,
        query_executor=RecordingQueryExecutor(),
    ).generate(skill_id="team-commit-style")

    assert events == [
        "list_files",
        "load_file_diff:tests/test_file.py",
        "analyze:tests/test_file.py",
        "load_file_diff:src/file.py",
        "analyze:src/file.py",
        "synthesize",
    ]
    assert [call.staged_file.path for call in analyzer.calls] == ["tests/test_file.py", "src/file.py"]
    assert [item.staged_file.path for item in result.evidence_bundle.evidence] == ["src/file.py", "tests/test_file.py"]
    assert synthesizer.calls[0].skill_id == "team-commit-style"
    assert result.recommendation.commit_message == (
        "feat(developer-workflow): generate commit messages from per-file evidence"
    )


def test_commit_message_workflow_maps_success_and_resets_evidence() -> None:
    recommendation = CommitMessageRecommendation(
        summary="Adds CLI architecture cleanup.",
        rationale="The workflow owns result mapping in the application layer.",
        commit_message="refactor(cli): clean up architecture",
    )
    generator = FakeCommitMessageGenerator(_result_for(recommendation))
    recorder = FakeEvidenceRecorder()

    result = CommitMessageWorkflow(generator=generator, evidence_recorder=recorder).run(
        GenerateCommitMessageCommand(skill_id="team-style"),
    )

    assert result == CommitMessageWorkflowResult(
        status=DeveloperWorkflowStatus.SUCCESS,
        recommendation=recommendation,
    )
    assert generator.skill_ids == ["team-style"]
    assert recorder.reset_count == 1


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_category"),
    [
        (
            GitStagedChangesLoadError("no staged changes", category=GitStagedChangesFailureCategory.NO_STAGED_CHANGES),
            DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            GitStagedChangesFailureCategory.NO_STAGED_CHANGES,
        ),
        (
            CommitMessageSkillContextLoadError("skill missing", category="skill_not_found"),
            DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            "skill_not_found",
        ),
        (
            GenerateCommitMessageError("bad input", metadata={"evidence_count": 0}),
            DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            "invalid_commit_message_input",
        ),
        (
            CommitMessageSynthesisError("model failed", metadata={"phase": "synthesis"}),
            DeveloperWorkflowStatus.MODEL_ERROR,
            "commit_message_model_failure",
        ),
    ],
)
def test_commit_message_workflow_maps_application_errors_to_results(
    error: Exception,
    expected_status: DeveloperWorkflowStatus,
    expected_category: object,
) -> None:
    result = CommitMessageWorkflow(generator=FakeCommitMessageGenerator(error)).run(skill_id="team-style")

    assert result.status is expected_status
    assert result.output_text is None
    assert result.observations[0].message == str(error)
    assert result.observations[0].metadata["category"] == expected_category


def test_generate_commit_message_uses_default_bounded_parallel_analysis_and_ordered_results() -> None:
    events: list[str] = []
    first = GitStagedFile(path="src/first.py", status=GitStagedFileStatus.MODIFIED)
    second = GitStagedFile(path="src/second.py", status=GitStagedFileStatus.MODIFIED)
    loader = FakeStagedChangesLoader(
        staged_files=GitStagedFileList(files=(first, second)),
        diffs={
            first.path: GitStagedDiff(text="diff --git a/src/first.py b/src/first.py\n+first\n"),
            second.path: GitStagedDiff(text="diff --git a/src/second.py b/src/second.py\n+second\n"),
        },
        events=events,
    )
    query_executor = RecordingQueryExecutor()

    result = GenerateCommitMessage(
        staged_changes_loader=loader,
        analyzer=FakeAnalyzer(events=events),
        synthesizer=FakeSynthesizer(events=events),
        query_executor=query_executor,
    ).generate()

    assert query_executor.max_concurrency_values == [4]
    assert query_executor.execution_order == [1, 0]
    assert [item.staged_file.path for item in result.evidence_bundle.evidence] == [
        "src/first.py",
        "src/second.py",
    ]


def test_generate_commit_message_uses_configured_bounded_parallel_analysis() -> None:
    events: list[str] = []
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)
    query_executor = RecordingQueryExecutor()

    GenerateCommitMessage(
        staged_changes_loader=_loader_for(staged_file, events=events),
        analyzer=FakeAnalyzer(events=events),
        synthesizer=FakeSynthesizer(events=events),
        query_executor=query_executor,
        options=GenerateCommitMessageOptions(max_parallel_analysis=2),
    ).generate()

    assert query_executor.max_concurrency_values == [2]


def test_generate_commit_message_fails_before_analysis_when_staged_file_bound_is_exceeded() -> None:
    events: list[str] = []
    files = tuple(GitStagedFile(path=f"file_{index}.py", status=GitStagedFileStatus.MODIFIED) for index in range(3))
    loader = FakeStagedChangesLoader(staged_files=GitStagedFileList(files=files), diffs={}, events=events)
    analyzer = FakeAnalyzer(events=events)
    synthesizer = FakeSynthesizer(events=events)

    with pytest.raises(GenerateCommitMessageError, match="too many staged files") as error_info:
        GenerateCommitMessage(
            staged_changes_loader=loader,
            analyzer=analyzer,
            synthesizer=synthesizer,
            query_executor=RecordingQueryExecutor(),
            options=GenerateCommitMessageOptions(max_staged_files=2),
        ).generate()

    assert error_info.value.metadata == {"staged_file_count": 3, "max_staged_files": 2}
    assert events == ["list_files"]
    assert analyzer.calls == []
    assert synthesizer.calls == []


def test_generate_commit_message_stops_before_synthesis_when_file_diff_loading_fails() -> None:
    events: list[str] = []
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)
    loader = FakeStagedChangesLoader(
        staged_files=GitStagedFileList(files=(staged_file,)),
        diffs={},
        diff_error_by_path={
            staged_file.path: GitStagedChangesLoadError(
                "git failed",
                category=GitStagedChangesFailureCategory.GIT_FAILED,
                metadata={"category": "git_failed"},
            )
        },
        events=events,
    )
    synthesizer = FakeSynthesizer(events=events)

    with pytest.raises(GitStagedChangesLoadError) as error_info:
        GenerateCommitMessage(
            staged_changes_loader=loader,
            analyzer=FakeAnalyzer(events=events),
            synthesizer=synthesizer,
            query_executor=RecordingQueryExecutor(),
        ).generate()

    assert error_info.value.metadata == {"category": "git_failed", "path": "src/file.py"}
    assert events == ["list_files", "load_file_diff:src/file.py"]
    assert synthesizer.calls == []


def test_generate_commit_message_stops_before_synthesis_when_analysis_fails() -> None:
    events: list[str] = []
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)
    loader = _loader_for(staged_file, events=events)
    analyzer = FakeAnalyzer(
        events=events,
        error_by_path={
            staged_file.path: CommitMessageAnalysisError("analysis failed", metadata={"path": staged_file.path})
        },
    )
    synthesizer = FakeSynthesizer(events=events)

    with pytest.raises(CommitMessageAnalysisError):
        GenerateCommitMessage(
            staged_changes_loader=loader,
            analyzer=analyzer,
            synthesizer=synthesizer,
            query_executor=RecordingQueryExecutor(),
        ).generate()

    assert events == ["list_files", "load_file_diff:src/file.py", "analyze:src/file.py"]
    assert synthesizer.calls == []


def test_generate_commit_message_translates_invalid_evidence_bundle_before_synthesis() -> None:
    events: list[str] = []
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)
    loader = _loader_for(staged_file, events=events)
    analyzer = FakeAnalyzer(events=events, summary_by_path={staged_file.path: "x" * 60_000})
    synthesizer = FakeSynthesizer(events=events)

    with pytest.raises(GenerateCommitMessageError, match="evidence is invalid") as error_info:
        GenerateCommitMessage(
            staged_changes_loader=loader,
            analyzer=analyzer,
            synthesizer=synthesizer,
            query_executor=RecordingQueryExecutor(),
        ).generate()

    assert error_info.value.metadata == {"evidence_count": 1}
    assert events == ["list_files", "load_file_diff:src/file.py", "analyze:src/file.py"]
    assert synthesizer.calls == []


def test_generate_commit_message_propagates_synthesis_failure_after_complete_evidence() -> None:
    events: list[str] = []
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)
    loader = _loader_for(staged_file, events=events)
    synthesizer = FakeSynthesizer(events=events, error=CommitMessageSynthesisError("synthesis failed"))

    with pytest.raises(CommitMessageSynthesisError):
        GenerateCommitMessage(
            staged_changes_loader=loader,
            analyzer=FakeAnalyzer(events=events),
            synthesizer=synthesizer,
            query_executor=RecordingQueryExecutor(),
        ).generate()

    assert events == ["list_files", "load_file_diff:src/file.py", "analyze:src/file.py", "synthesize"]
    assert len(synthesizer.calls[0].evidence_bundle.evidence) == 1


def _loader_for(staged_file: GitStagedFile, *, events: list[str]) -> FakeStagedChangesLoader:
    return FakeStagedChangesLoader(
        staged_files=GitStagedFileList(files=(staged_file,)),
        diffs={staged_file.path: GitStagedDiff(text=f"diff --git a/{staged_file.path} b/{staged_file.path}\n")},
        events=events,
    )


def _result_for(recommendation: CommitMessageRecommendation) -> GenerateCommitMessageResult:
    evidence = _evidence(
        GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED),
        summary="Adds CLI architecture cleanup.",
    )
    return GenerateCommitMessageResult(
        recommendation=recommendation,
        evidence_bundle=CommitMessageEvidenceBundle(evidence=(evidence,)),
    )


def _evidence(staged_file: GitStagedFile, *, summary: str) -> StagedFileCommitEvidence:
    return StagedFileCommitEvidence(
        staged_file=staged_file,
        summary=summary,
        category="architecture",
        public_contract_impact="Application use case boundary changes.",
        validation_relevance="Unit tests cover orchestration behavior.",
        migration_concern="No migration needed.",
        breaking_risk="No breaking risk identified.",
    )

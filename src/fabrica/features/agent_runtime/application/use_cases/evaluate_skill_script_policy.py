"""Use case for evaluating selected Agent Skill script execution policy."""

from fabrica.features.agent_runtime.application.dtos import (
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalStatus,
    SkillScriptMetadata,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyEvaluationResult,
    SkillScriptPolicyObservation,
    SkillScriptPolicyStatus,
    SkillScriptSandboxPolicy,
    skill_script_type_for_suffix,
)
from fabrica.features.agent_runtime.application.ports import (
    SkillScriptApprovalLookup,
    SkillScriptMetadataLoader,
    SkillScriptMetadataLoadError,
)


class EvaluateSkillScriptPolicy:
    """Evaluate selected script metadata against approval and sandbox policy."""

    def __init__(
        self,
        metadata_loader: SkillScriptMetadataLoader,
        approval_lookup: SkillScriptApprovalLookup,
    ) -> None:
        self._metadata_loader = metadata_loader
        self._approval_lookup = approval_lookup

    def evaluate(self, command: SkillScriptPolicyEvaluationCommand) -> SkillScriptPolicyEvaluationResult:
        """Return whether the selected script is allowed by declarative policy."""
        try:
            script_metadata = self._metadata_loader.load_metadata(command.selection)
        except SkillScriptMetadataLoadError as err:
            return SkillScriptPolicyEvaluationResult(
                status=SkillScriptPolicyStatus.METADATA_ERROR,
                selection=command.selection,
                observations=(
                    self._observation(
                        "selected script metadata could not be loaded",
                        command.selection,
                        category=err.category,
                    ),
                ),
            )

        metadata_error = self._metadata_error(command.selection, script_metadata)
        if metadata_error is not None:
            return SkillScriptPolicyEvaluationResult(
                status=SkillScriptPolicyStatus.METADATA_ERROR,
                selection=command.selection,
                binding=script_metadata.binding,
                observations=(metadata_error,),
            )

        policy_violation = self._policy_violation(command.selection, script_metadata.binding, command.sandbox_policy)
        if policy_violation is not None:
            return SkillScriptPolicyEvaluationResult(
                status=SkillScriptPolicyStatus.POLICY_VIOLATION,
                selection=command.selection,
                binding=script_metadata.binding,
                observations=(policy_violation,),
            )

        approval = self._approval_lookup.get_approval(script_metadata.binding)
        if approval.status is not SkillScriptApprovalStatus.APPROVED:
            return SkillScriptPolicyEvaluationResult(
                status=SkillScriptPolicyStatus.DENIED,
                selection=command.selection,
                binding=script_metadata.binding,
                observations=(
                    self._observation(
                        "selected script approval is not approved",
                        command.selection,
                        category="approval_not_approved",
                        approval_status=approval.status.value,
                    ),
                ),
            )

        if approval.binding != script_metadata.binding:
            return SkillScriptPolicyEvaluationResult(
                status=SkillScriptPolicyStatus.DENIED,
                selection=command.selection,
                binding=script_metadata.binding,
                observations=(
                    self._observation(
                        "selected script approval binding does not match metadata",
                        command.selection,
                        category="approval_binding_mismatch",
                    ),
                ),
            )

        return SkillScriptPolicyEvaluationResult(
            status=SkillScriptPolicyStatus.APPROVED,
            selection=command.selection,
            binding=script_metadata.binding,
            observations=(
                self._observation(
                    "selected script policy approved",
                    command.selection,
                    category="policy_approved",
                ),
            ),
        )

    def _metadata_error(
        self,
        selection: SelectedSkillScript,
        script_metadata: SkillScriptMetadata,
    ) -> SkillScriptPolicyObservation | None:
        if script_metadata.selection != selection:
            return self._observation(
                "selected script metadata does not match request",
                selection,
                category="metadata_selection_mismatch",
            )

        suffix_script_type = skill_script_type_for_suffix(script_metadata.binding.suffix)
        if suffix_script_type is None:
            return self._observation(
                "selected script suffix is not supported",
                selection,
                category="unsupported_script_suffix",
            )
        if suffix_script_type is not script_metadata.binding.script_type:
            return self._observation(
                "selected script metadata type does not match suffix",
                selection,
                category="metadata_script_type_mismatch",
                script_type=script_metadata.binding.script_type.value,
            )
        return None

    def _policy_violation(
        self,
        selection: SelectedSkillScript,
        binding: SkillScriptApprovalBinding,
        sandbox_policy: SkillScriptSandboxPolicy,
    ) -> SkillScriptPolicyObservation | None:
        if binding.byte_size > sandbox_policy.max_script_bytes:
            return self._observation(
                "selected script exceeds sandbox byte-size policy",
                selection,
                category="script_size_exceeds_policy",
                byte_size=binding.byte_size,
                max_script_bytes=sandbox_policy.max_script_bytes,
            )
        if sandbox_policy.allow_network:
            return self._observation(
                "selected script policy requests unsupported network access",
                selection,
                category="network_access_not_supported",
            )
        if sandbox_policy.writable_path_labels:
            return self._observation(
                "selected script policy requests unsupported writable paths",
                selection,
                category="writable_paths_not_supported",
                writable_path_count=len(sandbox_policy.writable_path_labels),
            )
        if sandbox_policy.environment_allowlist:
            return self._observation(
                "selected script policy requests unsupported environment access",
                selection,
                category="environment_access_not_supported",
                environment_name_count=len(sandbox_policy.environment_allowlist),
            )
        return None

    @staticmethod
    def _observation(
        message: str,
        selection: SelectedSkillScript,
        **metadata: str | float | bool | None,
    ) -> SkillScriptPolicyObservation:
        return SkillScriptPolicyObservation(
            message=message,
            metadata={
                "skill_id": selection.skill_id,
                "script_id": selection.script_id,
                **metadata,
            },
        )

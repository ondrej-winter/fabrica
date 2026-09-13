"""Bootstrap-owned handler for reporting-only mature-agent evaluation."""

from fabrica.adapters.inbound.cli.command import CommandContext
from fabrica.adapters.inbound.cli.rendering import write_line
from fabrica.features.agent_evaluation.adapters.inbound.cli import AgentEvaluationCliHandler, CliEvaluationCommand
from fabrica.features.agent_evaluation.application import EvaluateMatureAgentCorpus, EvaluationReportWriter
from fabrica.features.agent_evaluation.application.fixtures import mature_agent_corpus


def run_agent_evaluation_command(report_writer: EvaluationReportWriter) -> AgentEvaluationCliHandler:
    """Compose the fixed offline corpus with a report writer at the CLI boundary."""

    def run(command: CliEvaluationCommand, context: CommandContext) -> int:
        report = EvaluateMatureAgentCorpus(mature_agent_corpus()).execute()
        destination = report_writer.write(report, command.destination)
        write_line(context.stdout, f"Mature-agent evaluation: {'passed' if report.passed else 'failed'}")
        write_line(context.stdout, f"Scenarios: {len(report.results)}")
        write_line(context.stdout, f"Report: {destination}")
        return 0 if report.passed else 1

    return run

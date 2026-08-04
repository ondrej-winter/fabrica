from dataclasses import dataclass
from pathlib import Path

DEFAULT_OUTPUT_PATH = Path('.local-data/output.sqlite3')
DEFAULT_SERVICE_URL = 'https://service.example.test'


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Application-owned runtime settings."""

    required_secret: str
    service_url: str = DEFAULT_SERVICE_URL
    output_path: Path = DEFAULT_OUTPUT_PATH

"""Vulture whitelist -- items that appear unused but are part of the public API
or required by framework signatures."""

# pydantic-settings requires these parameters in settings_customise_sources
dotenv_settings  # type: ignore[name-defined]
file_secret_settings  # type: ignore[name-defined]

# Public API parameters that are part of the interface contract but not
# directly used in the current implementation
preceding_context  # type: ignore[name-defined]
document_id  # type: ignore[name-defined]
chunk_boundaries  # type: ignore[name-defined]

import json
from pathlib import Path
from typing import Any

import polars as pl


class SerializationFormat(Enum):
    PARQUET = "parquet"
    JSON = "json"
    PICKLE = "pickle"
    YAML = "yaml"
    CSV = "csv"


class DataSerializer:
    def __init__(self, compression: str | None = None):
        self.compression = compression  # 'gzip', 'lz4', or None
        self._serializers = {
            SerializationFormat.PARQUET: self._serialize_parquet,
            SerializationFormat.JSON: self._serialize_json,
            SerializationFormat.PICKLE: self._serialize_pickle,
            SerializationFormat.YAML: self._serialize_yaml,
            SerializationFormat.CSV: self._serialize_csv,
        }

    def save(
        self,
        data: pl.DataFrame | dict | List,
        filepath: str | Path,
        format: SerializationFormat = SerializationFormat.PARQUET,
    ) -> None:
        """Save data in specified format with optional compression"""
        filepath = Path(filepath)

        # Serialize data
        serialized = self._serializers[format](data)

        # Apply compression if requested
        if self.compression:
            serialized = self._compress(serialized, self.compression)
            filepath = filepath.with_suffix(filepath.suffix + f".{self.compression}")

        # Write to file
        self._write_file(filepath, serialized, format)

    def load(self, filepath: str | Path, format: SerializationFormat | None = None) -> Any:
        """Load data with automatic format detection"""
        filepath = Path(filepath)

        # Detect format if not specified
        if format is None:
            format = self._detect_format(filepath)

        # Read file
        data = self._read_file(filepath, format)

        # Decompress if needed
        if self._is_compressed(filepath):
            data = self._decompress(data, filepath.suffix.strip("."))

        # Deserialize
        return self._deserialize(data, format)

    def convert(
        self, input_path: str | Path, output_path: str | Path, output_format: SerializationFormat
    ) -> None:
        """Convert between formats"""
        data = self.load(input_path)
        self.save(data, output_path, output_format)

    def _serialize_parquet(self, data: pl.DataFrame) -> bytes:
        """Serialize DataFrame to Parquet bytes"""
        return data.write_parquet(None)

    def _serialize_json(self, data: Any) -> str:
        """Serialize to JSON with custom encoders"""
        return json.dumps(data, default=self._json_encoder, indent=2)

    def _json_encoder(self, obj):
        """Custom JSON encoder for complex types"""
        if isinstance(obj, pl.DataFrame):
            return obj.to_dicts()
        elif hasattr(obj, "to_dict"):
            return obj.to_dict()
        else:
            return str(obj)

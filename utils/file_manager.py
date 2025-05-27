"""File management utilities for StudioAssist PoC."""

import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Union, Dict, List, Optional

from constants import MAX_FILES_TO_KEEP  # Changed from ..constants

logger = logging.getLogger(__name__)

class FeatureFileManager:
    """Handles file operations with feature-specific organization."""
    
    def __init__(self, data_dir: str, feature: str):
        self.data_dir = Path(data_dir)
        self.feature = feature
        self.feature_dir = self.data_dir / feature
        self.feature_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_filename(self, data_type: str, llm_version: str = "", extension: str = "json") -> Path:
        """Generate feature-specific filename with timestamp and UUID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        components = ["studioassist", self.feature, data_type]
        if llm_version:
            components.append(llm_version)
        components.extend([timestamp, unique_id])
        
        filename = f"{'_'.join(components)}.{extension}"
        return self.feature_dir / filename
    
    def get_latest_file(self, pattern: str) -> Optional[Path]:
        """Get the most recent file matching the pattern."""
        files = list(self.feature_dir.glob(pattern))
        if not files:
            return None
        return max(files, key=lambda x: x.stat().st_mtime)
    
    def save_json(self, data: Union[Dict, List], filename: Path) -> None:
        """Save data to JSON file with error handling."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Data saved to {filename}")
        except (IOError, TypeError) as e:
            logger.error(f"Failed to save data to {filename}: {e}")
            raise
    
    def load_json(self, filename: Union[str, Path]) -> Union[Dict, List]:
        """Load JSON data from file."""
        # Handle absolute paths and relative paths properly
        if isinstance(filename, str):
            filepath = Path(filename)
            if not filepath.is_absolute():
                # Only prepend feature_dir if it's not already in the path
                if self.feature not in str(filepath):
                    filepath = self.feature_dir / filepath
        else:
            filepath = filename
        
        try:
            logger.debug(f"Loading JSON from: {filepath}")
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filepath}: {e}")
            raise
    
    def cleanup_old_files(self, data_type: str = "*") -> None:
        """Remove old files for specific feature and data type."""
        pattern = f"studioassist_{self.feature}_{data_type}_*.json"
        files = sorted(self.feature_dir.glob(pattern), key=lambda x: x.stat().st_mtime)
        if len(files) > MAX_FILES_TO_KEEP:
            for old_file in files[:-MAX_FILES_TO_KEEP]:
                try:
                    old_file.unlink()
                    logger.info(f"Cleaned up old file: {old_file}")
                except OSError as e:
                    logger.warning(f"Could not remove {old_file}: {e}")
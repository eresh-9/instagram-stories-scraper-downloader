thonimport json
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def export_stories_to_json(
    stories: List[Dict[str, Any]],
    output_path: str,
    pretty: bool = False,
) -> None:
    """
    Write normalized stories to a JSON file at output_path. Any missing
    directories will be created automatically.
    """
    directory = os.path.dirname(output_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.debug("Created output directory %s", directory)

    options = {"ensure_ascii": False}
    if pretty:
        options["indent"] = 2
        options["sort_keys"] = True

    tmp_path = f"{output_path}.tmp"

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(stories, f, **options)
        os.replace(tmp_path, output_path)
        logger.info("Exported %d stories to %s", len(stories), output_path)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to export stories to %s: %s", output_path, exc)
        # Clean up temporary file if something went wrong
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
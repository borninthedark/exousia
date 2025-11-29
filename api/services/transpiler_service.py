"""
Transpiler Service
==================

Service for YAML validation and Containerfile generation.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any
import yaml

from ..config import settings


class TranspilerService:
    """Service for transpiling YAML configs to Containerfiles."""

    def __init__(self):
        self.transpiler_script = settings.TRANSPILER_SCRIPT

    async def validate(self, yaml_content: str) -> Dict[str, Any]:
        """
        Validate YAML configuration.

        Returns:
            Dictionary with 'valid' (bool), 'errors' (list), and 'warnings' (list)
        """
        errors = []
        warnings = []

        # Parse YAML
        try:
            config = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return {
                "valid": False,
                "errors": [f"YAML syntax error: {str(e)}"],
                "warnings": []
            }

        # Basic schema validation
        required_fields = ["name", "description", "modules"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Validate modules
        if "modules" in config:
            if not isinstance(config["modules"], list):
                errors.append("'modules' must be a list")
            else:
                for idx, module in enumerate(config["modules"]):
                    if not isinstance(module, dict):
                        errors.append(f"Module {idx} must be a dictionary")
                        continue

                    if "type" not in module:
                        errors.append(f"Module {idx} missing 'type' field")

        # Use transpiler script for validation if no parse errors
        if not errors:
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
                    f.write(yaml_content)
                    temp_file = f.name

                process = await asyncio.create_subprocess_exec(
                    "python3",
                    str(self.transpiler_script),
                    "--config", temp_file,
                    "--validate",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                _, stderr = await process.communicate()

                # Clean up temp file
                Path(temp_file).unlink()

                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Validation failed"
                    errors.append(error_msg)

            except (OSError, asyncio.TimeoutError) as e:
                errors.append(f"Validation error: {str(e)}")

        return {
            "valid": len(errors) == 0,
            "errors": errors if errors else None,
            "warnings": warnings if warnings else None
        }

    async def transpile(
        self,
        yaml_content: str,
        image_type: str,
        fedora_version: str,
        enable_plymouth: bool
    ) -> str:
        """
        Transpile YAML configuration to Containerfile.

        Args:
            yaml_content: YAML configuration content
            image_type: Base image type (fedora-bootc or fedora-sway-atomic)
            fedora_version: Fedora version number
            enable_plymouth: Whether to enable Plymouth

        Returns:
            Generated Containerfile content

        Raises:
            Exception: If transpilation fails
        """
        # Create temporary file for YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            yaml_file = f.name

        try:
            # Build command args
            args = [
                "python3",
                str(self.transpiler_script),
                "--config", yaml_file,
                "--image-type", image_type,
                "--fedora-version", fedora_version,
            ]

            if enable_plymouth:
                args.append("--enable-plymouth")
            else:
                args.append("--disable-plymouth")

            # Run transpiler
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Transpilation failed"
                raise RuntimeError(error_msg)

            return stdout.decode()

        finally:
            # Clean up temp file
            Path(yaml_file).unlink(missing_ok=True)

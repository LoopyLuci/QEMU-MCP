"""Docker Compose stack management.

Provides deploy and remove operations for Docker Compose stacks,
supporting both v2 (``docker compose``) and v1 (``docker-compose``) CLI.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ComposeError(Exception):
    """Base exception for Compose operations."""
    pass


class DockerCompose:
    """Manage Docker Compose stacks via the Docker CLI.

    This class provides high-level operations for deploying and removing
    Docker Compose stacks, abstracting away CLI version differences.
    """

    def __init__(
        self,
        compose_cmd: str = "docker compose",
        working_dir: Optional[Union[str, Path]] = None,
        env_file: Optional[Union[str, Path]] = None,
    ):
        """
        Args:
            compose_cmd: Docker Compose command (default: 'docker compose').
                         Falls back to 'docker-compose' if v2 unavailable.
            working_dir: Default working directory for compose operations.
            env_file: Path to .env file for compose.
        """
        self._compose_cmd = compose_cmd
        self._working_dir = Path(working_dir) if working_dir else None
        self._env_file = Path(env_file) if env_file else None
        self._available_cmd: Optional[str] = None

    async def _detect_compose_cmd(self) -> str:
        """Detect available docker compose command."""
        if self._available_cmd:
            return self._available_cmd

        for cmd in ["docker compose", "docker-compose"]:
            try:
                proc = await asyncio.create_subprocess_shell(
                    f"{cmd} --version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.wait()
                if proc.returncode == 0:
                    self._available_cmd = cmd
                    return cmd
            except Exception:
                continue

        raise ComposeError(
            "Docker Compose not found. Install Docker Compose v2 or v1."
        )

    def _build_env(
        self,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Build environment dict for subprocess, merging system + custom vars."""
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        return env

    async def deploy(
        self,
        compose_content: Optional[str] = None,
        compose_file: Optional[Union[str, Path]] = None,
        project_name: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        build: bool = False,
        remove_orphans: bool = False,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Deploy a Docker Compose stack.

        Args:
            compose_content: Inline compose YAML content.
            compose_file: Path to docker-compose.yml file.
            project_name: Project name (defaults to directory name).
            working_dir: Working directory (overrides constructor).
            env_vars: Additional environment variables.
            build: Build images before starting.
            remove_orphans: Remove containers not defined in compose.
            timeout: Command timeout in seconds.

        Returns:
            Dict with 'success', 'stdout', 'stderr' keys.

        Raises:
            ComposeError: If deploy fails.
        """
        cmd = await self._detect_compose_cmd()
        work_dir = Path(working_dir) if working_dir else self._working_dir
        env = self._build_env(env_vars)

        # Write compose content to temp file if provided
        temp_file = None
        try:
            if compose_content:
                temp_file = tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".yml",
                    prefix="compose_",
                    dir=work_dir,
                    delete=False,
                )
                temp_file.write(compose_content)
                temp_file.close()
                compose_file = temp_file.name

            if not compose_file:
                raise ComposeError("Either compose_content or compose_file must be provided")

            # Build command
            args = [cmd]
            if project_name:
                args.extend(["-p", project_name])
            if self._env_file:
                args.extend(["--env-file", str(self._env_file)])
            args.extend(["-f", str(compose_file), "up", "-d"])
            if build:
                args.append("--build")
            if remove_orphans:
                args.append("--remove-orphans")

            result = await self._run(args, env, work_dir, timeout)

            if result["returncode"] != 0:
                raise ComposeError(
                    f"Deploy failed: {result['stderr']}",
                )

            return result

        finally:
            if temp_file:
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    pass

    async def remove(
        self,
        compose_file: Optional[Union[str, Path]] = None,
        project_name: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        remove_volumes: bool = False,
        remove_images: bool = False,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """Remove a Docker Compose stack.

        Args:
            compose_file: Path to docker-compose.yml file.
            project_name: Project name.
            working_dir: Working directory.
            env_vars: Additional environment variables.
            remove_volumes: Remove named volumes.
            remove_images: Remove images used by services.
            timeout: Command timeout in seconds.

        Returns:
            Dict with 'success', 'stdout', 'stderr' keys.

        Raises:
            ComposeError: If remove fails.
        """
        cmd = await self._detect_compose_cmd()
        work_dir = Path(working_dir) if working_dir else self._working_dir
        env = self._build_env(env_vars)

        args = [cmd]
        if project_name:
            args.extend(["-p", project_name])
        if self._env_file:
            args.extend(["--env-file", str(self._env_file)])

        if compose_file:
            args.extend(["-f", str(compose_file)])

        args.append("down")

        if remove_volumes:
            args.append("-v")
        if remove_images:
            args.append("--rmi")
            args.append("all")

        result = await self._run(args, env, work_dir, timeout)

        if result["returncode"] != 0:
            raise ComposeError(f"Remove failed: {result['stderr']}")

        return result

    async def list_stacks(
        self,
        all: bool = True,
    ) -> List[Dict[str, Any]]:
        """List running Docker Compose stacks.

        Args:
            all: Include stopped stacks.

        Returns:
            List of stack info dicts with 'name', 'services', 'status'.
        """
        cmd = await self._detect_compose_cmd()
        args = [cmd, "ls", "--format", "json"]
        if all:
            args.append("-a")

        result = await self._run(args, os.environ.copy(), None, 30)

        if result["returncode"] != 0:
            raise ComposeError(f"Failed to list stacks: {result['stderr']}")

        try:
            output = result["stdout"].strip()
            if not output:
                return []
            # Handle both single JSON object and JSONL
            if output.startswith("["):
                return json.loads(output)
            return [json.loads(line) for line in output.splitlines() if line.strip()]
        except json.JSONDecodeError as e:
            raise ComposeError(f"Failed to parse stack list: {e}")

    async def get_services(
        self,
        compose_file: Union[str, Path],
        project_name: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
    ) -> List[Dict[str, Any]]:
        """Get services in a compose stack.

        Args:
            compose_file: Path to docker-compose.yml.
            project_name: Project name.
            working_dir: Working directory.

        Returns:
            List of service info dicts.
        """
        cmd = await self._detect_compose_cmd()
        work_dir = Path(working_dir) if working_dir else self._working_dir

        args = [cmd]
        if project_name:
            args.extend(["-p", project_name])
        args.extend(["-f", str(compose_file), "ps", "--format", "json"])

        result = await self._run(args, os.environ.copy(), work_dir, 30)

        if result["returncode"] != 0:
            raise ComposeError(f"Failed to get services: {result['stderr']}")

        try:
            output = result["stdout"].strip()
            if not output:
                return []
            if output.startswith("["):
                return json.loads(output)
            return [json.loads(line) for line in output.splitlines() if line.strip()]
        except json.JSONDecodeError as e:
            raise ComposeError(f"Failed to parse services list: {e}")

    async def restart_service(
        self,
        service: str,
        compose_file: Optional[Union[str, Path]] = None,
        project_name: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Restart a service in a compose stack.

        Args:
            service: Service name.
            compose_file: Path to docker-compose.yml.
            project_name: Project name.
            working_dir: Working directory.
            timeout: Timeout in seconds.

        Returns:
            Command result dict.
        """
        cmd = await self._detect_compose_cmd()
        work_dir = Path(working_dir) if working_dir else self._working_dir

        args = [cmd]
        if project_name:
            args.extend(["-p", project_name])
        if compose_file:
            args.extend(["-f", str(compose_file)])
        args.extend(["restart", service])

        result = await self._run(args, os.environ.copy(), work_dir, timeout)

        if result["returncode"] != 0:
            raise ComposeError(f"Failed to restart service: {result['stderr']}")

        return result

    async def scale_service(
        self,
        service: str,
        replicas: int,
        compose_file: Union[str, Path],
        project_name: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Scale a service to N replicas.

        Args:
            service: Service name.
            replicas: Number of replicas.
            compose_file: Path to docker-compose.yml.
            project_name: Project name.
            working_dir: Working directory.

        Returns:
            Command result dict.
        """
        cmd = await self._detect_compose_cmd()
        work_dir = Path(working_dir) if working_dir else self._working_dir

        args = [cmd]
        if project_name:
            args.extend(["-p", project_name])
        args.extend(["-f", str(compose_file)])
        args.extend(["up", "-d", "--scale", f"{service}={replicas}", "--no-recreate"])

        result = await self._run(args, os.environ.copy(), work_dir, 60)

        if result["returncode"] != 0:
            raise ComposeError(f"Failed to scale service: {result['stderr']}")

        return result

    async def get_logs(
        self,
        compose_file: Optional[Union[str, Path]] = None,
        project_name: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        service: Optional[str] = None,
        tail: int = 50,
        follow: bool = False,
        timestamps: bool = False,
    ) -> str:
        """Get logs from a compose stack.

        Args:
            compose_file: Path to docker-compose.yml.
            project_name: Project name.
            working_dir: Working directory.
            service: Specific service (None for all).
            tail: Number of lines.
            follow: Stream logs (not implemented, returns current).
            timestamps: Include timestamps.

        Returns:
            Log output string.
        """
        cmd = await self._detect_compose_cmd()
        work_dir = Path(working_dir) if working_dir else self._working_dir

        args = [cmd]
        if project_name:
            args.extend(["-p", project_name])
        if compose_file:
            args.extend(["-f", str(compose_file)])
        args.extend(["logs", "--tail", str(tail)])
        if timestamps:
            args.append("--timestamps")
        if not follow:
            args.append("--no-log-prefix")

        if service:
            args.append(service)

        result = await self._run(args, os.environ.copy(), work_dir, 30)

        if result["returncode"] != 0:
            raise ComposeError(f"Failed to get logs: {result['stderr']}")

        return result["stdout"]

    async def _run(
        self,
        args: List[str],
        env: Dict[str, str],
        cwd: Optional[Path],
        timeout: int,
    ) -> Dict[str, Any]:
        """Run a compose command.

        Args:
            args: Command and arguments.
            env: Environment variables.
            cwd: Working directory.
            timeout: Timeout in seconds.

        Returns:
            Dict with 'stdout', 'stderr', 'returncode' keys.
        """
        cmd_str = " ".join(args)

        proc = await asyncio.create_subprocess_shell(
            cmd_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(cwd) if cwd else None,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise ComposeError(f"Command timed out after {timeout}s: {cmd_str}")

        return {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "returncode": proc.returncode,
            "success": proc.returncode == 0,
        }

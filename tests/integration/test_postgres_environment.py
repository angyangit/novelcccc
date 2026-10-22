"""Real PostgreSQL lifecycle acceptance; a missing Docker daemon is a failure."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scripts/check_postgres.py"


def run(argv, env, *, check=True, timeout=120):
    result = subprocess.run(argv, env=env, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        pytest.fail(f"Command failed ({result.returncode}): {argv!r}\n{result.stdout}\n{result.stderr}")
    return result


def clean_environment():
    env = os.environ.copy()
    # Do not inherit production/another test's database configuration.
    for key in list(env):
        if key.startswith(("ANOVELOS_TEST_", "PG", "COMPOSE_")):
            env.pop(key)
    return env


@contextmanager
def postgres():
    env = clean_environment()
    project = "anovel-v2001-" + uuid.uuid4().hex[:16]
    env.update(ANOVELOS_TEST_DB="bootstrap_test", ANOVELOS_TEST_USER="bootstrap_test",
               ANOVELOS_TEST_PASSWORD=secrets.token_urlsafe(24))
    compose = ["docker", "compose", "--env-file", os.devnull, "-f", str(ROOT / "compose.yaml"), "-p", project]
    print(f"POSTGRES_PROJECT {project}", flush=True)

    # Detect GitLab CI DinD mode where container network access is required
    ci_dind_mode = os.getenv("CI_DIND_MODE") == "true"

    try:
        if ci_dind_mode:
            # GitLab DinD: Resolve docker service IP and bind postgres to it
            # This allows job container to access published port on docker service interface
            docker_ip_result = run(["getent", "hosts", "docker"], env)
            docker_ip = docker_ip_result.stdout.strip().split()[0]

            if not docker_ip:
                pytest.fail("CI_DIND_MODE: Could not resolve docker service IP")

            print(f"CI_DIND_MODE: Docker service IP: {docker_ip}", flush=True)
            env["ANOVELOS_POSTGRES_BIND_IP"] = docker_ip

        run(compose + ["up", "-d", "--wait", "--wait-timeout", "60"], env)

        if ci_dind_mode:
            # Get published endpoint - handles both IPv4 and IPv6
            endpoint = run(compose + ["port", "postgres", "5432"], env).stdout.strip()

            # Extract port correctly for IPv6 [::1]:port or IPv4 127.0.0.1:port
            port_str = endpoint.split(":")[-1]

            # Validate port
            if not port_str.isdigit():
                pytest.fail(f"CI_DIND_MODE: Invalid port '{port_str}' from endpoint '{endpoint}'")

            port = int(port_str)
            if port < 1 or port > 65535:
                pytest.fail(f"CI_DIND_MODE: Port {port} out of valid range")

            # Use docker service IP as host (same IP we bound to)
            host = docker_ip

            print(f"CI_DIND_MODE: Published endpoint: {endpoint}", flush=True)
            print(f"CI_DIND_MODE: Connecting to: {host}:{port}", flush=True)
        else:
            # Local development: Use port mapping to 127.0.0.1 (original behavior)
            endpoint = run(compose + ["port", "postgres", "5432"], env).stdout.strip()
            host, port = endpoint.rsplit(":", 1)
            assert host == "127.0.0.1", f"Expected 127.0.0.1, got {host} - check compose.yaml host_ip binding"
            print(f"Local mode: Using port mapping: {host}:{port}", flush=True)

        dsn = URL.create("postgresql+psycopg", username=env["ANOVELOS_TEST_USER"],
                         password=env["ANOVELOS_TEST_PASSWORD"], host=host, port=int(port),
                         database=env["ANOVELOS_TEST_DB"]).render_as_string(hide_password=False)
        env["ANOVELOS_TEST_DSN"] = dsn
        yield env, project
    finally:
        # This finally covers startup/health/port failures as well as test failures.
        run(compose + ["down", "--volumes", "--remove-orphans", "--timeout", "10"], env)
        label = "label=com.docker.compose.project=" + project
        for kind, args in [("container", ["ps", "-aq"]), ("network", ["network", "ls", "-q"]), ("volume", ["volume", "ls", "-q"])]:
            residual = run(["docker"] + args + ["--filter", label], env).stdout.strip()
            assert not residual, f"Residual {kind} for {project}: {residual}"
        print(f"POSTGRES_CLEANUP {project} containers=0 networks=0 volumes=0", flush=True)


def test_postgres_start_connect_and_cleanup():
    with postgres() as (env, project):
        result = run([sys.executable, str(PROBE)], env)
        actual = json.loads(result.stdout)
        assert actual == {"database": "bootstrap_test", "server_version_num": 170011, "driver": "postgresql+psycopg"}
        engine = create_engine(env["ANOVELOS_TEST_DSN"])
        try:
            with engine.connect() as first, engine.connect() as second:
                assert first.execute(text("SELECT pg_backend_pid()")).scalar_one() != second.execute(text("SELECT pg_backend_pid()")).scalar_one()
                assert first.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar_one() == 0
        finally:
            engine.dispose()
        print(f"POSTGRES_CONNECTED {project} {result.stdout.strip()}", flush=True)


def test_postgres_cleanup_after_interrupted_test():
    # A real container is removed even when the consumer raises before completion.
    with pytest.raises(RuntimeError, match="injected consumer failure"):
        with postgres():
            raise RuntimeError("injected consumer failure")


@pytest.mark.parametrize("dsn", [None, "", "sqlite:///:memory:", "postgresql://user:password@127.0.0.1:1234/db", "postgresql+psycopg://user@localhost/db", "not-a-url"])
def test_missing_or_invalid_configuration_fails(dsn):
    env = clean_environment()
    if dsn is not None:
        env["ANOVELOS_TEST_DSN"] = dsn
    result = run([sys.executable, str(PROBE)], env, check=False)
    assert result.returncode == 2
    assert "ANOVELOS_TEST_DSN" in result.stderr
    assert not result.stdout
    assert "Traceback" not in result.stderr


def test_unreachable_database_fails_without_disclosing_password():
    env = clean_environment()
    # Bound but non-listening port cannot belong to another PostgreSQL process.
    with socket.socket() as blocked:
        blocked.bind(("127.0.0.1", 0))
        env["ANOVELOS_TEST_DSN"] = f"postgresql+psycopg://test:disposable_probe_password@127.0.0.1:{blocked.getsockname()[1]}/test"
        result = run([sys.executable, str(PROBE)], env, check=False, timeout=15)
    assert result.returncode == 1
    assert "connection/query failed" in result.stderr
    assert "disposable_probe_password" not in result.stderr + result.stdout


def test_compose_requires_explicit_configuration():
    env = clean_environment()
    result = run(["docker", "compose", "--env-file", os.devnull, "-f", str(ROOT / "compose.yaml"), "config", "--quiet"], env, check=False)
    assert result.returncode != 0
    assert "ANOVELOS_TEST_" in result.stderr

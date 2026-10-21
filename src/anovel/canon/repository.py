"""CanonRepository minimal persistence interface.

Provides database connection management, transaction control, and
idempotent commit operations for Canon persistence.

This is the minimal repository interface for V2-009. Complete
CanonCommitService business logic is deferred to V2-010.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker


class CanonRepositoryError(Exception):
    """Base exception for Canon repository errors."""

    pass


class ProjectScopeViolationError(CanonRepositoryError):
    """Raised when attempting cross-project operations."""

    pass


class RootCommitExistsError(CanonRepositoryError):
    """Raised when attempting to create duplicate root commit."""

    pass


class IdempotencyConflictError(CanonRepositoryError):
    """Raised when idempotency key conflict detected."""

    pass


class CASUpdateFailedError(CanonRepositoryError):
    """Raised when CAS update fails due to concurrent modification."""

    pass


class ExecutionVersionMismatchError(CanonRepositoryError):
    """Raised when execution version does not match."""

    pass


class CanonRepository:
    """Minimal Canon persistence repository.

    Manages database connections, transactions, and basic CRUD operations
    for Canon commits, events, and execution control.

    Thread-safety: Each repository instance is not thread-safe. Create
    separate instances per thread or use connection pooling appropriately.
    """

    def __init__(self, database_url: str, echo: bool = False):
        """Initialize repository with database connection.

        Args:
            database_url: SQLAlchemy database URL
            echo: If True, log all SQL statements
        """
        self.engine: Engine = create_engine(database_url, echo=echo, pool_pre_ping=True)
        self.session_factory = sessionmaker(bind=self.engine)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Provide transactional context with automatic rollback on error.

        Yields:
            SQLAlchemy session with active transaction

        Example:
            with repo.transaction() as session:
                repo.create_project(session, "project1")
                # Automatically commits on success, rolls back on exception
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_project(self, session: Session, project_id: str) -> None:
        """Create a new project scope boundary.

        Args:
            session: Active database session
            project_id: Unique project identifier

        Raises:
            IdempotencyConflictError: If project already exists
        """
        try:
            session.execute(
                text("INSERT INTO project (project_id) VALUES (:project_id)"),
                {"project_id": project_id},
            )
        except IntegrityError as e:
            raise IdempotencyConflictError(
                f"Project {project_id} already exists"
            ) from e

    def create_root_commit(
        self,
        session: Session,
        project_id: str,
        branch_name: str,
        commit_id: str,
        idempotency_key: str,
        payload_hash: str,
        changeset: dict[str, Any],
        permit_ref: str | None = None,
    ) -> None:
        """Create root commit (parent_commit_id IS NULL) for project/branch.

        Args:
            session: Active database session
            project_id: Project scope identifier
            branch_name: Branch name within project
            commit_id: Unique commit identifier
            idempotency_key: Idempotency key for retry safety
            payload_hash: Content hash of commit payload
            changeset: Commit changeset data
            permit_ref: Optional execution permit reference

        Raises:
            RootCommitExistsError: If root commit already exists for project/branch
            IdempotencyConflictError: If idempotency key conflict detected
        """
        try:
            session.execute(
                text("""
                    INSERT INTO canon_commit
                    (project_id, branch_name, commit_id, parent_commit_id,
                     idempotency_key, payload_hash, changeset, permit_ref)
                    VALUES (:project_id, :branch_name, :commit_id, NULL,
                            :idempotency_key, :payload_hash, :changeset, :permit_ref)
                """),
                {
                    "project_id": project_id,
                    "branch_name": branch_name,
                    "commit_id": commit_id,
                    "idempotency_key": idempotency_key,
                    "payload_hash": payload_hash,
                    "changeset": json.dumps(changeset),
                    "permit_ref": permit_ref,
                },
            )
        except IntegrityError as e:
            error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "uq_canon_commit_root" in error_msg:
                raise RootCommitExistsError(
                    f"Root commit already exists for project={project_id}, branch={branch_name}"
                ) from e
            elif "uq_canon_commit_idempotency" in error_msg:
                raise IdempotencyConflictError(
                    f"Idempotency key conflict: {idempotency_key}"
                ) from e
            else:
                raise CanonRepositoryError(
                    f"Failed to create root commit: {error_msg}"
                ) from e

    def create_commit(
        self,
        session: Session,
        project_id: str,
        branch_name: str,
        commit_id: str,
        parent_commit_id: str,
        idempotency_key: str,
        payload_hash: str,
        changeset: dict[str, Any],
        permit_ref: str | None = None,
    ) -> None:
        """Create non-root commit with parent reference.

        Args:
            session: Active database session
            project_id: Project scope identifier
            branch_name: Branch name within project
            commit_id: Unique commit identifier
            parent_commit_id: Parent commit ID (must exist)
            idempotency_key: Idempotency key for retry safety
            payload_hash: Content hash of commit payload
            changeset: Commit changeset data
            permit_ref: Optional execution permit reference

        Raises:
            IdempotencyConflictError: If idempotency key conflict detected
            ProjectScopeViolationError: If parent commit not found or scope violation
        """
        try:
            session.execute(
                text("""
                    INSERT INTO canon_commit
                    (project_id, branch_name, commit_id, parent_commit_id,
                     idempotency_key, payload_hash, changeset, permit_ref)
                    VALUES (:project_id, :branch_name, :commit_id, :parent_commit_id,
                            :idempotency_key, :payload_hash, :changeset, :permit_ref)
                """),
                {
                    "project_id": project_id,
                    "branch_name": branch_name,
                    "commit_id": commit_id,
                    "parent_commit_id": parent_commit_id,
                    "idempotency_key": idempotency_key,
                    "payload_hash": payload_hash,
                    "changeset": json.dumps(changeset),
                    "permit_ref": permit_ref,
                },
            )
        except IntegrityError as e:
            error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "uq_canon_commit_idempotency" in error_msg:
                raise IdempotencyConflictError(
                    f"Idempotency key conflict: {idempotency_key}"
                ) from e
            elif "fk_canon_commit_parent" in error_msg:
                raise ProjectScopeViolationError(
                    f"Parent commit not found or scope violation: {parent_commit_id}"
                ) from e
            else:
                raise CanonRepositoryError(
                    f"Failed to create commit: {error_msg}"
                ) from e

    def update_branch_head_cas(
        self,
        session: Session,
        project_id: str,
        branch_name: str,
        new_head_commit_id: str,
        expected_head_commit_id: str | None = None,
    ) -> bool:
        """Update branch HEAD with compare-and-swap semantics.

        Args:
            session: Active database session
            project_id: Project scope identifier
            branch_name: Branch name within project
            new_head_commit_id: New HEAD commit ID
            expected_head_commit_id: Expected current HEAD (None for initial)

        Returns:
            True if update succeeded, False if CAS condition failed

        Raises:
            ProjectScopeViolationError: If new_head_commit_id not found
        """
        if expected_head_commit_id is None:
            # Initial HEAD creation
            try:
                session.execute(
                    text("""
                        INSERT INTO branch_head (project_id, branch_name, head_commit_id)
                        VALUES (:project_id, :branch_name, :head_commit_id)
                    """),
                    {
                        "project_id": project_id,
                        "branch_name": branch_name,
                        "head_commit_id": new_head_commit_id,
                    },
                )
                return True
            except IntegrityError as e:
                error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
                if (
                    "pk_branch_head" in error_msg
                    or "duplicate key" in error_msg.lower()
                ):
                    return False
                elif "fk_branch_head_commit" in error_msg:
                    raise ProjectScopeViolationError(
                        f"Commit not found: {new_head_commit_id}"
                    ) from e
                else:
                    raise CanonRepositoryError(
                        f"Failed to create branch head: {error_msg}"
                    ) from e
        else:
            # CAS update
            try:
                result = session.execute(
                    text("""
                        UPDATE branch_head
                        SET head_commit_id = :new_head, updated_at = CURRENT_TIMESTAMP
                        WHERE project_id = :project_id
                          AND branch_name = :branch_name
                          AND head_commit_id = :expected_head
                    """),
                    {
                        "project_id": project_id,
                        "branch_name": branch_name,
                        "new_head": new_head_commit_id,
                        "expected_head": expected_head_commit_id,
                    },
                )
                return result.rowcount > 0
            except IntegrityError as e:
                error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
                if "fk_branch_head_commit" in error_msg:
                    raise ProjectScopeViolationError(
                        f"Commit not found: {new_head_commit_id}"
                    ) from e
                else:
                    raise CanonRepositoryError(
                        f"Failed to update branch head: {error_msg}"
                    ) from e

    def get_branch_head(
        self, session: Session, project_id: str, branch_name: str
    ) -> str | None:
        """Get current branch HEAD commit ID.

        Args:
            session: Active database session
            project_id: Project scope identifier
            branch_name: Branch name within project

        Returns:
            Current HEAD commit ID, or None if branch not initialized
        """
        result = session.execute(
            text("""
                SELECT head_commit_id FROM branch_head
                WHERE project_id = :project_id AND branch_name = :branch_name
            """),
            {"project_id": project_id, "branch_name": branch_name},
        )
        row = result.fetchone()
        return row[0] if row else None

    def get_commit(
        self, session: Session, project_id: str, branch_name: str, commit_id: str
    ) -> dict[str, Any] | None:
        """Retrieve commit by project/branch/commit_id.

        Args:
            session: Active database session
            project_id: Project scope identifier
            branch_name: Branch name within project
            commit_id: Commit identifier

        Returns:
            Commit data dict or None if not found
        """
        result = session.execute(
            text("""
                SELECT commit_id, parent_commit_id, idempotency_key,
                       payload_hash, changeset, permit_ref, committed_at
                FROM canon_commit
                WHERE project_id = :project_id
                  AND branch_name = :branch_name
                  AND commit_id = :commit_id
            """),
            {
                "project_id": project_id,
                "branch_name": branch_name,
                "commit_id": commit_id,
            },
        )
        row = result.fetchone()
        if row:
            return {
                "commit_id": row[0],
                "parent_commit_id": row[1],
                "idempotency_key": row[2],
                "payload_hash": row[3],
                "changeset": row[4],
                "permit_ref": row[5],
                "committed_at": row[6],
            }
        return None

    def init_execution_control(
        self, session: Session, project_id: str, branch_name: str
    ) -> None:
        """Initialize execution control for project/branch.

        Args:
            session: Active database session
            project_id: Project scope identifier
            branch_name: Branch name within project

        Raises:
            IdempotencyConflictError: If execution control already exists
        """
        try:
            session.execute(
                text("""
                    INSERT INTO execution_control (project_id, branch_name, execution_version)
                    VALUES (:project_id, :branch_name, 1)
                """),
                {"project_id": project_id, "branch_name": branch_name},
            )
        except IntegrityError as e:
            raise IdempotencyConflictError(
                f"Execution control already exists for {project_id}/{branch_name}"
            ) from e

    def get_execution_version(
        self, session: Session, project_id: str, branch_name: str, lock: bool = False
    ) -> int | None:
        """Get current execution version with optional row lock.

        Args:
            session: Active database session
            project_id: Project scope identifier
            branch_name: Branch name within project
            lock: If True, acquire FOR UPDATE lock on the row

        Returns:
            Current execution version or None if not initialized
        """
        lock_clause = " FOR UPDATE" if lock else ""
        result = session.execute(
            text(
                f"""
                SELECT execution_version FROM execution_control
                WHERE project_id = :project_id AND branch_name = :branch_name
                {lock_clause}
            """
            ),
            {"project_id": project_id, "branch_name": branch_name},
        )
        row = result.fetchone()
        return row[0] if row else None

    def cancel_execution(
        self, session: Session, project_id: str, branch_name: str
    ) -> int:
        """Cancel execution by incrementing version (with lock).

        Args:
            session: Active database session
            project_id: Project scope identifier
            branch_name: Branch name within project

        Returns:
            New execution version after cancellation

        Raises:
            CanonRepositoryError: If execution control not found
        """
        result = session.execute(
            text("""
                UPDATE execution_control
                SET execution_version = execution_version + 1,
                    cancelled_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE project_id = :project_id AND branch_name = :branch_name
                RETURNING execution_version
            """),
            {"project_id": project_id, "branch_name": branch_name},
        )
        row = result.fetchone()
        if not row:
            raise CanonRepositoryError(
                f"Execution control not found for {project_id}/{branch_name}"
            )
        return row[0]

    def create_commit_with_fencing(
        self,
        session: Session,
        project_id: str,
        branch_name: str,
        commit_id: str,
        parent_commit_id: str | None,
        expected_execution_version: int,
        idempotency_key: str,
        payload_hash: str,
        changeset: dict[str, Any],
        permit_ref: str | None = None,
    ) -> None:
        """Create commit with execution version fencing.

        Args:
            session: Active database session
            project_id: Project scope identifier
            branch_name: Branch name within project
            commit_id: Unique commit identifier
            parent_commit_id: Parent commit ID (None for root)
            expected_execution_version: Expected execution version (fencing token)
            idempotency_key: Idempotency key for retry safety
            payload_hash: Content hash of commit payload
            changeset: Commit changeset data
            permit_ref: Optional execution permit reference

        Raises:
            ExecutionVersionMismatchError: If execution version does not match
            RootCommitExistsError: If root already exists
            IdempotencyConflictError: If idempotency key conflicts
            ProjectScopeViolationError: If parent not found or scope violation
        """
        # Lock and verify execution version
        current_version = self.get_execution_version(
            session, project_id, branch_name, lock=True
        )
        if current_version is None:
            raise CanonRepositoryError(
                f"Execution control not initialized for {project_id}/{branch_name}"
            )
        if current_version != expected_execution_version:
            raise ExecutionVersionMismatchError(
                f"Execution version mismatch: expected {expected_execution_version}, found {current_version}"
            )

        # Create commit (root or non-root)
        if parent_commit_id is None:
            self.create_root_commit(
                session,
                project_id,
                branch_name,
                commit_id,
                idempotency_key,
                payload_hash,
                changeset,
                permit_ref,
            )
        else:
            self.create_commit(
                session,
                project_id,
                branch_name,
                commit_id,
                parent_commit_id,
                idempotency_key,
                payload_hash,
                changeset,
                permit_ref,
            )

    def close(self) -> None:
        """Close database connection and dispose of connection pool."""
        self.engine.dispose()

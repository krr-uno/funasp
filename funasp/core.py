"""
Core funasp utilities shared across the package.

Currently this hosts :class:`Library`, a wrapper around the clingo
``Library`` that captures and normalizes log messages (e.g. rewriting
"undefined predicate F..." into "undefined intensional function ...") and
carries the ``processing_statement`` text used in error reports.
"""

import typing

from clingo_funasp import ast
from clingo_funasp.core import Library as ClingoLibrary
from clingo_funasp.core import LogLevel, MessageType


class Library:

    def __init__(
        self,
        *,
        shared: bool = True,
        slotted: bool = True,
        log_level: LogLevel = LogLevel.Info,
        logger: typing.Callable[[MessageType, str], None] | None = None,
        message_limit: int = 25,
    ) -> None:
        """Initialize the clingo library wrapper and its message handling state."""
        self.error_messages: list[tuple[MessageType, str]] = []
        self.last_error_reported = 0
        self.shared = shared
        self.slotted = slotted
        self.log_level = log_level
        self.logger = logger
        self.message_limit = message_limit
        self.library = ClingoLibrary(
            shared=shared,
            slotted=slotted,
            log_level=log_level,
            logger=self.handle_log_message,
            message_limit=message_limit,
        )
        self.original_statements: dict[str, list[ast.statements.Statement]] = {}
        self.ignore_info = False
        self._processing_statement: str | None = None

    def processing_statement(self, statement: str) -> None:
        """Set the currently processing statement for more informative logging."""
        self._processing_statement = statement

    def clear_processing_statement(self) -> None:
        """Clear the currently processing statement."""
        self._processing_statement = None

    # def add_original_statement(self, statement: ast.statements.Statement) -> None:
    #     file = statement.location.begin.file
    #     if file not in self.original_statements:
    #         self.original_statements[file] = []
    #     self.original_statements[file].append(statement)

    def handle_log_message(self, msg_type: MessageType, message: str) -> None:
        """Capture, normalize, and optionally forward messages emitted by clingo."""
        self.error_messages.append((msg_type, message))
        new_message = self.normalize_log_message(msg_type, message)
        if (
            new_message
            and self.logger is not None
            and (
                not self.ignore_info
                or msg_type not in {MessageType.Info, MessageType.OperationUndefined}
            )
        ):  # pragma: no cover
            self.logger(msg_type, new_message)

    def normalize_log_message(self, msg_type: MessageType, message: str) -> str | None:
        """Normalize selected clingo messages for FASP-specific reporting."""
        if "unsafe variable" in message:
            lines = message.split("\n")
            if self._processing_statement is None:  # pragma: no cover
                lines[0] = lines[0][9:-3]
                lines.pop(1)
            else:
                lines[1] = f"  {self._processing_statement}"
            message = "\n".join(lines)
        elif (
            "operation undefined" in message and self._processing_statement is not None
        ):
            lines = message.split("\n")
            lines[0] = lines[0][:-1] + " in:"
            lines.insert(1, f"  {self._processing_statement}")
            lines.insert(2, "note: the following operations are undefined:")
            message = "\n".join(lines)
        elif "undefined predicate F" in message:
            if message.startswith("<functional>:0:0-0:"):
                return None
            message = message.replace(
                "undefined predicate F", "undefined intensional function "
            )
        return message

    def __enter__(self) -> typing.Self:
        """Enter the managed context and return this library wrapper."""
        return self

    def __exit__(
        self, exc_type: typing.Any, exc_value: typing.Any, traceback: typing.Any
    ) -> bool:
        """Exit the managed context; clingo's Library needs no explicit close."""
        return False

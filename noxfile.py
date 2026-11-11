import nox, os

PYTHON_VERSIONS = False
if "GITHUB_ACTIONS" in os.environ:
    nox.options.sessions = "typecheck", "slow_test", "format"
else:
    #     PYTHON_VERSIONS = [f"3.{i}" for i in range(13, 14)]
    nox.options.sessions = "typecheck", "test", "format"
# nox.options.sessions = "test", "format"
nox.options.default_venv_backend = "none"

PROJECT_NAME = "funasp"

TESTS_PATH = "tests"


from pathlib import Path

TESTS = sorted(Path(TESTS_PATH).rglob("test_*.py"))

SLOW_TESTS = {
    "tests/test_app.py",
}

INTEGRATION_TESTS = {
    "tests/test_app.py",
    "tests/test_app_patch.py",
    "tests/test_control.py",
}

TESTS = [test for test in TESTS if str(test) not in SLOW_TESTS]
FTESTS = [test for test in TESTS if str(test) not in INTEGRATION_TESTS]

SLOW_TESTS = [*TESTS, *SLOW_TESTS]

COVERAGE_OMIT = ["tests/*"]


@nox.session(python=PYTHON_VERSIONS)
def test(session):
    """Run the test suite."""
    if session.python:
        session.install("clingo")
    session.run(
        "coverage",
        "run",
        "-m",
        "unittest",
        *TESTS,
        "-v",
    )

    session.run(
        "coverage",
        "report",
        "--sort=cover",
        "--fail-under=100",
        "-m",
        f"--omit={','.join(COVERAGE_OMIT)}",
    )


@nox.session(python=PYTHON_VERSIONS)
def ftest(session):
    """Run the test suite."""
    if session.python:
        session.install("clingo")
    session.run(
        "coverage",
        "run",
        "-m",
        "unittest",
        *FTESTS,
        "-v",
    )
    session.run(
        "coverage",
        "report",
        "--sort=cover",
        "--fail-under=100",
        "-m",
        f"--omit={','.join(COVERAGE_OMIT)}",
    )


@nox.session(python=PYTHON_VERSIONS)
def slow_test(session):
    """Run the test suite."""
    if session.python:
        session.install("clingo")
        session.install("coverage")
    session.run(
        "coverage",
        "run",
        "-m",
        "unittest",
        "discover",
        "-v",
    )
    session.run("coverage", "combine", "--append")
    session.run(
        "coverage",
        "report",
        "--sort=cover",
        "--fail-under=100",
        "-m",
        f"--omit={','.join(COVERAGE_OMIT)}",
    )


@nox.session(python=False)
def format(session):
    """Run formatting tools, or check formatting when requested."""
    if session.python:
        max_version = max(v for v in PYTHON_VERSIONS)
        if max_version != session.python:
            return
        session.install("black", "isort", "autoflake")

    check = "check" in session.posargs

    autoflake_args = [
        "--in-place",
        "--imports=clingo",
        "--ignore-init-module-imports",
        "--remove-unused-variables",
        "-r",
        PROJECT_NAME,
    ]
    if check:
        autoflake_args.remove("--in-place")
    session.run("autoflake", *autoflake_args)

    isort_args = ["--profile", "black", PROJECT_NAME]
    if check:
        isort_args.insert(0, "--check")
        isort_args.insert(1, "--diff")
    session.run("isort", *isort_args)

    black_args = [PROJECT_NAME]
    if check:
        black_args.append("--check")
        black_args.append("--diff")
    black_args.append("--target-version")
    black_args.append("py314")
    session.run("black", *black_args)


@nox.session
def lint(session):
    """Run pylint on the project package."""
    if session.python:
        session.install("pylint")
    session.run("pylint", PROJECT_NAME)


@nox.session(python=PYTHON_VERSIONS)
def typecheck(session):
    """Run mypy with the repository type-checking settings."""
    # session.install("mypy")
    session.run(
        "mypy",
        "--allow-redefinition-new",
        "--local-partial-types",
        "--strict",
        "-p",
        PROJECT_NAME,
    )

from __future__ import annotations



import difflib

import io

import json

import os

import re

import shutil

import subprocess

import sys

import tempfile

import zipfile

from dataclasses import dataclass, field

from pathlib import Path

from typing import Any, Callable



import streamlit as st

from dotenv import load_dotenv

from groq import Groq



load_dotenv()



APP_TITLE = "AI Coding Agent — Groq"

DEFAULT_MODEL = "openai/gpt-oss-120b"



MAX_DISCOVERY_FILES = 1000

MAX_PREVIEW_FILES = 160

MAX_FILE_BYTES = 200_000

MAX_CONTEXT_CHARS = 120_000

MAX_SELECTED_FILES = 15

MAX_CHANGES = 10

MAX_REPAIRS = 2

TIMEOUT = 120



IGNORED_DIRS = {

    ".git",

    ".venv",

    "venv",

    "env",

    "node_modules",

    "__pycache__",

    ".pytest_cache",

    ".mypy_cache",

    ".ruff_cache",

    ".idea",

    ".vscode",

    "dist",

    "build",

    "coverage",

    ".next",

    ".tox",

    ".streamlit",

}



IGNORED_FILES = {

    ".env",

    ".env.local",

    ".env.production",

    "secrets.toml",

    "id_rsa",

    "id_ed25519",

}



TEXT_EXTS = {

    ".py",

    ".js",

    ".jsx",

    ".ts",

    ".tsx",

    ".java",

    ".go",

    ".rs",

    ".c",

    ".cpp",

    ".h",

    ".hpp",

    ".cs",

    ".php",

    ".rb",

    ".swift",

    ".kt",

    ".json",

    ".yaml",

    ".yml",

    ".toml",

    ".ini",

    ".cfg",

    ".txt",

    ".md",

    ".html",

    ".css",

    ".scss",

    ".sql",

    ".sh",

    ".bat",

    ".ps1",

}



FAKE_FILES = {

    "docx.py",

    "groq.py",

    "openai.py",

    "requests.py",

    "streamlit.py",

    "pytest.py",

    "fastapi.py",

    "pydantic.py",

    "langchain.py",

    "flask.py",

    "numpy.py",

    "pandas.py",

    "langchain_google_genai.py",

}



FAKE_PACKAGES = {

    "docx",

    "openai",

    "groq",

    "requests",

    "streamlit",

    "pytest",

    "fastapi",

    "pydantic",

    "langchain",

    "langchain_core",

    "langchain_community",

    "google",

    "numpy",

    "pandas",

}



READ_ONLY_PHRASES = (

    "do not change",

    "don't change",

    "do not modify",

    "don't modify",

    "no changes",

    "no edits",

    "read only",

    "read-only",

    "without changing",

    "without modifying",

    "only inspect",

    "inspect and explain",

    "analyze only",

    "review only",

)



ACTION_WORDS = (

    "fix ",

    "add ",

    "change ",

    "modify ",

    "edit ",

    "update ",

    "implement ",

    "create ",

    "write ",

    "remove ",

    "delete ",

    "refactor ",

    "rename ",

    "replace ",

    "build ",

)


INTENTIONAL_FAILURE_MARKERS = (

    "intentional failure",

    "intentionally fail",

    "temporary failing test",

    "temporary failure",

    "report the failure honestly",

    "assert 1 == 2",

)


STANDARD_LIBRARY_NAMES = {

    "re",

    "json",

    "math",

    "os",

    "sys",

    "pathlib",

    "typing",

    "datetime",

    "time",

    "random",

    "collections",

    "itertools",

    "functools",

    "statistics",

    "subprocess",

    "shutil",

    "tempfile",

    "zipfile",

    "io",

    "difflib",

    "unittest",

    "logging",

    "string",

}





@dataclass

class Result:

    mode: str

    plan: dict[str, Any]

    changes: list[dict[str, str]] = field(default_factory=list)

    diff: str = ""

    command: str = ""

    output: str = ""

    passed: bool = False

    repairs: int = 0

    baseline_collection: str = ""

    final_collection: str = ""

    workspace: Path | None = None





# ============================================================

# GROQ

# ============================================================



def secret(name: str) -> str:

    value = os.getenv(name, "").strip()



    if value:

        return value



    try:

        return str(st.secrets.get(name, "")).strip()

    except Exception:

        return ""





def model() -> str:

    return secret("GROQ_MODEL") or DEFAULT_MODEL





def client() -> Groq:

    key = secret("GROQ_API_KEY")



    if not key:

        raise RuntimeError(

            "GROQ_API_KEY is missing. Add it to .env or Streamlit Secrets."

        )



    return Groq(api_key=key)





def call_json(

    c: Groq,

    system: str,

    user: str,

) -> dict[str, Any]:



    response = c.chat.completions.create(

        model=model(),

        messages=[

            {

                "role": "system",

                "content": system,

            },

            {

                "role": "user",

                "content": user,

            },

        ],

        temperature=0,

        response_format={"type": "json_object"},

    )



    text = (

        response.choices[0].message.content

        or "{}"

    ).strip()



    if text.startswith("```"):

        lines = text.splitlines()[1:]



        if lines and lines[-1].strip() == "```":

            lines = lines[:-1]



        text = "\n".join(lines).strip()



        if text.lower().startswith("json"):

            text = text[4:].lstrip()



    try:

        data = json.loads(text)



    except json.JSONDecodeError as exc:

        raise RuntimeError(

            "Groq returned invalid JSON. "

            "No files were changed.\n\n"

            + text[:4000]

        ) from exc



    if not isinstance(data, dict):

        raise RuntimeError(

            "Groq returned JSON, but not an object."

        )



    return data





def call_text(

    c: Groq,

    system: str,

    user: str,

) -> str:



    response = c.chat.completions.create(

        model=model(),

        messages=[

            {

                "role": "system",

                "content": system,

            },

            {

                "role": "user",

                "content": user,

            },

        ],

        temperature=0,

    )



    return (

        response.choices[0].message.content

        or ""

    ).strip()





# ============================================================

# REQUEST CLASSIFICATION

# ============================================================



def read_only_task(task: str) -> bool:

    """Detect explicit inspection-only requests."""

    text = " ".join(
        task.lower().strip().split()
    )

    starts_read_only = text.startswith(
        (
            "inspect ",
            "review ",
            "analyze ",
            "analyse ",
            "explain ",
            "understand ",
        )
    )

    explicit_no_write = any(
        phrase in text
        for phrase in (
            "do not change",
            "don't change",
            "do not modify",
            "don't modify",
            "do not edit",
            "don't edit",
            "do not create",
            "don't create",
            "do not write",
            "don't write",
            "no changes",
            "no edits",
            "read only",
            "read-only",
            "without changing",
            "without modifying",
            "without editing",
            "without creating",
        )
    )

    if starts_read_only and explicit_no_write:
        return True

    return False



# ============================================================

# REPOSITORY DISCOVERY

# ============================================================



def rel(

    path: Path,

    root: Path,

) -> str:



    return (

        path.resolve()

        .relative_to(root.resolve())

        .as_posix()

    )





def text_file(path: Path) -> bool:



    return (

        path.suffix.lower()

        in TEXT_EXTS

        or path.suffix == ""

    )





def repo_paths(

    root: Path,

) -> list[str]:



    ignored_dirs = {

        x.lower()

        for x in IGNORED_DIRS

    }



    ignored_files = {

        x.lower()

        for x in IGNORED_FILES

    }



    result: list[str] = []



    for path in root.rglob("*"):



        if not path.is_file() or path.is_symlink():

            continue



        relative = Path(

            rel(path, root)

        )



        if any(

            part.lower() in ignored_dirs

            for part in relative.parts

        ):

            continue



        if path.name.lower() in ignored_files:

            continue



        result.append(

            relative.as_posix()

        )



        if len(result) >= MAX_DISCOVERY_FILES:

            break



    return sorted(

        result,

        key=str.lower,

    )





def source_files(

    root: Path,

) -> list[Path]:



    ignored_dirs = {

        x.lower()

        for x in IGNORED_DIRS

    }



    ignored_files = {

        x.lower()

        for x in IGNORED_FILES

    }



    result: list[Path] = []



    for path in root.rglob("*"):



        if not path.is_file() or path.is_symlink():

            continue



        relative = Path(

            rel(path, root)

        )



        if any(

            part.lower() in ignored_dirs

            for part in relative.parts

        ):

            continue



        if path.name.lower() in ignored_files:

            continue



        if not text_file(path):

            continue



        try:

            if path.stat().st_size > MAX_FILE_BYTES:

                continue

        except OSError:

            continue



        result.append(path)



        if len(result) >= MAX_DISCOVERY_FILES:

            break



    return sorted(

        result,

        key=lambda p: rel(

            p,

            root,

        ).lower(),

    )





def read(path: Path) -> str:



    return path.read_text(

        encoding="utf-8",

        errors="replace",

    )





def catalog(

    root: Path,

    files: list[Path],

) -> str:



    paths = repo_paths(root)



    parts = [

        "EXACT REPOSITORY PATH MANIFEST:",

        *[

            f"- {path}"

            for path in paths

        ],

        "\nSOURCE/TEXT PREVIEWS:",

    ]



    used = sum(

        len(item)

        for item in parts

    )



    for path in files[:MAX_PREVIEW_FILES]:



        relative = rel(

            path,

            root,

        )



        content = read(path)



        preview = content[:1800]



        if len(content) > 1800:

            preview += "\n... [truncated]"



        block = (

            f"\n### FILE: {relative}\n"

            "```text\n"

            f"{preview}\n"

            "```\n"

        )



        if used + len(block) > MAX_CONTEXT_CHARS:

            break



        parts.append(block)

        used += len(block)



    return "\n".join(parts)





# ============================================================

# MODEL PATH HANDLING

# ============================================================



def normalize_path(

    value: str,

) -> str:



    text = (

        str(value)

        .strip()

        .strip("`")

        .replace("\\\\", "/")

    )



    text = re.sub(

        r"^[-*]\s*",

        "",

        text,

    )



    while text.startswith("./"):

        text = text[2:]



    while "//" in text:

        text = text.replace(

            "//",

            "/",

        )



    return text.strip("/")





def resolve_path(

    value: str,

    existing: list[str],

) -> str | None:



    candidate = normalize_path(value)



    exact = {

        path.lower(): path

        for path in existing

    }



    if candidate.lower() in exact:

        return exact[

            candidate.lower()

        ]



    suffix_matches = [

        path

        for path in existing

        if path.lower().endswith(

            "/" + candidate.lower()

        )

    ]



    if len(suffix_matches) == 1:

        return suffix_matches[0]



    pieces = [

        item

        for item in candidate.split("/")

        if item

    ]



    for count in (

        5,

        4,

        3,

        2,

    ):



        if len(pieces) < count:

            continue



        tail = "/".join(

            pieces[-count:]

        ).lower()



        matches = [

            path

            for path in existing

            if path.lower() == tail

            or path.lower().endswith(

                "/" + tail

            )

        ]



        if len(matches) == 1:

            return matches[0]



    return None





def resolve_many(

    values: Any,

    existing: list[str],

) -> list[str]:



    if not isinstance(

        values,

        list,

    ):

        return []



    result: list[str] = []



    for value in values:



        if not isinstance(

            value,

            str,

        ):

            continue



        match = resolve_path(

            value,

            existing,

        )



        if (

            match

            and match not in result

        ):

            result.append(match)



    return result[

        :MAX_SELECTED_FILES

    ]





# ============================================================

# READ-ONLY INSPECTION

# ============================================================



def inspect_repo(

    c: Groq,

    root: Path,

    files: list[Path],

    task: str,

) -> dict[str, Any]:



    system = """

You are the READ-ONLY inspection stage of a coding agent.



Return JSON only.



Schema:

{

  "summary": "architecture summary",

  "files": [

    {

      "path": "relative/path",

      "purpose": "what the file does"

    }

  ],

  "tests": "how tests relate to the code",

  "dependencies": [

    "dependency"

  ],

  "confirmed_issues": [

    "issue directly supported by repository evidence"

  ],

  "possible_environment_issues": [

    "possible environment issue"

  ]

}



Do not propose code changes.

Do not create a patch.

"""



    user = (

        f"User request:\n{task}\n\n"

        f"Repository:\n"

        f"{catalog(root, files)}"

    )



    try:



        return call_json(

            c,

            system,

            user,

        )



    except RuntimeError:



        fallback = call_text(

            c,

            (

                "Inspect this repository read-only. "

                "Do not propose code changes."

            ),

            user,

        )



        return {

            "summary": fallback,

            "files": [],

            "tests": "",

            "dependencies": [],

            "confirmed_issues": [],

            "possible_environment_issues": [],

        }





# ============================================================

# PLANNER

# ============================================================



def plan(

    c: Groq,

    root: Path,

    files: list[Path],

    task: str,

) -> dict[str, Any]:



    existing = [

        rel(

            path,

            root,

        )

        for path in files

    ]



    system = """

You are the planning stage of a small Codex-like coding agent.



Return JSON only.



Schema:

{

  "summary": "one sentence",

  "steps": [

    "ordered steps"

  ],

  "relevant_files": [

    "EXACT existing repository-relative paths"

  ],

  "allowed_new_files": [

    "new paths only when genuinely needed"

  ],

  "test_strategy": "specific validation command",

  "risks": [

    "important risks"

  ]

}



Rules:

- relevant_files MUST come from the supplied repository manifest.

- Never use absolute paths.

- Never prepend the uploaded folder name.

- Include relevant implementation, configuration, and test files.

- Keep the change minimal.

- Preserve the existing architecture.

- Never plan fake dependency modules or packages.

- Never plan deleting or weakening tests.

"""



    data = call_json(

        c,

        system,

        (

            f"Task:\n{task}\n\n"

            f"Repository:\n"

            f"{catalog(root, files)}"

        ),

    )



    relevant = resolve_many(

        data.get("relevant_files"),

        existing,

    )



    if not relevant:



        correction = call_json(

            c,

            (

                "Return ONLY this JSON shape: "

                "{\"relevant_files\":[\"exact/path.py\"]}. "

                "Choose ONLY from the provided manifest."

            ),

            (

                f"Task:\n{task}\n\n"

                "Exact manifest:\n"

                + "\n".join(

                    f"- {item}"

                    for item in existing

                )

            ),

        )



        relevant = resolve_many(

            correction.get(

                "relevant_files"

            ),

            existing,

        )



    if not relevant:

        raise RuntimeError(

            "Planner could not resolve any relevant existing files."

        )



    new_files: list[str] = []



    allowed_new = data.get(

        "allowed_new_files",

    )



    if isinstance(

        allowed_new,

        list,

    ):



        for value in allowed_new:



            if not isinstance(

                value,

                str,

            ):

                continue



            path = normalize_path(

                value

            )



            if (

                path

                and path not in existing

                and path not in new_files

            ):

                new_files.append(path)



    data["relevant_files"] = relevant

    data["allowed_new_files"] = new_files[

        :MAX_SELECTED_FILES

    ]



    if not isinstance(

        data.get("steps"),

        list,

    ):

        data["steps"] = []



    if not isinstance(

        data.get("risks"),

        list,

    ):

        data["risks"] = []



    return data





# ============================================================

# IMPLEMENTATION

# ============================================================



def context(

    root: Path,

    paths: list[str],

) -> str:



    output: list[str] = []

    used = 0



    for relative in paths:



        path = (

            root / relative

        ).resolve()



        try:

            path.relative_to(

                root.resolve()

            )

        except ValueError:

            continue



        if not path.is_file():

            continue



        content = read(path)



        if len(content) > 50_000:

            content = (

                content[:50_000]

                + "\n... [truncated]"

            )



        block = (

            f"\n### FILE: {relative}\n"

            "```text\n"

            f"{content}\n"

            "```\n"

        )



        if (

            used + len(block)

            > MAX_CONTEXT_CHARS

        ):

            break



        output.append(block)

        used += len(block)



    return "".join(output)





def snapshot(

    root: Path,

) -> dict[str, str]:



    return {

        rel(path, root): read(path)

        for path in source_files(root)

    }





def test_paths(

    data: dict[str, str],

) -> set[str]:



    result = set()



    for path in data:



        name = Path(path).name

        lower = path.lower()



        if (

            name.startswith("test_")

            or name.endswith("_test.py")

            or "/tests/" in f"/{lower}/"

        ):

            result.add(path)



    return result





def is_test_path(

    path: str,

) -> bool:



    lower = path.lower()



    return (

        Path(path).name.startswith("test_")

        or Path(path).name.endswith("_test.py")

        or "/tests/" in f"/{lower}/"

    )





def implementation(

    c: Groq,

    root: Path,

    task: str,

    plan_data: dict[str, Any],

    baseline: dict[str, str],

    failure: str = "",

) -> list[dict[str, str]]:



    allowed = (

        list(

            plan_data["relevant_files"]

        )

        + list(

            plan_data.get(

                "allowed_new_files",

                [],

            )

        )

    )



    system = """

You are the implementation stage of a coding agent.



Return JSON only:



{

  "changes": [

    {

      "path": "relative/path",

      "content": "complete file contents",

      "rationale": "why the file changes"

    }

  ]

}



Rules:

- Change ONLY files in APPROVED CHANGE PATHS.

- New files are allowed only when listed in allowed_new_files.

- Preserve unrelated behavior.

- Preserve the existing architecture.

- Never create fake third-party modules or packages.

- Never create docx.py, a docx package, langchain_core package,

  groq.py, openai.py, requests.py, pytest.py, fastapi.py,

  pydantic.py, or similar substitute modules.

- Never delete or weaken existing tests.

- Never replace real behavior with a permanent stub returning

  empty or constant data.

- Never rewrite a large existing file when a small change is enough.

- Address validation failures at their root cause.

- Return complete file contents.

"""



    user = (

        f"Task:\n{task}\n\n"

        f"Plan:\n"

        f"{json.dumps(plan_data, indent=2)}\n\n"

        "APPROVED CHANGE PATHS:\n"

        f"{json.dumps(allowed, indent=2)}\n\n"

        "CURRENT FILES:\n"

        f"{context(root, allowed)}\n\n"

        "LATEST VALIDATION FAILURE:\n"

        f"{failure[-14_000:] if failure else 'None'}"

    )



    data = call_json(

        c,

        system,

        user,

    )



    raw = data.get(

        "changes"

    )



    if not isinstance(

        raw,

        list,

    ):

        raise RuntimeError(

            "Implementation response did not contain a changes list."

        )



    result: list[

        dict[str, str]

    ] = []



    for item in raw[

        :MAX_CHANGES

    ]:



        if not isinstance(

            item,

            dict,

        ):

            continue



        path = normalize_path(

            item.get(

                "path",

                "",

            )

        )



        content = item.get(

            "content"

        )



        if (

            path

            and isinstance(

                content,

                str,

            )

        ):

            result.append(

                {

                    "path": path,

                    "content": content,

                    "rationale": str(

                        item.get(

                            "rationale",

                            "",

                        )

                    ).strip(),

                }

            )



    if not result:

        raise RuntimeError(

            "Implementation response contained no usable file changes."

        )



    return result





# ============================================================

# SAFETY GATES

# ============================================================



def secret_like(

    path: Path,

) -> bool:



    name = path.name.lower()



    return (

        name

        in {

            x.lower()

            for x in IGNORED_FILES

        }

        or name.startswith(".env")

        or name

        in {

            "credentials.json",

            "service-account.json",

            "secrets.json",

        }

    )





def validate_changes(

    changes: list[dict[str, str]],

    plan_data: dict[str, Any],

    baseline: dict[str, str],

) -> None:



    allowed = (

        set(

            plan_data["relevant_files"]

        )

        | set(

            plan_data.get(

                "allowed_new_files",

                [],

            )

        )

    )



    violations = [

        normalize_path(

            change["path"]

        )

        for change in changes

        if normalize_path(

            change["path"]

        ) not in allowed

    ]



    if violations:

        raise RuntimeError(

            "Implementation attempted to modify files "

            "outside the approved plan:\n"

            + "\n".join(

                f"- {item}"

                for item in violations

            )

        )



    for change in changes:



        path = normalize_path(

            change["path"]

        )



        path_obj = Path(path)



        if secret_like(path_obj):

            raise RuntimeError(

                f"Refusing to edit secret-like file: {path}"

            )



        if (

            path_obj.name.lower()

            in FAKE_FILES

            and path not in baseline

        ):

            raise RuntimeError(

                "Refusing to create "

                f"dependency-shadowing module: {path}"

            )



        if (

            any(

                part.lower()

                in FAKE_PACKAGES

                for part in path_obj.parts[:-1]

            )

            and path not in baseline

        ):

            raise RuntimeError(

                "Refusing to create "

                f"fake dependency package: {path}"

            )



        if path not in baseline:

            continue



        old = baseline[path]

        new = change["content"]



        old_lines = old.splitlines()

        new_lines = new.splitlines()



        if (

            len(old_lines) >= 20

            and len(new_lines)

            < len(old_lines) * 0.40

        ):

            raise RuntimeError(

                "Rejected destructive rewrite of "

                f"{path}: more than 60% of existing lines were removed."

            )



        if (

            is_test_path(path)

            and len(old_lines) >= 10

            and len(new_lines)

            < len(old_lines) * 0.75

        ):

            raise RuntimeError(

                "Rejected large reduction of "

                f"existing test file: {path}"

            )



        if (

            "retrieval" in path.lower()

            and "return []" in new.lower()

            and "return []" not in old.lower()

        ):

            raise RuntimeError(

                f"Rejected suspected retrieval stub in {path}."

            )





def apply(

    root: Path,

    changes: list[dict[str, str]],

    plan_data: dict[str, Any],

    baseline: dict[str, str],

) -> None:



    validate_changes(

        changes,

        plan_data,

        baseline,

    )



    root_resolved = root.resolve()



    for change in changes:



        path = normalize_path(

            change["path"]

        )



        target = (

            root / path

        ).resolve()



        try:

            target.relative_to(

                root_resolved

            )

        except ValueError as exc:

            raise RuntimeError(

                f"Unsafe change path rejected: {path}"

            ) from exc



        if not text_file(

            Path(path)

        ):

            raise RuntimeError(

                f"Only text/source files may be changed: {path}"

            )



        if (

            target.exists()

            and not target.is_file()

        ):

            raise RuntimeError(

                "Refusing to overwrite a "

                f"non-file path: {path}"

            )



        if (

            len(

                change["content"].encode(

                    "utf-8"

                )

            )

            > MAX_FILE_BYTES

        ):

            raise RuntimeError(

                f"Generated file is too large: {path}"

            )



        target.parent.mkdir(

            parents=True,

            exist_ok=True,

        )



        target.write_text(

            change["content"],

            encoding="utf-8",

        )





def verify_tests(

    root: Path,

    baseline: dict[str, str],

) -> None:



    current = snapshot(root)



    before = test_paths(

        baseline

    )



    after = test_paths(

        current

    )



    deleted = before - after



    if deleted:

        raise RuntimeError(

            "Existing test files were deleted:\n"

            + "\n".join(

                f"- {item}"

                for item in sorted(deleted)

            )

        )



    for path in before & after:



        old = baseline[path].splitlines()

        new = current[path].splitlines()



        if (

            len(old) >= 10

            and len(new)

            < len(old) * 0.75

        ):

            raise RuntimeError(

                "Existing test file was "

                f"substantially reduced: {path}"

            )





# ============================================================

# VALIDATION

# ============================================================



def collect_only(

    root: Path,

) -> tuple[bool, int | None, str]:



    has_tests = any(

        is_test_path(

            rel(path, root)

        )

        for path in source_files(root)

    )



    if not has_tests:

        return (

            True,

            None,

            "No pytest-style tests detected.",

        )



    try:



        process = subprocess.run(

            [

                sys.executable,

                "-m",

                "pytest",

                "--collect-only",

                "-q",

            ],

            cwd=root,

            text=True,

            capture_output=True,

            timeout=TIMEOUT,

        )



    except Exception as exc:



        return (

            False,

            None,

            str(exc),

        )



    output = (

        process.stdout

        or ""

    )



    if process.stderr:

        output += (

            "\n"

            + process.stderr

        )



    match = re.search(

        r"(\d+)\s+tests?\s+collected",

        output,

    )



    count = (

        int(match.group(1))

        if match

        else None

    )



    return (

        process.returncode == 0,

        count,

        output.strip(),

    )





def validate(

    root: Path,

) -> tuple[bool, str, str]:



    has_tests = any(

        is_test_path(

            rel(path, root)

        )

        for path in source_files(root)

    )



    if has_tests:



        command = (

            "python -m pytest -q"

        )



        argv = [

            sys.executable,

            "-m",

            "pytest",

            "-q",

        ]



    else:



        command = (

            "python -m compileall -q ."

        )



        argv = [

            sys.executable,

            "-m",

            "compileall",

            "-q",

            ".",

        ]



    try:



        process = subprocess.run(

            argv,

            cwd=root,

            text=True,

            capture_output=True,

            timeout=TIMEOUT,

            env={

                **os.environ,

                "PYTHONUNBUFFERED": "1",

            },

        )



    except subprocess.TimeoutExpired:



        return (

            False,

            command,

            (

                f"Validation timed out after "

                f"{TIMEOUT} seconds."

            ),

        )



    except Exception as exc:



        return (

            False,

            command,

            str(exc),

        )



    output = (

        process.stdout

        or ""

    )



    if process.stderr:

        output += (

            "\n"

            + process.stderr

        )



    return (

        process.returncode == 0,

        command,

        output.strip(),

    )





# ============================================================

# DIFF

# ============================================================



def make_diff(

    root: Path,

    baseline: dict[str, str],

) -> str:



    current = snapshot(root)



    result: list[str] = []



    for path in sorted(

        set(baseline)

        | set(current),

        key=str.lower,

    ):



        old = baseline.get(

            path,

            "",

        ).splitlines(

            keepends=True

        )



        new = current.get(

            path,

            "",

        ).splitlines(

            keepends=True

        )



        if old == new:

            continue



        result.extend(

            difflib.unified_diff(

                old,

                new,

                fromfile=(

                    f"a/{path}"

                    if path in baseline

                    else "/dev/null"

                ),

                tofile=(

                    f"b/{path}"

                    if path in current

                    else "/dev/null"

                ),

            )

        )



    return "".join(result)





def is_intentional_failure_request(task: str) -> bool:

    text = task.lower()

    has_failure_request = any(
        marker in text
        for marker in INTENTIONAL_FAILURE_MARKERS
    )

    has_cleanup_instruction = any(
        phrase in text
        for phrase in (
            "remove",
            "restore",
            "clean diff",
            "clean state",
            "final diff",
        )
    )

    return (
        has_failure_request
        and has_cleanup_instruction
    )



def choose_temporary_test_file(
    root: Path,
    task: str,
) -> Path:

    match = re.search(
        r"\b(?:in|to|inside)\s+([A-Za-z0-9_./\\-]+\.py)\b",
        task,
        re.IGNORECASE,
    )

    if match:

        candidate = (
            root
            / normalize_path(
                match.group(1)
            )
        ).resolve()

        try:
            candidate.relative_to(
                root.resolve()
            )

            if candidate.is_file():
                return candidate

        except ValueError:
            pass

    test_files = [
        path
        for path in source_files(root)
        if is_test_path(
            rel(
                path,
                root,
            )
        )
    ]

    if not test_files:
        raise RuntimeError(
            "The intentional-failure workflow requires "
            "an existing pytest test file."
        )

    return test_files[0]



def extract_requested_assertion(
    task: str,
) -> str:

    for line in task.splitlines():

        match = re.search(
            r"\bassert\s+.+",
            line,
            re.IGNORECASE,
        )

        if match:

            assertion = (
                match.group(0)
                .strip()
                .strip("`")
            )

            if "\n" in assertion or "\r" in assertion:
                continue

            return assertion

    return "assert 1 == 2"



def run_intentional_failure_workflow(
    root: Path,
    task: str,
    progress: Callable[[str], None],
) -> Result:

    baseline = snapshot(root)

    baseline_passed, baseline_command, baseline_output = (
        validate(root)
    )

    if not baseline_passed:
        raise RuntimeError(
            "Cannot run the intentional-failure check because "
            "the baseline test suite is already failing.\n\n"
            + baseline_output
        )

    target = choose_temporary_test_file(
        root,
        task,
    )

    assertion = extract_requested_assertion(
        task
    )

    original = read(target)

    temporary_block = (
        "\n\n"
        "# BEGIN CODING_AGENT_INTENTIONAL_FAILURE\n"
        "def test_coding_agent_intentional_failure():\n"
        f"    {assertion}\n"
        "# END CODING_AGENT_INTENTIONAL_FAILURE\n"
    )

    progress(
        "Adding temporary failing assertion to "
        + rel(target, root)
    )

    target.write_text(
        original + temporary_block,
        encoding="utf-8",
    )

    progress(
        "Running the expected failing test suite"
    )

    failure_passed, failure_command, failure_output = (
        validate(root)
    )

    failure_observed = not failure_passed

    target.write_text(
        original,
        encoding="utf-8",
    )

    progress(
        "Restored the project to its pre-check state"
    )

    final_passed, final_command, final_output = (
        validate(root)
    )

    final_diff = make_diff(
        root,
        baseline,
    )

    success = (
        failure_observed
        and final_passed
        and final_diff == ""
    )

    combined_output = (
        "EXPECTED TEMPORARY FAILURE:\n"
        + failure_output
        + "\n\nFINAL VALIDATION AFTER CLEANUP:\n"
        + final_output
    )

    return Result(
        mode="intentional_failure",
        plan={
            "summary": (
                "Run a temporary failing test, verify "
                "the failure, restore the project, and "
                "confirm a clean final state."
            ),
            "target_test": rel(target, root),
            "assertion": assertion,
            "baseline_command": baseline_command,
            "failure_command": failure_command,
            "final_command": final_command,
        },
        changes=[],
        diff=final_diff,
        command=final_command,
        output=combined_output,
        passed=success,
        repairs=0,
        baseline_collection=baseline_output,
        final_collection=final_output,
        workspace=root,
    )



def explicit_dependency_request(
    task: str,
) -> str | None:

    patterns = (
        r"\b(?:using|use|with)\s+"
        r"([A-Za-z_][\w.-]*)\s+"
        r"(?:library|package|dependency|module)\b",
        r"\b(?:library|package|dependency|module)\s+"
        r"(?:called|named)\s+"
        r"([A-Za-z_][\w.-]*)\b",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            task,
            re.IGNORECASE,
        )

        if not match:
            continue

        name = match.group(1).strip(
            "`.,:;()[]{}"
        )

        if name.lower() in STANDARD_LIBRARY_NAMES:
            return None

        return name

    return None



def dependency_is_declared(
    root: Path,
    dependency: str,
) -> bool:

    manifests = {
        "requirements.txt",
        "requirements-dev.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "Pipfile.lock",
        "package.json",
        "package-lock.json",
    }

    wanted = (
        dependency
        .lower()
        .replace("-", "_")
    )

    for path in root.rglob("*"):

        if (
            not path.is_file()
            or path.name not in manifests
        ):
            continue

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            continue

        normalized = (
            content
            .lower()
            .replace("-", "_")
        )

        if wanted in normalized:
            return True

    return False



def missing_requested_dependency(
    root: Path,
    task: str,
) -> str | None:

    dependency = explicit_dependency_request(
        task
    )

    if not dependency:
        return None

    lowered = task.lower()

    explicit_dependency_change = any(
        phrase in lowered
        for phrase in (
            "add the dependency",
            "add it to requirements",
            "add to requirements.txt",
            "declare the dependency",
            "update requirements.txt",
            "update pyproject.toml",
        )
    )

    if explicit_dependency_change:
        return None

    if dependency_is_declared(
        root,
        dependency,
    ):
        return None

    return dependency


# ============================================================

# AGENT

# ============================================================



def execute(

    root: Path,

    task: str,

    progress: Callable[[str], None],

) -> Result:



    c = client()



    files = source_files(root)



    if not files:

        raise RuntimeError(

            "No readable source/text files were found in the project."

        )



    baseline = snapshot(root)



    progress(

        f"Indexed {len(repo_paths(root))} repository paths "

        f"and {len(files)} editable files"

    )



    # --------------------------------------------------------

    # INTENTIONAL FAILURE VALIDATION

    # --------------------------------------------------------

    if is_intentional_failure_request(task):

        progress(
            "Intentional-failure validation mode detected; "
            "no persistent code changes will be kept"
        )

        return run_intentional_failure_workflow(
            root,
            task,
            progress,
        )



    # --------------------------------------------------------

    # READ ONLY

    # --------------------------------------------------------



    if read_only_task(task):



        progress(

            "Read-only request detected; "

            "no files will be modified"

        )



        analysis = inspect_repo(

            c,

            root,

            files,

            task,

        )



        return Result(

            mode="read_only",

            plan=analysis,

            workspace=root,

        )



    # --------------------------------------------------------

    # DEPENDENCY SAFETY

    # --------------------------------------------------------

    missing_dependency = missing_requested_dependency(
        root,
        task,
    )

    if missing_dependency:

        progress(
            f"Dependency review: {missing_dependency} is not declared"
        )

        return Result(
            mode="dependency_blocked",
            plan={
                "summary": (
                    f"The requested dependency '{missing_dependency}' "
                    "is not declared in the project."
                ),
                "dependency": missing_dependency,
                "next_step": (
                    "Add and approve the dependency in the project's "
                    "dependency manifest, then rerun the task. The agent "
                    "will not create a fake local package or silently "
                    "substitute a different implementation."
                ),
            },
            workspace=root,
        )



    # --------------------------------------------------------

    # BASELINE TEST COLLECTION

    # --------------------------------------------------------



    baseline_ok, baseline_count, baseline_output = (

        collect_only(root)

    )



    if baseline_count is not None:



        progress(

            "Baseline test collection: "

            f"{baseline_count} test(s) discovered"

        )



    elif not baseline_ok:



        progress(

            "Baseline test collection has errors; "

            "they will be reported"

        )



    # --------------------------------------------------------

    # PLAN

    # --------------------------------------------------------



    progress(

        "Planning task"

    )



    plan_data = plan(

        c,

        root,

        files,

        task,

    )



    progress(

        "Relevant files: "

        + ", ".join(

            plan_data["relevant_files"]

        )

    )



    if plan_data.get(

        "allowed_new_files"

    ):



        progress(

            "Approved new files: "

            + ", ".join(

                plan_data[

                    "allowed_new_files"

                ]

            )

        )



    # --------------------------------------------------------

    # IMPLEMENT

    # --------------------------------------------------------



    changes = implementation(

        c,

        root,

        task,

        plan_data,

        baseline,

    )



    apply(

        root,

        changes,

        plan_data,

        baseline,

    )



    verify_tests(

        root,

        baseline,

    )



    # --------------------------------------------------------

    # VALIDATE

    # --------------------------------------------------------



    passed, command, output = validate(

        root

    )



    repairs = 0



    # --------------------------------------------------------

    # REPAIR

    # --------------------------------------------------------



    while (

        not passed

        and repairs < MAX_REPAIRS

    ):



        repairs += 1



        progress(

            f"Repairing validation failure "

            f"({repairs}/{MAX_REPAIRS})"

        )



        repair = implementation(

            c,

            root,

            task,

            plan_data,

            baseline,

            output,

        )



        apply(

            root,

            repair,

            plan_data,

            baseline,

        )



        verify_tests(

            root,

            baseline,

        )



        changes.extend(

            repair

        )



        passed, command, output = validate(

            root

        )



    # --------------------------------------------------------

    # FINAL VALIDATION SAFETY

    # --------------------------------------------------------



    final_ok, final_count, final_output = (

        collect_only(root)

    )



    if (

        baseline_count is not None

        and final_count is not None

        and final_count < baseline_count

    ):



        passed = False



        output += (

            "\n\nSafety check: final test "

            "collection dropped from "

            f"{baseline_count} to "

            f"{final_count}."

        )



    if (

        not final_ok

        and command.startswith(

            "python -m pytest"

        )

    ):



        passed = False



        output += (

            "\n\nFinal test collection failed."

        )



    # Conservative protection against the exact

    # Research Agent failure observed earlier:

    # broken baseline + tiny successful final suite.

    if (

        not baseline_ok

        and baseline_count is None

        and final_count is not None

        and final_count <= 1

    ):



        passed = False



        output += (

            "\n\nSafety check: baseline "

            "collection failed and final "

            "collection is too small to "

            "establish full-suite success."

        )



    return Result(

        mode="implementation",

        plan=plan_data,

        changes=changes,

        diff=make_diff(

            root,

            baseline,

        ),

        command=command,

        output=output,

        passed=passed,

        repairs=repairs,

        baseline_collection=baseline_output,

        final_collection=final_output,

        workspace=root,

    )





# ============================================================

# SAMPLE PROJECT

# ============================================================



def reset_sample(

    root: Path,

) -> None:



    if root.exists():

        shutil.rmtree(

            root,

            ignore_errors=True,

        )



    files = {

        "app.py": (

            "def divide(a: float, b: float) -> float:\n"

            "    return a / b\n\n\n"

            "def format_result(value: float) -> str:\n"

            "    return f\"Result: {value:g}\"\n"

        ),

        "calculator.py": (

            "from app import divide\n\n\n"

            "def calculate(a: float, b: float) -> str:\n"

            "    return f\"{a} / {b} = {divide(a, b)}\"\n"

        ),

        "test_app.py": (

            "from app import divide, format_result\n\n\n"

            "def test_divide():\n"

            "    assert divide(8, 2) == 4\n\n\n"

            "def test_format_result():\n"

            "    assert format_result(3.5) == \"Result: 3.5\"\n"

        ),

        "README.md": (

            "# Sample Calculator Project\n\n"

            "A tiny project used to demonstrate "

            "the AI coding agent.\n"

        ),

    }



    root.mkdir(

        parents=True,

        exist_ok=True,

    )



    for path, content in files.items():



        target = root / path



        target.parent.mkdir(

            parents=True,

            exist_ok=True,

        )



        target.write_text(

            content,

            encoding="utf-8",

        )





def get_demo_root() -> Path:



    if "demo_root" not in st.session_state:



        root = Path(

            tempfile.mkdtemp(

                prefix="groq_agent_demo_"

            )

        )



        reset_sample(root)



        st.session_state.demo_root = str(

            root

        )



    root = Path(

        st.session_state.demo_root

    )



    if not root.exists():

        reset_sample(root)



    return root





# ============================================================

# ZIP

# ============================================================



def extract_zip(

    uploaded: Any,

) -> Path:



    target = Path(

        tempfile.mkdtemp(

            prefix="groq_agent_upload_"

        )

    )



    try:



        with zipfile.ZipFile(

            io.BytesIO(

                uploaded.getvalue()

            )

        ) as archive:



            for member in archive.infolist():



                name = member.filename.replace(

                    "\\\\",

                    "/",

                )



                member_path = Path(

                    name

                )



                if (

                    member_path.is_absolute()

                    or ".."

                    in member_path.parts

                ):

                    raise RuntimeError(

                        "The uploaded ZIP contains an unsafe path."

                    )



                if member.is_dir():

                    continue



                destination = (

                    target

                    / member_path

                ).resolve()



                destination.relative_to(

                    target.resolve()

                )



                destination.parent.mkdir(

                    parents=True,

                    exist_ok=True,

                )



                with (

                    archive.open(

                        member,

                        "r",

                    ) as source,

                    destination.open(

                        "wb"

                    ) as dest,

                ):



                    shutil.copyfileobj(

                        source,

                        dest,

                    )



    except zipfile.BadZipFile as exc:



        shutil.rmtree(

            target,

            ignore_errors=True,

        )



        raise RuntimeError(

            "The uploaded file is not a valid ZIP archive."

        ) from exc



    except Exception:



        shutil.rmtree(

            target,

            ignore_errors=True,

        )



        raise



    children = list(

        target.iterdir()

    )



    if (

        len(children) == 1

        and children[0].is_dir()

    ):



        nested = children[0]



        flat = Path(

            tempfile.mkdtemp(

                prefix="groq_agent_flat_"

            )

        )



        for item in nested.rglob("*"):



            destination = (

                flat

                / item.relative_to(

                    nested

                )

            )



            if item.is_dir():



                destination.mkdir(

                    parents=True,

                    exist_ok=True,

                )



            elif item.is_file():



                destination.parent.mkdir(

                    parents=True,

                    exist_ok=True,

                )



                shutil.copy2(

                    item,

                    destination,

                )



        shutil.rmtree(

            target,

            ignore_errors=True,

        )



        return flat



    return target





def zip_result(

    root: Path,

) -> bytes:



    buffer = io.BytesIO()



    ignored_dirs = {

        x.lower()

        for x in IGNORED_DIRS

    }



    ignored_files = {

        x.lower()

        for x in IGNORED_FILES

    }



    with zipfile.ZipFile(

        buffer,

        "w",

        zipfile.ZIP_DEFLATED,

    ) as archive:



        for path in root.rglob("*"):



            if not path.is_file():

                continue



            if (

                path.name.lower()

                in ignored_files

            ):

                continue



            if any(

                part.lower()

                in ignored_dirs

                for part in path.parts

            ):

                continue



            archive.writestr(

                rel(path, root),

                path.read_bytes(),

            )



    return buffer.getvalue()





# ============================================================

# UI

# ============================================================



def render_plan(

    data: dict[str, Any],

) -> None:



    st.subheader(

        "1. Plan"

    )



    st.write(

        data.get(

            "summary",

            "",

        )

    )



    for index, step in enumerate(

        data.get(

            "steps",

            [],

        ),

        start=1,

    ):



        st.write(

            f"{index}. {step}"

        )



    st.markdown(

        "**Relevant files selected by the agent**"

    )



    for path in data.get(

        "relevant_files",

        [],

    ):



        st.code(path)



    if data.get(

        "allowed_new_files"

    ):



        st.markdown(

            "**Approved new files**"

        )



        for path in data[

            "allowed_new_files"

        ]:



            st.code(path)



    if data.get(

        "test_strategy"

    ):



        st.markdown(

            "**Validation strategy**"

        )



        st.write(

            data[

                "test_strategy"

            ]

        )



    if data.get(

        "risks"

    ):



        st.markdown(

            "**Risks / assumptions**"

        )



        for risk in data[

            "risks"

        ]:



            st.write(

                f"- {risk}"

            )





def main() -> None:



    st.set_page_config(

        page_title=APP_TITLE,

        page_icon="🛠️",

        layout="wide",

    )



    st.title(

        "🛠️ AI Coding Agent"

    )



    st.caption(

        "Natural language → inspect → plan → "

        "implement → validate → bounded repair"

    )



    demo = get_demo_root()



    with st.sidebar:



        st.header(

            "Project"

        )



        source = st.radio(

            "Project source",

            [

                "Bundled sample",

                "Upload ZIP",

            ],

            index=0,

        )



        uploaded = (

            st.file_uploader(

                "Upload project ZIP",

                type=["zip"],

            )

            if source == "Upload ZIP"

            else None

        )



        st.divider()



        st.write(

            "**Provider:** Groq"

        )



        st.write(

            "**Model:**",

            model(),

        )



        st.write(

            "**Repair rounds:**",

            MAX_REPAIRS,

        )



        if st.button(

            "Reset bundled sample"

        ):



            reset_sample(

                demo

            )



            st.success(

                "Bundled sample reset."

            )



        st.info(

            "GROQ_API_KEY goes in .env locally "

            "or Streamlit Secrets when deployed."

        )



    task = st.text_area(

        "Developer task",

        value=(

            "Add input validation to divide() so "

            "b=0 raises a clear ValueError, and "

            "add a meaningful test for that behavior."

        ),

        height=140,

    )



    root: Path | None = (

        demo

        if source == "Bundled sample"

        else None

    )



    if source == "Bundled sample":



        st.success(

            "Using bundled sample repository."

        )



    elif uploaded is not None:



        try:



            root = extract_zip(

                uploaded

            )



            st.success(

                "ZIP extracted safely into "

                "a temporary workspace."

            )



        except Exception as exc:



            st.error(

                str(exc)

            )



    if root is not None:



        paths = repo_paths(

            root

        )



        st.caption(

            f"Repository indexed "

            f"({len(paths)} paths)"

        )



        with st.expander(

            "Repository files",

            expanded=False,

        ):



            for path in paths:

                st.code(path)



    run = st.button(

        "▶ Run coding agent",

        type="primary",

        use_container_width=True,

    )



    if not run:

        return



    if not task.strip():



        st.warning(

            "Enter a developer task first."

        )



        return



    if root is None:



        st.warning(

            "Choose a project first."

        )



        return



    status = st.status(

        "Running coding agent…",

        expanded=True,

    )



    def progress(

        message: str,

    ) -> None:



        status.write(

            "• " + message

        )



    try:



        result = execute(

            root,

            task.strip(),

            progress,

        )



        status.update(

            label="Coding agent finished",

            state=(

                "complete"

                if (

                    result.mode

                    in {
                        "read_only",
                        "dependency_blocked",
                        "intentional_failure",
                    }

                    or result.passed

                )

                else "error"

            ),

            expanded=False,

        )



        # ----------------------------------------------------

        # INTENTIONAL FAILURE

        # ----------------------------------------------------

        if result.mode == "intentional_failure":

            st.subheader(
                "Intentional failure validation"
            )

            st.write(
                result.plan.get(
                    "summary",
                    "",
                )
            )

            st.markdown(
                "**Temporary assertion**"
            )

            st.code(
                result.plan.get(
                    "assertion",
                    "",
                )
            )

            st.markdown(
                "**Expected failure output**"
            )

            st.code(
                result.output
                or "No failure output captured.",
                language="text",
            )

            st.markdown(
                "**Final diff after cleanup**"
            )

            st.code(
                result.diff
                or "No diff — the project was restored exactly.",
                language="diff",
            )

            if result.passed:
                st.success(
                    "Expected failure was observed, the temporary "
                    "test was removed, the final test suite passed, "
                    "and the final diff is clean."
                )
            else:
                st.error(
                    "The intentional-failure workflow did not "
                    "complete safely."
                )

            return



        # ----------------------------------------------------

        # DEPENDENCY REVIEW

        # ----------------------------------------------------

        if result.mode == "dependency_blocked":

            st.subheader(
                "Dependency review"
            )

            st.warning(
                result.plan.get(
                    "summary",
                    "Requested dependency is not declared.",
                )
            )

            st.write(
                result.plan.get(
                    "next_step",
                    "Review the project's dependency manifest.",
                )
            )

            st.success(
                "No project files were modified."
            )

            return



        # ----------------------------------------------------

        # READ-ONLY

        # ----------------------------------------------------



        if result.mode == "read_only":



            st.subheader(

                "Read-only repository analysis"

            )



            st.write(

                result.plan.get(

                    "summary",

                    "",

                )

            )



            if result.plan.get(

                "files"

            ):



                st.markdown(

                    "**Files**"

                )



                for item in result.plan[

                    "files"

                ]:



                    st.write(

                        f"**{item.get('path', '')}** "

                        f"— {item.get('purpose', '')}"

                    )



            if result.plan.get(

                "tests"

            ):



                st.markdown(

                    "**Tests**"

                )



                st.write(

                    result.plan[

                        "tests"

                    ]

                )



            if result.plan.get(

                "dependencies"

            ):



                st.markdown(

                    "**Dependencies**"

                )



                for dependency in result.plan[

                    "dependencies"

                ]:



                    st.write(

                        f"- {dependency}"

                    )



            if result.plan.get(

                "confirmed_issues"

            ):



                st.markdown(

                    "**Confirmed issues**"

                )



                for issue in result.plan[

                    "confirmed_issues"

                ]:



                    st.write(

                        f"- {issue}"

                    )



            if result.plan.get(

                "possible_environment_issues"

            ):



                st.markdown(

                    "**Possible environment issues**"

                )



                for issue in result.plan[

                    "possible_environment_issues"

                ]:



                    st.write(

                        f"- {issue}"

                    )



            st.success(

                "Read-only task completed. "

                "No files were modified."

            )



            return



        # ----------------------------------------------------

        # PLAN

        # ----------------------------------------------------



        render_plan(

            result.plan

        )



        # ----------------------------------------------------

        # CHANGES

        # ----------------------------------------------------



        st.subheader(

            "2. Changes"

        )



        for change in result.changes:



            with st.expander(

                change["path"],

                expanded=False,

            ):



                st.write(

                    change.get(

                        "rationale",

                        "",

                    )

                )



                target = (

                    root

                    / change["path"]

                ).resolve()



                if target.is_file():



                    st.code(

                        read(target),

                        language=(

                            target.suffix.lstrip(".")

                            or "text"

                        ),

                    )



        # ----------------------------------------------------

        # VALIDATION

        # ----------------------------------------------------



        st.subheader(

            "3. Validation"

        )



        st.markdown(

            "**Baseline collection**"

        )



        st.code(

            result.baseline_collection

            or "Not applicable"

        )



        st.code(

            result.command

        )



        if result.passed:



            st.success(

                "Validation passed and "

                "safety checks passed."

            )



        else:



            st.error(

                "Validation did not establish "

                "a safe full-suite success."

            )



        st.code(

            result.output

            or "No validation output.",

            language="text",

        )



        st.write(

            f"Repair rounds used: "

            f"{result.repairs}/"

            f"{MAX_REPAIRS}"

        )



        # ----------------------------------------------------

        # DIFF

        # ----------------------------------------------------



        st.subheader(

            "4. Diff"

        )



        st.code(

            result.diff

            or "No file diff detected.",

            language="diff",

        )



        # ----------------------------------------------------

        # FINAL

        # ----------------------------------------------------



        st.subheader(

            "5. Final status"

        )



        if result.passed:



            st.success(

                "End-to-end flow completed successfully."

            )



        else:



            st.warning(

                "Review the diff and validation output. "

                "No success claim was made."

            )



        # ----------------------------------------------------

        # DOWNLOAD

        # ----------------------------------------------------



        st.download_button(

            "⬇️ Download modified project",

            data=zip_result(root),

            file_name="coding-agent-result.zip",

            mime="application/zip",

            use_container_width=True,

        )



    except Exception as exc:



        status.update(

            label="Coding agent stopped safely",

            state="error",

            expanded=False,

        )



        st.error(

            str(exc)

        )



        st.info(

            "No success claim is made when a "

            "safety, planning, or validation "

            "check fails."

        )





if __name__ == "__main__":

    main()
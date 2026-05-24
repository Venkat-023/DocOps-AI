import re
from typing import Any, Dict, Iterable, List

from github import Github, GithubException, RateLimitExceededException

from api.config import settings
from api.utils.language_detect import detect_language

GITHUB_URL_PATTERN = re.compile(
    r"^(?:https?://)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)"
    r"(?P<tail>/.*)?$"
)

REPO_SCAN_EXTENSIONS = {
    ".py",
    ".ipynb",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".rs",
    ".rb",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".yaml",
    ".yml",
    ".json",
}
REPO_SCAN_EXCLUDED_PARTS = {
    ".git",
    ".github",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    "data",
    "results",
    "outputs",
}


class GitHubRateLimitError(RuntimeError):
    pass


class GitHubUnavailableError(RuntimeError):
    pass


def _parse_github_url(url: str) -> Dict[str, Any]:
    cleaned = url.strip().rstrip("/")
    match = GITHUB_URL_PATTERN.match(cleaned)
    if not match:
        raise ValueError(
            "Cannot parse GitHub URL. Paste a direct file URL like "
            "github.com/owner/repo/blob/main/file.py"
        )

    tail = match.group("tail") or ""
    parts = [part for part in tail.split("/") if part]
    parsed = {
        "owner": match.group("owner"),
        "repo": match.group("repo").removesuffix(".git"),
        "branch": None,
        "path": None,
        "pr": None,
    }

    if len(parts) >= 2 and parts[0] == "pull":
        parsed["pr"] = int(parts[1])
        return parsed

    if len(parts) >= 3 and parts[0] == "blob":
        parsed["branch"] = parts[1]
        parsed["path"] = "/".join(parts[2:])
        return parsed

    if not parts:
        return parsed

    raise ValueError(
        "Cannot parse GitHub URL. Paste a direct file URL like "
        "github.com/owner/repo/blob/main/file.py"
    )


async def fetch_github_content(url: str) -> dict:
    parsed = _parse_github_url(url)
    client = Github(settings.github_token) if settings.github_token else Github()

    try:
        repo = client.get_repo(f"{parsed['owner']}/{parsed['repo']}")
        if parsed["pr"]:
            return await _fetch_pr_diff(repo, parsed["pr"])
        if parsed["path"]:
            return await _fetch_single_file(repo, parsed["path"], parsed["branch"] or "main")
        return await _fetch_repo_overview(repo)
    except RateLimitExceededException as exc:
        raise GitHubRateLimitError("Rate limit hit. Wait 30 seconds and retry.") from exc
    except GithubException as exc:
        if exc.status == 404:
            raise ValueError(
                "Cannot parse GitHub URL. Paste a direct file URL like "
                "github.com/owner/repo/blob/main/file.py"
            ) from exc
        raise GitHubUnavailableError("Could not reach GitHub. Check the URL and try again.") from exc


async def _fetch_single_file(repo, path: str, branch: str) -> dict:
    file_content = repo.get_contents(path, ref=branch)
    if isinstance(file_content, list):
        raise ValueError(
            "Cannot parse GitHub URL. Paste a direct file URL like "
            "github.com/owner/repo/blob/main/file.py"
        )

    content = file_content.decoded_content.decode("utf-8", errors="replace")
    return {
        "content": content,
        "file_path": path,
        "language": detect_language(path),
        "is_pr": False,
        "pr_diff": None,
    }


async def _fetch_pr_diff(repo, pr_number: int) -> dict:
    pr = repo.get_pull(pr_number)
    diff_parts = []

    for changed_file in pr.get_files():
        if changed_file.patch:
            diff_parts.append(f"### {changed_file.filename}\n{changed_file.patch}")

    return {
        "content": "\n\n".join(diff_parts),
        "file_path": f"PR #{pr_number}: {pr.title}",
        "language": "diff",
        "is_pr": True,
        "pr_diff": pr.body,
    }


async def _fetch_repo_overview(repo) -> dict:
    branch = repo.default_branch or "main"
    tree_items = _repo_tree_items(repo, branch)
    tree = "\n".join(f"{item['type']} {item['path']}" for item in tree_items[:120])
    try:
        readme = repo.get_readme()
        readme_text = readme.decoded_content.decode("utf-8", errors="replace")
    except GithubException:
        readme_text = f"# {repo.full_name}\n\nNo README found."

    content = _build_repo_scan_content(repo, branch, readme_text, tree, tree_items)

    return {
        "content": content,
        "file_path": "README.md + repository scan",
        "language": "markdown",
        "is_pr": False,
        "pr_diff": None,
    }


def _repo_tree_items(repo, branch: str) -> List[Dict[str, str]]:
    try:
        git_tree = repo.get_git_tree(branch, recursive=True)
        return [
            {"path": item.path, "type": item.type}
            for item in git_tree.tree
            if item.path and not _is_excluded_path(item.path)
        ]
    except GithubException:
        root_items = repo.get_contents("", ref=branch)
        return [
            {"path": item.path, "type": item.type}
            for item in root_items
            if not _is_excluded_path(item.path)
        ]


def _is_excluded_path(path: str) -> bool:
    parts = set(path.split("/"))
    return bool(parts & REPO_SCAN_EXCLUDED_PARTS)


def _candidate_source_files(tree_items: Iterable[Dict[str, str]]) -> List[str]:
    files = [item["path"] for item in tree_items if item["type"] == "blob"]

    def score(path: str) -> tuple[int, int, str]:
        lower = path.lower()
        ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
        priority = 10
        if lower.endswith("requirements.txt") or lower.endswith("pyproject.toml"):
            priority = 0
        elif lower.startswith(("src/", "api/", "app/", "backend/", "frontend/")):
            priority = 1
        elif lower.startswith(("notebook", "notebooks")) or ext == ".ipynb":
            priority = 2
        elif ext in REPO_SCAN_EXTENSIONS:
            priority = 3
        return (priority, len(path), path)

    return [
        path
        for path in sorted(files, key=score)
        if _has_supported_extension(path) or path.lower().endswith(("requirements.txt", "pyproject.toml"))
    ][:10]


def _has_supported_extension(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in REPO_SCAN_EXTENSIONS)


def _build_repo_scan_content(repo, branch: str, readme_text: str, tree: str, tree_items: List[Dict[str, str]]) -> str:
    max_lines = max(200, min(settings.max_file_size_lines - 30, 760))
    sections = [
        _truncate_lines(readme_text, 280),
        "## Repository tree",
        tree,
    ]
    used_lines = sum(len(section.splitlines()) for section in sections)
    snippets = []

    for path in _candidate_source_files(tree_items):
        if used_lines >= max_lines:
            break
        snippet = _read_repo_file_snippet(repo, path, branch, max_lines - used_lines)
        if not snippet:
            continue
        snippets.append(snippet)
        used_lines += len(snippet.splitlines())

    if snippets:
        sections.extend(["## Scanned repository files", *snippets])

    return "\n\n".join(sections)


def _read_repo_file_snippet(repo, path: str, branch: str, remaining_lines: int) -> str:
    if remaining_lines < 20:
        return ""
    try:
        contents = repo.get_contents(path, ref=branch)
    except GithubException:
        return ""
    if isinstance(contents, list) or not getattr(contents, "decoded_content", None):
        return ""

    text = contents.decoded_content.decode("utf-8", errors="replace")
    if "\x00" in text:
        return ""

    line_limit = min(80, max(20, remaining_lines - 8))
    body = _truncate_lines(text, line_limit)
    language = detect_language(path)
    fence_language = language if language != "unknown" else ""
    return f"### File: {path}\n\n```{fence_language}\n{body}\n```"


def _truncate_lines(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines] + [f"... truncated {len(lines) - max_lines} lines ..."])

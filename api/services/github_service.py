import re
from typing import Any, Dict

from github import Github, GithubException, RateLimitExceededException

from api.config import settings
from api.utils.language_detect import detect_language

GITHUB_URL_PATTERN = re.compile(
    r"^(?:https?://)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)"
    r"(?P<tail>/.*)?$"
)


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
    readme = repo.get_readme()
    root_items = repo.get_contents("")
    tree = "\n".join(
        f"{'dir ' if item.type == 'dir' else 'file'} {item.path}" for item in root_items[:80]
    )
    content = f"{readme.decoded_content.decode('utf-8', errors='replace')}\n\n## Repository tree\n{tree}"

    return {
        "content": content,
        "file_path": "README.md + repository tree",
        "language": "markdown",
        "is_pr": False,
        "pr_diff": None,
    }

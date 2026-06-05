"""GitHub scraper: commits, releases, stars, contributor growth."""
import structlog

from agents.scraper.base import BaseScraperAgent
from core.config import get_settings

log = structlog.get_logger()

GH_API = "https://api.github.com"


class GitHubSubAgent(BaseScraperAgent):
    name = "github"

    async def _headers(self) -> dict:
        token = get_settings().github_token
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    async def fetch(self, config: dict) -> list[dict]:
        """config keys: repo (str) or org (str)."""
        results: list[dict] = []
        headers = await self._headers()

        repo = config.get("repo")
        org = config.get("org")

        if repo:
            results += await self._fetch_repo(repo, headers)
        elif org:
            results += await self._fetch_org(org, headers)

        return results

    async def _fetch_repo(self, repo: str, headers: dict) -> list[dict]:
        items: list[dict] = []

        # Releases
        try:
            resp = await self.get(f"{GH_API}/repos/{repo}/releases", headers=headers, params={"per_page": 10})
            for r in resp.json():
                items.append({
                    "type": "release",
                    "title": r.get("name") or r.get("tag_name", ""),
                    "url": r.get("html_url", ""),
                    "date": r.get("published_at", "")[:10] if r.get("published_at") else None,
                    "body": (r.get("body") or "")[:1000],
                    "repo": repo,
                })
        except Exception as e:
            log.warning("github_releases_failed", repo=repo, error=str(e))

        # Recent commits (default branch)
        try:
            resp = await self.get(f"{GH_API}/repos/{repo}/commits", headers=headers, params={"per_page": 20})
            for c in resp.json():
                commit = c.get("commit", {})
                items.append({
                    "type": "commit",
                    "title": commit.get("message", "").split("\n")[0][:200],
                    "url": c.get("html_url", ""),
                    "date": (commit.get("author") or {}).get("date", "")[:10],
                    "repo": repo,
                })
        except Exception as e:
            log.warning("github_commits_failed", repo=repo, error=str(e))

        # Repo metadata (stars, forks)
        try:
            resp = await self.get(f"{GH_API}/repos/{repo}", headers=headers)
            meta = resp.json()
            items.append({
                "type": "repo_stats",
                "title": f"{repo} stats",
                "url": meta.get("html_url", ""),
                "stars": meta.get("stargazers_count", 0),
                "forks": meta.get("forks_count", 0),
                "open_issues": meta.get("open_issues_count", 0),
                "repo": repo,
            })
        except Exception as e:
            log.warning("github_repo_meta_failed", repo=repo, error=str(e))

        return items

    async def _fetch_org(self, org: str, headers: dict) -> list[dict]:
        items: list[dict] = []
        try:
            resp = await self.get(f"{GH_API}/orgs/{org}/repos", headers=headers, params={"per_page": 10, "sort": "updated"})
            for r in resp.json():
                items.append({
                    "type": "org_repo",
                    "title": r.get("full_name", ""),
                    "url": r.get("html_url", ""),
                    "description": r.get("description", "") or "",
                    "stars": r.get("stargazers_count", 0),
                    "org": org,
                })
        except Exception as e:
            log.warning("github_org_failed", org=org, error=str(e))
        return items

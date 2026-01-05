from __future__ import annotations

import os
from django.http import JsonResponse, HttpRequest
from django.template.loader import get_template


def _guess_git_sha() -> str:
    # Railway sometimes provides one of these; if not, we’ll still show "unknown"
    return (
        os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_COMMIT")
        or os.environ.get("COMMIT_SHA")
        or "unknown"
    )


def debug_status(request: HttpRequest) -> JsonResponse:
    """
    Browser-checkable endpoint so we can prove what code/templates are deployed.
    Safe: only returns a few strings, no secrets.
    """

    # Template origins (this is the same idea as your shell commands)
    tmpl_base = get_template("base.html").origin.name
    tmpl_header = get_template("includes/header.html").origin.name
    tmpl_footer = get_template("includes/footer.html").origin.name
    tmpl_home = get_template("board/home.html").origin.name
    tmpl_job_list = get_template("board/job_list.html").origin.name

    return JsonResponse(
        {
            "git_sha_env": _guess_git_sha(),
            "templates": {
                "base.html": tmpl_base,
                "includes/header.html": tmpl_header,
                "includes/footer.html": tmpl_footer,
                "board/home.html": tmpl_home,
                "board/job_list.html": tmpl_job_list,
            },
        }
    )

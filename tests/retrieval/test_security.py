from __future__ import annotations

import pytest

from app.retrieval.security import RetrievalSecurityError, validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://www.cninfo.com.cn/admin",
        "https://127.0.0.1/admin",
        "https://169.254.169.254/latest/meta-data",
        "https://10.0.0.8/internal",
    ],
)
def test_private_or_insecure_targets_are_rejected(url):
    with pytest.raises(RetrievalSecurityError):
        validate_public_url(url, allowed_hosts={"www.cninfo.com.cn"})


def test_unlisted_host_is_rejected():
    with pytest.raises(RetrievalSecurityError, match="not allowlisted"):
        validate_public_url("https://example.com/article", allowed_hosts={"www.cninfo.com.cn"})


def test_cninfo_https_url_is_accepted(monkeypatch):
    monkeypatch.setattr(
        "app.retrieval.security.resolve_host_ips",
        lambda _host: ["1.1.1.1"],
    )
    assert validate_public_url(
        "https://static.cninfo.com.cn/finalpage/report.pdf",
        allowed_hosts={"www.cninfo.com.cn", "static.cninfo.com.cn"},
    ).hostname == "static.cninfo.com.cn"

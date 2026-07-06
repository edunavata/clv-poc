import pytest
import requests

from client.odds_api import OddsApiClient, OddsApiError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "test-key")
    return OddsApiClient()


@pytest.mark.parametrize(
    ("bookmakers", "markets", "expected_cost"),
    [
        (["pinnacle"], ["h2h"], 1),
        (["pinnacle", "bet365"], ["h2h"], 1),
        ([f"book{i}" for i in range(10)], ["h2h"], 1),
        ([f"book{i}" for i in range(11)], ["h2h"], 2),
        (["pinnacle"], ["h2h", "spreads"], 2),
    ],
)
def test_get_odds_dry_run_estimates_cost_without_network_call(
    client, bookmakers, markets, expected_cost
):
    result = client.get_odds("soccer_fifa_world_cup", markets=markets, bookmakers=bookmakers)

    assert result["dry_run"] is True
    assert result["estimated_cost"] == expected_cost


def test_get_odds_dry_run_is_the_default(client):
    result = client.get_odds("soccer_fifa_world_cup", markets=["h2h"], bookmakers=["pinnacle"])

    assert result["dry_run"] is True


def test_get_usage_reads_quota_headers(client, monkeypatch):
    class Response:
        ok = True
        status_code = 200
        text = "ok"
        headers = {
            "x-requests-remaining": "498",
            "x-requests-used": "2",
            "x-requests-last": "0",
        }

    def fake_get(url, params, timeout):
        assert url.endswith("/sports")
        assert params == {"apiKey": "test-key"}
        assert timeout == 10
        return Response()

    monkeypatch.setattr("client.odds_api.requests.get", fake_get)

    assert client.get_usage() == {
        "remaining": "498",
        "used": "2",
        "last": "0",
    }


def test_network_errors_do_not_expose_api_key(client, monkeypatch):
    def fake_get(url, params, timeout):
        raise requests.ConnectionError(f"failed: {url}?apiKey={params['apiKey']}")

    monkeypatch.setattr("client.odds_api.requests.get", fake_get)

    with pytest.raises(OddsApiError) as exc_info:
        client.get_usage()

    assert "test-key" not in str(exc_info.value)

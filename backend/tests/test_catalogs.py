from app.config import settings
from app.services import catalog_search


class TMDbResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "results": [
                {
                    "id": 550,
                    "title": "Clube da Luta",
                    "original_title": "Fight Club",
                    "overview": "Um homem conhece Tyler Durden.",
                    "release_date": "1999-10-15",
                    "poster_path": "/poster.jpg",
                    "vote_average": 8.4,
                }
            ]
        }


class TicketmasterResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "_embedded": {
                "events": [
                    {
                        "id": "show-1",
                        "name": "Show de Teste",
                        "info": "Descrição do show",
                        "url": "https://ticketmaster.example/show-1",
                        "images": [
                            {"url": "https://img.example/small.jpg", "width": 100, "height": 50},
                            {"url": "https://img.example/large.jpg", "width": 1000, "height": 500},
                        ],
                        "dates": {
                            "start": {
                                "localDate": "2026-12-20",
                                "dateTime": "2026-12-20T22:00:00Z",
                            }
                        },
                        "_embedded": {
                            "venues": [
                                {
                                    "name": "Arena",
                                    "city": {"name": "São Paulo"},
                                    "state": {"name": "São Paulo"},
                                }
                            ]
                        },
                    }
                ]
            }
        }


def test_tmdb_catalog_maps_movie_overview_and_image(monkeypatch):
    captured = {}

    def fake_get(url, *, headers, params, timeout):
        captured.update(
            {"url": url, "headers": headers, "params": params, "timeout": timeout}
        )
        return TMDbResponse()

    monkeypatch.setattr(settings, "tmdb_api_key", "test-token")
    monkeypatch.setattr("app.services.httpx.get", fake_get)

    result = catalog_search("tmdb", "Clube da Luta")

    assert result["configured"] is True
    assert captured["headers"]["Authorization"] == "Bearer test-token"
    assert captured["params"]["language"] == "pt-BR"
    assert result["items"][0] == {
        "id": "550",
        "title": "Clube da Luta",
        "original_title": "Fight Club",
        "overview": "Um homem conhece Tyler Durden.",
        "date": "1999-10-15",
        "image": "https://image.tmdb.org/t/p/w500/poster.jpg",
        "vote_average": 8.4,
    }


def test_ticketmaster_catalog_maps_show_data(monkeypatch):
    captured = {}

    def fake_get(url, *, params, timeout):
        captured.update({"url": url, "params": params, "timeout": timeout})
        return TicketmasterResponse()

    monkeypatch.setattr(settings, "ticketmaster_api_key", "test-key")
    monkeypatch.setattr("app.services.httpx.get", fake_get)

    result = catalog_search("ticketmaster", "Show")

    assert result["configured"] is True
    assert captured["params"]["apikey"] == "test-key"
    assert captured["params"]["classificationName"] == "music"
    assert result["items"][0] == {
        "id": "show-1",
        "title": "Show de Teste",
        "overview": "Descrição do show",
        "date": "2026-12-20",
        "starts_at": "2026-12-20T22:00:00Z",
        "location": "Arena · São Paulo · São Paulo",
        "image": "https://img.example/large.jpg",
        "url": "https://ticketmaster.example/show-1",
    }


def test_ticketmaster_catalog_reports_missing_configuration(monkeypatch):
    monkeypatch.setattr(settings, "ticketmaster_api_key", None)

    result = catalog_search("ticketmaster", "Show")

    assert result == {
        "source": "ticketmaster",
        "configured": False,
        "items": [],
    }

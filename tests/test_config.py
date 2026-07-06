from config import Target, load_config

SAMPLE_YAML = """
storage:
  db_path: data/test.duckdb

min_remaining_credits: 20

targets:
  - name: world_cup_2026
    active: true
    sport_key: soccer_fifa_world_cup
    markets: [h2h]
    sharp_book: pinnacle
    soft_books: [williamhill, betvictor]
    poll_interval_hours: 3
  - name: mlb_2026
    active: false
    sport_key: baseball_mlb
    markets: [h2h]
    sharp_book: pinnacle
    soft_books: [fanduel]
    poll_interval_hours: 3
"""


def test_load_config_parses_targets(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(SAMPLE_YAML)

    config = load_config(config_path)

    assert config.db_path == "data/test.duckdb"
    assert config.min_remaining_credits == 20
    assert len(config.targets) == 2
    assert config.targets[0].sport_key == "soccer_fifa_world_cup"


def test_active_targets_filters_inactive(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(SAMPLE_YAML)

    config = load_config(config_path)
    active = config.active_targets()

    assert len(active) == 1
    assert active[0].name == "world_cup_2026"


def test_target_bookmakers_combines_sharp_and_soft():
    target = Target(
        name="x",
        active=True,
        sport_key="soccer_fifa_world_cup",
        markets=["h2h"],
        sharp_book="pinnacle",
        soft_books=["williamhill", "betvictor"],
        poll_interval_hours=3,
    )

    assert target.bookmakers == ["pinnacle", "williamhill", "betvictor"]

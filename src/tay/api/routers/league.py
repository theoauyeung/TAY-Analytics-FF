"""GET/POST /league/settings — persisted to data/league_settings.json."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter

from tay.api.schemas import LeagueSettingsSchema

router = APIRouter(prefix='/league', tags=['league'])

SETTINGS_PATH: Path = Path(__file__).resolve().parent.parent.parent.parent.parent / 'data' / 'league_settings.json'

_DEFAULT = LeagueSettingsSchema()


@router.get('/settings', response_model=LeagueSettingsSchema)
def get_league_settings() -> LeagueSettingsSchema:
    if not SETTINGS_PATH.exists():
        return _DEFAULT
    data = json.loads(SETTINGS_PATH.read_text())
    return LeagueSettingsSchema(**data)


@router.post('/settings')
def save_league_settings(body: LeagueSettingsSchema) -> dict:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(body.model_dump_json())
    return {'ok': True}

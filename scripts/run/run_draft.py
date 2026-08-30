"""CLI: print draft recommendation for a given pick and draft state."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from tay.db import get_conn, init_schema
from tay.draft.models import LeagueSettings, DraftState
from tay.draft.pipeline import run_draft_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description='TAY Draft Recommendation Engine')
    parser.add_argument('--season', type=int, default=2026)
    parser.add_argument('--model-version', default='neural-v1')
    parser.add_argument('--pick', type=int, default=1, help='Current overall pick (1-indexed)')
    parser.add_argument('--user-slot', type=int, default=1, help='User draft position (1-indexed)')
    args = parser.parse_args()

    conn = get_conn()
    init_schema(conn)

    state = DraftState(
        season=args.season,
        model_version=args.model_version,
        league_settings=LeagueSettings(),
        current_pick=args.pick,
        total_picks=180,
        user_pick_position=args.user_slot,
        drafted_ids=[],
        user_roster={'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )

    print(f'=== TAY Draft Engine — Season {args.season}, Pick {args.pick} ===')
    result = run_draft_pipeline(conn, state)

    top = result.top_pick
    print(f'\nTOP RECOMMENDATION: {top.player.name} ({top.player.position}, {top.player.team})')
    print(f'  Draft Score: {top.draft_score:.1f}')
    print(f'  VOR: {top.player.vor:.1f} | Sim Mean: {top.player.sim_mean:.1f}')
    print(f'  ADP: {top.player.adp:.1f} | Tier: {top.player.tier}')
    print(f'  Roster Fit: {top.roster_fit:.2f} | Positional Urgency: {top.positional_urgency:.2f}')
    print(f'  Future Availability: {top.future_availability_pct:.0%}')
    print(f'  Why: {"; ".join(top.explanation)}')

    print('\nALTERNATIVES:')
    for alt in result.alternatives:
        print(f'  {alt.player.name} ({alt.player.position}) — score {alt.draft_score:.1f}')

    if result.may_not_make_it_back:
        print('\nMAY NOT MAKE IT BACK:')
        for p in result.may_not_make_it_back:
            print(f'  {p.name} ({p.position}) — ADP {p.adp:.0f}')

    print(f'\nPOSITIONAL NEEDS (by urgency): {", ".join(result.positional_needs)}')
    print(f'Round {result.board_state["round"]} | {result.board_state["picks_until_next"]} picks until next turn')
    conn.close()


if __name__ == '__main__':
    main()

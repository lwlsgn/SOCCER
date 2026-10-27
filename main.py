import os
import json
from datetime import date
from typing import Any

import pandas as pd
import requests
import streamlit as st

# ------------------------------------------------------------
# My Football Squad - first working version
# Data provider: API-FOOTBALL (API-Sports)
# Configure Streamlit Cloud:
# App -> Settings -> Secrets
# API_FOOTBALL_KEY = "your_api_key"
# ------------------------------------------------------------

st.set_page_config(
    page_title="My Football Squad",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = "https://v3.football.api-sports.io"
LEAGUES = {
    "Premier League (England)": 39,
    "La Liga (Spain)": 140,
    "Serie A (Italy)": 135,
    "Bundesliga (Germany)": 78,
    "Ligue 1 (France)": 61,
    "MLS (USA)": 253,
}
FORMATIONS = {
    "4-3-3": [
        ("LW", 17, 22), ("ST", 50, 15), ("RW", 83, 22),
        ("CM-L", 30, 43), ("CM", 50, 39), ("CM-R", 70, 43),
        ("LB", 15, 66), ("CB-L", 38, 69), ("CB-R", 62, 69), ("RB", 85, 66),
        ("GK", 50, 89),
    ],
    "4-2-3-1": [
        ("ST", 50, 14),
        ("LAM", 22, 31), ("CAM", 50, 29), ("RAM", 78, 31),
        ("DM-L", 38, 46), ("DM-R", 62, 46),
        ("LB", 15, 67), ("CB-L", 38, 70), ("CB-R", 62, 70), ("RB", 85, 67),
        ("GK", 50, 89),
    ],
    "4-4-2": [
        ("ST-L", 38, 17), ("ST-R", 62, 17),
        ("LM", 15, 40), ("CM-L", 39, 45), ("CM-R", 61, 45), ("RM", 85, 40),
        ("LB", 15, 67), ("CB-L", 38, 70), ("CB-R", 62, 70), ("RB", 85, 67),
        ("GK", 50, 89),
    ],
}

POSITION_TRANSLATIONS = {
    "Goalkeeper": "GK",
    "Defender": "DF",
    "Midfielder": "MF",
    "Attacker": "FW",
}


def get_api_key() -> str:
    """Read API key from Streamlit secrets or environment variable."""
    try:
        key = st.secrets.get("API_FOOTBALL_KEY", "")
        if key:
            return str(key).strip()
    except Exception:
        # A local secrets.toml file is optional during initial setup.
        pass
    return os.getenv("API_FOOTBALL_KEY", "").strip()


@st.cache_data(ttl=3600, show_spinner=False)
def search_players(api_key: str, league_id: int, season: int, query: str) -> list[dict[str, Any]]:
    """Search player profiles/statistics in a league and season."""
    response = requests.get(
        f"{API_BASE_URL}/players",
        headers={"x-apisports-key": api_key},
        params={"league": league_id, "season": season, "search": query},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()

    errors = payload.get("errors")
    if errors:
        raise RuntimeError(f"API 응답 오류: {errors}")

    return payload.get("response", [])


def normalize_player(item: dict[str, Any]) -> dict[str, Any]:
    """Convert API-Football's response into the app's internal player schema."""
    player = item.get("player", {}) or {}
    statistics = item.get("statistics", []) or []
    stat = statistics[0] if statistics else {}
    team = stat.get("team", {}) or {}
    league = stat.get("league", {}) or {}
    games = stat.get("games", {}) or {}
    goals = stat.get("goals", {}) or {}
    cards = stat.get("cards", {}) or {}

    return {
        "player_id": player.get("id"),
        "name": player.get("name") or "Unknown",
        "age": player.get("age"),
        "nationality": player.get("nationality") or "정보 없음",
        "position": player.get("position") or "정보 없음",
        "club": team.get("name") or "정보 없음",
        "league": league.get("name") or "정보 없음",
        "appearances": games.get("appearences"),
        "goals": goals.get("total"),
        "assists": goals.get("assists"),
        "yellow_cards": cards.get("yellow"),
        "photo_url": player.get("photo"),
        "season": league.get("season"),
        "data_source": "API-FOOTBALL",
        "last_updated": date.today().isoformat(),
    }


def player_label(player: dict[str, Any]) -> str:
    return f'{player["name"]} · {player["club"]} · {player["position"]}'


def init_state() -> None:
    defaults = {
        "squad_name": "My Dream Team",
        "formation": "4-3-3",
        "starting_xi": {},
        "bench": [],
        "last_search_results": [],
        "known_players": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def player_by_id(players: list[dict[str, Any]], player_id: int) -> dict[str, Any] | None:
    for player in players:
        if player.get("player_id") == player_id:
            return player
    return None


def render_pitch(formation: str, starting_xi: dict[str, int], player_index: dict[int, dict[str, Any]]) -> None:
    """Render a responsive-looking pitch with player labels using HTML/CSS."""
    slots = FORMATIONS[formation]
    player_nodes = []
    for slot, x, y in slots:
        player = player_index.get(starting_xi.get(slot))
        if player:
            name = player["name"]
            # Keep HTML safe if an API field contains special characters.
            import html
            safe_name = html.escape(name)
            safe_pos = html.escape(slot)
            content = (
                f'<div class="shirt">{safe_pos}</div>'
                f'<div class="player-name">{safe_name}</div>'
            )
        else:
            content = (
                f'<div class="shirt empty">{slot}</div>'
                '<div class="player-name empty-name">선수 선택</div>'
            )
        player_nodes.append(
            f'<div class="pitch-player" style="left:{x}%;top:{y}%;">{content}</div>'
        )

    html_doc = f"""
    <style>
      .pitch {{
        position: relative; width: 100%; min-height: 590px; overflow: hidden;
        border: 2px solid rgba(255,255,255,.75); border-radius: 14px;
        background:
          linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px),
          linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
          repeating-linear-gradient(0deg, #267348 0px, #267348 70px, #2c7d4e 70px, #2c7d4e 140px);
        background-size: 10% 100%, 100% 10%, 100% 100%;
      }}
      .pitch:before {{
        content:""; position:absolute; left:3%; right:3%; top:3%; bottom:3%;
        border:1.5px solid rgba(255,255,255,.65); border-radius:4px;
      }}
      .halfway {{
        position:absolute; left:3%; right:3%; top:50%; border-top:1.5px solid rgba(255,255,255,.65);
      }}
      .center-circle {{
        position:absolute; width:100px; height:100px; left:50%; top:50%;
        transform:translate(-50%,-50%); border:1.5px solid rgba(255,255,255,.65); border-radius:50%;
      }}
      .pitch-player {{
        position:absolute; transform:translate(-50%,-50%); width:88px;
        text-align:center; z-index:2; color:#fff; font-family:Arial,sans-serif;
      }}
      .shirt {{
        display:inline-flex; align-items:center; justify-content:center;
        width:36px; height:36px; border-radius:10px 10px 12px 12px;
        background:#f7f7f7; color:#183b2a; border:2px solid #d9f99d;
        font-size:10px; font-weight:800; box-shadow:0 2px 8px #0005;
      }}
      .shirt.empty {{ background:#173e2b; color:#e7f6eb; border:1.5px dashed #d9f99d; }}
      .player-name {{
        margin-top:3px; padding:2px 4px; border-radius:4px;
        background:rgba(8,28,18,.78); font-size:10px; font-weight:700;
        white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
      }}
      .empty-name {{ color:#e5e7eb; font-weight:500; }}
      @media(max-width:700px) {{
        .pitch {{ min-height:520px; }}
        .pitch-player {{ width:65px; }}
        .shirt {{ width:30px; height:30px; }}
        .player-name {{ font-size:8px; }}
        .center-circle {{ width:70px; height:70px; }}
      }}
    </style>
    <div class="pitch">
      <div class="halfway"></div><div class="center-circle"></div>
      {''.join(player_nodes)}
    </div>
    """
    st.components.v1.html(html_doc, height=610, scrolling=False)


# ------------------------------ UI ------------------------------
init_state()

st.title("⚽ My Football Squad")
st.caption("실제 축구 선수 데이터를 검색하고 나만의 스쿼드를 구성하세요.")


with st.sidebar:
    st.header("⚙️ 설정")
    api_key = get_api_key()

    if api_key:
        st.success("API 키가 설정되어 있습니다.")
    else:
        st.warning("API 키가 설정되지 않았습니다.")
        st.markdown(
            "Streamlit Cloud의 **Settings → Secrets**에 다음 항목을 추가하세요."
        )
        st.code(
            'API_FOOTBALL_KEY = "발급받은_API_키"',
            language="toml",
        )
        st.markdown(
            "[API-FOOTBALL 공식 사이트](https://www.api-football.com/)"
        )

    league_name = st.selectbox(
        "리그",
        list(LEAGUES.keys()),
    )

    # 무료 API 플랜에서 접근 가능한 시즌
    available_seasons = [2024, 2023, 2022]

    season = st.selectbox(
        "시즌 시작 연도",
        available_seasons,
        index=0,
    )

    st.caption(
        "무료 API 플랜에서는 2022~2024 시즌을 선택하세요."
    )

    st.session_state["formation"] = st.selectbox(
        "포메이션",
        list(FORMATIONS.keys()),
        index=list(FORMATIONS.keys()).index(
            st.session_state["formation"]
        ),
    )

search_col, info_col = st.columns([2, 1])

with search_col:
    st.subheader("🔎 선수 검색")
    with st.form("player_search_form"):
        query = st.text_input(
            "선수 이름 (영문 3글자 이상 권장)",
            placeholder="예: Salah, Son, Haaland",
        ).strip()
        submitted = st.form_submit_button("선수 검색", type="primary", use_container_width=True)

    if submitted:
        if not api_key:
            st.error("먼저 API_FOOTBALL_KEY를 설정해 주세요.")
        elif len(query) < 3:
            st.warning("검색어를 3글자 이상 입력해 주세요.")
        else:
            try:
                with st.spinner("실제 선수 데이터를 불러오는 중..."):
                    raw_results = search_players(api_key, LEAGUES[league_name], int(season), query)
                    normalized = [normalize_player(item) for item in raw_results]
                    # API can return the same player in multiple team/stat rows.
                    deduped = {}
                    for player in normalized:
                        pid = player.get("player_id")
                        if pid is not None and pid not in deduped:
                            deduped[pid] = player
                    st.session_state["last_search_results"] = list(deduped.values())
                    for player in deduped.values():
                        st.session_state["known_players"][player["player_id"]] = player
                if not st.session_state["last_search_results"]:
                    st.info("검색 결과가 없습니다. 영문 이름이나 리그·시즌을 바꿔 보세요.")
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                st.error(f"API 요청에 실패했습니다 (HTTP {status}). API 키, 요금제, 리그 및 시즌을 확인해 주세요.")
            except requests.RequestException as exc:
                st.error(f"네트워크 오류가 발생했습니다: {exc}")
            except (ValueError, RuntimeError) as exc:
                st.error(f"선수 데이터를 처리하지 못했습니다: {exc}")

    results = st.session_state["last_search_results"]
    if results:
        st.markdown(f"검색 결과 **{len(results)}명**")
        option_map = {player_label(p): p["player_id"] for p in results}
        selected_label = st.selectbox("선수 선택", list(option_map.keys()))
        selected_id = option_map[selected_label]
        selected_player = player_by_id(results, selected_id)

        if selected_player:
            card_col, details_col = st.columns([1, 2])
            with card_col:
                if selected_player.get("photo_url"):
                    st.image(selected_player["photo_url"], width=130)
                else:
                    st.markdown("👤")
            with details_col:
                st.markdown(f"### {selected_player['name']}")
                st.write(f"**구단:** {selected_player['club']}")
                st.write(f"**포지션:** {selected_player['position']}")
                st.write(f"**국적:** {selected_player['nationality']}")
                st.write(f"**나이:** {selected_player['age'] or '정보 없음'}")
                st.caption(
                    f"출전 {selected_player['appearances'] if selected_player['appearances'] is not None else '—'} · "
                    f"골 {selected_player['goals'] if selected_player['goals'] is not None else '—'} · "
                    f"도움 {selected_player['assists'] if selected_player['assists'] is not None else '—'}"
                )

            with st.form("add_player_form"):
                slot_labels = [f"{slot} 포지션" for slot, _, _ in FORMATIONS[st.session_state["formation"]]]
                slot_values = [slot for slot, _, _ in FORMATIONS[st.session_state["formation"]]]
                slot = st.selectbox("배치할 선발 포지션", slot_values)
                add_to_bench = st.checkbox("후보 선수로 추가")
                add_clicked = st.form_submit_button("스쿼드에 추가", use_container_width=True)

            if add_clicked:
                pid = selected_player["player_id"]
                current_starting = st.session_state["starting_xi"]
                in_starting = pid in current_starting.values()
                in_bench = any(p["player_id"] == pid for p in st.session_state["bench"])
                if in_starting or in_bench:
                    st.warning("이미 스쿼드에 포함된 선수입니다.")
                elif add_to_bench:
                    st.session_state["bench"].append(selected_player)
                    st.success(f"{selected_player['name']} 선수를 후보에 추가했습니다.")
                    st.rerun()
                else:
                    existing_pid = current_starting.get(slot)
                    current_starting[slot] = pid
                    if existing_pid is not None and existing_pid != pid:
                        st.info("해당 포지션의 선수를 교체했습니다.")
                    st.session_state["starting_xi"] = current_starting
                    st.session_state["known_players"][pid] = selected_player
                    st.success(f"{selected_player['name']} 선수를 {slot}에 배치했습니다.")
                    st.rerun()

with info_col:
    st.subheader("📋 구성 현황")
    st.metric("선발 배치", f"{len(st.session_state['starting_xi'])} / 11")
    st.metric("후보 선수", len(st.session_state["bench"]))
    st.metric("포메이션", st.session_state["formation"])
    if len(st.session_state["starting_xi"]) < 11:
        st.progress(len(st.session_state["starting_xi"]) / 11, text="선발 11명 구성 진행률")
    else:
        st.success("선발 11명이 모두 배치되었습니다.")

st.divider()
st.subheader("🏟️ 전술 보드")
st.caption("각 포지션의 선수는 왼쪽 검색 영역에서 선택해 배치할 수 있습니다. 이 버전은 클릭·선택 방식이며 드래그 앤 드롭은 아직 지원하지 않습니다.")

all_known_players = dict(st.session_state["known_players"])
all_known_players.update({p["player_id"]: p for p in st.session_state["last_search_results"] if p.get("player_id") is not None})
for p in st.session_state["bench"]:
    all_known_players[p["player_id"]] = p

# Players already selected are kept in session state even if a later search changes.
render_pitch(st.session_state["formation"], st.session_state["starting_xi"], all_known_players)

# Show lineup table and allow removing players.
st.subheader("👥 선발 명단")
formation_slots = [slot for slot, _, _ in FORMATIONS[st.session_state["formation"]]]
lineup_rows = []
for slot in formation_slots:
    pid = st.session_state["starting_xi"].get(slot)
    player = all_known_players.get(pid)
    lineup_rows.append({
        "포지션": slot,
        "선수": player["name"] if player else ("선수 정보가 현재 검색 결과에 없습니다" if pid else "미배치"),
        "구단": player["club"] if player else "—",
        "국적": player["nationality"] if player else "—",
        "player_id": pid,
    })

lineup_df = pd.DataFrame(lineup_rows)
st.dataframe(lineup_df.drop(columns=["player_id"]), use_container_width=True, hide_index=True)

occupied_slots = [slot for slot in formation_slots if st.session_state["starting_xi"].get(slot) is not None]
if occupied_slots:
    with st.form("remove_player_form"):
        slot_to_remove = st.selectbox("선발에서 제외할 포지션", occupied_slots)
        remove_clicked = st.form_submit_button("선수 배치 해제")
    if remove_clicked:
        st.session_state["starting_xi"].pop(slot_to_remove, None)
        st.rerun()

st.subheader("🪑 후보 선수")
if st.session_state["bench"]:
    bench_df = pd.DataFrame([
        {
            "선수": p["name"],
            "구단": p["club"],
            "포지션": p["position"],
            "국적": p["nationality"],
            "player_id": p["player_id"],
        }
        for p in st.session_state["bench"]
    ])
    st.dataframe(bench_df.drop(columns=["player_id"]), use_container_width=True, hide_index=True)
    bench_options = {f'{p["name"]} · {p["club"]}': p["player_id"] for p in st.session_state["bench"]}
    with st.form("remove_bench_form"):
        bench_to_remove = st.selectbox("후보에서 제외할 선수", list(bench_options.keys()))
        remove_bench_clicked = st.form_submit_button("후보에서 제외")
    if remove_bench_clicked:
        remove_id = bench_options[bench_to_remove]
        st.session_state["bench"] = [
            p for p in st.session_state["bench"] if p["player_id"] != remove_id
        ]
        st.rerun()
else:
    st.info("아직 후보 선수가 없습니다.")

# Save/load squad JSON. Player details are included to make the exported file portable.
st.divider()
st.subheader("💾 스쿼드 저장 및 불러오기")
export_players = {}
for pid in st.session_state["starting_xi"].values():
    if pid is not None and pid in all_known_players:
        export_players[str(pid)] = all_known_players[pid]

squad_payload = {
    "squad_name": st.session_state["squad_name"],
    "formation": st.session_state["formation"],
    "starting_xi": st.session_state["starting_xi"],
    "bench": st.session_state["bench"],
    "players": export_players,
    "exported_at": date.today().isoformat(),
    "data_source": "API-FOOTBALL",
}

save_col, load_col = st.columns(2)
with save_col:
    st.download_button(
        "⬇️ 스쿼드 JSON 다운로드",
        data=json.dumps(squad_payload, ensure_ascii=False, indent=2),
        file_name="my_football_squad.json",
        mime="application/json",
        use_container_width=True,
    )
with load_col:
    uploaded = st.file_uploader("저장한 스쿼드 JSON 불러오기", type=["json"])
    if uploaded is not None:
        if st.button("JSON 불러오기", use_container_width=True):
            try:
                loaded = json.load(uploaded)
                if not isinstance(loaded, dict) or "starting_xi" not in loaded:
                    raise ValueError("스쿼드 파일 형식이 올바르지 않습니다.")
                formation = loaded.get("formation", "4-3-3")
                if formation not in FORMATIONS:
                    formation = "4-3-3"
                st.session_state["squad_name"] = str(loaded.get("squad_name", "Imported Squad"))[:50]
                st.session_state["formation"] = formation
                st.session_state["starting_xi"] = {
                    str(k): (int(v) if v is not None else None)
                    for k, v in loaded.get("starting_xi", {}).items()
                    if k in [s[0] for s in FORMATIONS[formation]]
                }
                st.session_state["bench"] = loaded.get("bench", [])
                # Rebuild local player index from exported details so lineup remains visible.
                players_from_file = loaded.get("players", {})
                imported_players = []
                for value in players_from_file.values():
                    if isinstance(value, dict) and value.get("player_id") is not None:
                        imported_players.append(value)
                st.session_state["last_search_results"] = imported_players
                st.session_state["known_players"] = {p["player_id"]: p for p in imported_players}
                for player in st.session_state["bench"]:
                    if isinstance(player, dict) and player.get("player_id") is not None:
                        st.session_state["known_players"][player["player_id"]] = player
                st.success("스쿼드를 불러왔습니다.")
                st.rerun()
            except Exception as exc:
                st.error(f"파일을 불러오지 못했습니다: {exc}")

st.caption(
    "선수 프로필과 시즌 통계는 API-FOOTBALL에서 제공되는 범위에 따릅니다. "
    "이 버전은 기초 기능이며, API 요금제에 따라 검색 가능한 선수와 통계가 달라질 수 있습니다."
)

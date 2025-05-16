import streamlit as st
import requests
import pandas as pd
import io

st.title("MLB Game Inning Start/End Times")

# Input: GamePk(s) or file upload
game_pks_input = st.text_area(
    "Enter one or more GamePk (one per line), or upload a file below:",
    height=100
)
upload_file = st.file_uploader(
    "Or upload a CSV/TXT file with GamePk on each line:",
    type=["csv", "txt"]
)

# Button to trigger processing
if st.button("Get Info"):
    # Gather list of GamePks
    game_pks = []
    # From text area
    if game_pks_input:
        lines = game_pks_input.splitlines()
        game_pks.extend([line.strip() for line in lines if line.strip()])
    # From uploaded file
    if upload_file is not None:
        content = upload_file.read()
        try:
            text = content.decode('utf-8')
        except AttributeError:
            text = content
        file_lines = text.splitlines()
        game_pks.extend([line.strip() for line in file_lines if line.strip()])

    if not game_pks:
        st.error("Please provide at least one GamePk via text or file.")
    else:
        @st.cache_data
        def process_game(game_pk):
            """Fetch play-by-play data and compute inning start/end times."""
            url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/playByPlay"
            try:
                resp = requests.get(url)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                st.error(f"Error fetching data for game {game_pk}: {e}")
                return None

            plays = data.get('allPlays', [])
            times = {}
            for play in plays:
                about = play.get('about', {})
                inning = about.get('inning')
                half = about.get('halfInning')
                start = about.get('startTime')
                end = about.get('endTime')
                if inning is None or half is None or start is None or end is None:
                    continue
                key = (inning, half)
                if key not in times:
                    times[key] = {'start': start, 'end': end}
                else:
                    if start < times[key]['start']:
                        times[key]['start'] = start
                    if end > times[key]['end']:
                        times[key]['end'] = end

            rows = []
            for (inning, half), t in sorted(times.items()):
                rows.append({
                    'gamePk': game_pk,
                    'inning': inning,
                    'halfInning': half.title(),
                    'startTime': t['start'],
                    'endTime': t['end']
                })
            return pd.DataFrame(rows)

        # Process each game and collect results
        result_dfs = []
        for gp in game_pks:
            df = process_game(gp)
            if df is not None and not df.empty:
                result_dfs.append(df)

        if result_dfs:
            combined = pd.concat(result_dfs, ignore_index=True)
            st.dataframe(combined)
            # Single vs multiple export
            if len(result_dfs) == 1:
                csv_data = combined.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"{game_pks[0]}_innings_times.csv",
                    mime="text/csv"
                )
            else:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    combined.to_excel(writer, index=False, sheet_name='Innings')
                st.download_button(
                    label="Download Excel",
                    data=buffer.getvalue(),
                    file_name="innings_times.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("No data found for the provided GamePk(s).")
else:
    st.info("Enter GamePk(s) above and click 'Get Info' to retrieve inning times.")

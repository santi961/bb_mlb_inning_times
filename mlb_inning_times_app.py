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
    if game_pks_input:
        game_pks.extend([line.strip() for line in game_pks_input.splitlines() if line.strip()])
    if upload_file is not None:
        content = upload_file.read()
        try:
            text = content.decode("utf-8")
        except AttributeError:
            text = content
        game_pks.extend([line.strip() for line in text.splitlines() if line.strip()])

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

            plays = data.get("allPlays", [])
            times = {}
            for play in plays:
                about = play.get("about", {})
                inning = about.get("inning")
                half = about.get("halfInning")
                start = about.get("startTime")
                end = about.get("endTime")
                if inning is None or half is None or start is None or end is None:
                    continue
                key = (inning, half)
                if key not in times:
                    times[key] = {"start": start, "end": end}
                else:
                    if start < times[key]["start"]:
                        times[key]["start"] = start
                    if end > times[key]["end"]:
                        times[key]["end"] = end

            rows = []
            for (inning, half), t in times.items():
                rows.append({
                    "gamePk": game_pk,
                    "inning": inning,
                    "halfInning": half.title(),
                    "startTime": t["start"],
                    "endTime": t["end"],
                })
            return pd.DataFrame(rows)

        # Process each game and collect results
        result_data = []  # list of (gamePk, DataFrame)
        for gp in game_pks:
            df = process_game(gp)
            if df is not None and not df.empty:
                result_data.append((gp, df))

        # Sort games numerically by GamePk for preview and sheets
        try:
            result_data.sort(key=lambda x: int(x[0]))
        except ValueError:
            # fallback to string sort if non-numeric
            result_data.sort(key=lambda x: x[0])

        if result_data:
            # Preview each game separately if multiple
            if len(result_data) > 1:
                tabs = st.tabs([str(gp) for gp, _ in result_data])
                for tab, (gp, df) in zip(tabs, result_data):
                    with tab:
                        df2 = df.copy()
                        df2["InningHalf"] = df2["inning"].astype(str) + " " + df2["halfInning"]
                        df2["order"] = df2["halfInning"].map({"Top": 0, "Bottom": 1})
                        df2 = df2.sort_values(by=["inning", "order"]).reset_index(drop=True)
                        df2 = df2[["InningHalf", "startTime", "endTime"]]
                        st.dataframe(df2)
            else:
                # Single game preview
                gp, df = result_data[0]
                df2 = df.copy()
                df2["InningHalf"] = df2["inning"].astype(str) + " " + df2["halfInning"]
                df2["order"] = df2["halfInning"].map({"Top": 0, "Bottom": 1})
                df2 = df2.sort_values(by=["inning", "order"]).reset_index(drop=True)
                df2 = df2[["InningHalf", "startTime", "endTime"]]
                st.dataframe(df2)

            # Export to file
            if len(result_data) == 1:
                csv_data = df2.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"{gp}_innings_times.csv",
                    mime="text/csv",
                )
            else:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    for gp, df in result_data:
                        df3 = df.copy()
                        df3["InningHalf"] = df3["inning"].astype(str) + " " + df3["halfInning"]
                        df3["order"] = df3["halfInning"].map({"Top": 0, "Bottom": 1})
                        df3 = df3.sort_values(by=["inning", "order"]).reset_index(drop=True)
                        df3 = df3[["InningHalf", "startTime", "endTime"]]
                        df3.to_excel(writer, index=False, sheet_name=str(gp))
                st.download_button(
                    label="Download Excel",
                    data=buffer.getvalue(),
                    file_name="innings_times_by_game.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        else:
            st.info("No data found for the provided GamePk(s).")
else:
    st.info("Enter GamePk(s) above and click 'Get Info' to retrieve inning times.")

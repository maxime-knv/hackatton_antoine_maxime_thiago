# Graph Report - NFL_HACKATHON  (2026-10-21)

## Corpus Check
- Corpus is ~11,433 words - fits in a single context window. You may not need a graph.

## Summary
- 282 nodes · 690 edges · 10 communities (8 shown, 2 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Data Loading & Imports
- Plotting & Integration Tests
- Metrics Tests
- Streamlit App Core
- Evaluation Tests
- Calibration Script
- README Concepts & Verdicts
- App UI Tests
- NumPy
- Pandas

## God Nodes (most connected - your core abstractions)
1. `evaluate_decision()` - 26 edges
2. `PlayAnalysis` - 24 edges
3. `analyze_play()` - 17 edges
4. `analyze_game()` - 16 edges
5. `load_tables()` - 15 edges
6. `build_field_figure()` - 15 edges
7. `frame()` - 13 edges
8. `build_separation_figure()` - 13 edges
9. `key_events()` - 12 edges
10. `Tables` - 12 edges

## Surprising Connections (you probably didn't know these)
- `get_game()` --uses--> `GameAnalysis`  [INFERRED]
  app.py → tracker/analysis.py
- `Player` --uses--> `PlayAnalysis`  [INFERRED]
  app.py → tracker/analysis.py
- `event_rows()` --uses--> `PlayAnalysis`  [INFERRED]
  app.py → tracker/analysis.py
- `render_decisions()` --uses--> `GameAnalysis`  [INFERRED]
  app.py → tracker/analysis.py
- `render_decisions()` --uses--> `PlayAnalysis`  [INFERRED]
  app.py → tracker/analysis.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **QB decision grade levels** — readme_meilleur_coup, readme_bon_coup, readme_erreur, readme_gaffe [EXTRACTED 1.00]
- **YAC Potential model inputs** — readme_yac_potential, readme_separation, readme_space_ahead [EXTRACTED 1.00]
- **Python dependencies** — requirements_streamlit, requirements_pandas, requirements_numpy, requirements_plotly, requirements_pytest [EXTRACTED 1.00]

## Communities (10 total, 2 thin omitted)

### Community 0 - "Data Loading & Imports"
Cohesion: 0.07
Nodes (30): candidates(), test_build_play_tracking_splits_teams_and_finds_events(), test_find_targeted_receiver(), test_headshots_are_resized_and_missing_file_is_harmless(), test_incomplete_tracking_is_rejected(), test_load_tracking_rotates_left_plays_so_offence_always_goes_right(), test_name_variants_cover_nfl_description_styles(), test_placeholder_avatar_is_a_valid_svg_data_uri_with_initials() (+22 more)

### Community 1 - "Plotting & Integration Tests"
Cohesion: 0.09
Nodes (18): game(), tables(), test_field_orientation_matches_the_play_description(), test_figures_render_for_key_frames(), test_key_events_are_chronological_and_inside_the_tracking(), _clean(), key_events(), KeyEvent (+10 more)

### Community 2 - "Metrics Tests"
Cohesion: 0.09
Nodes (25): test_decision_matches_the_time_series(), _flight(), test_direct_defender_is_the_one_who_sticks(), test_estimate_landing_falls_back_to_the_receiver_when_data_is_too_short(), test_estimate_landing_meets_the_receiver(), test_estimate_landing_uses_observed_arrival(), test_nearest_to_point(), test_route_separations_one_value_per_receiver() (+17 more)

### Community 3 - "Streamlit App Core"
Cohesion: 0.09
Nodes (23): apply_filters(), available_options(), _bump_epoch(), event_rows(), facet_options(), get_game(), get_tables(), _goto() (+15 more)

### Community 4 - "Evaluation Tests"
Cohesion: 0.14
Nodes (19): frame(), test_an_interception_is_always_a_blunder(), test_an_open_running_back_is_not_a_primary_alternative(), test_blunder_takes_priority_over_mistake(), test_blunder_when_a_defender_already_sits_at_the_catch_point(), test_blunder_when_the_receiver_is_glued_to_a_defender(), test_covered_receiver_while_a_primary_receiver_is_open_is_a_mistake(), test_every_decision_has_a_short_comment_that_fits_a_table_cell() (+11 more)

### Community 5 - "Calibration Script"
Cohesion: 0.12
Nodes (6): audit_verdicts(), collect(), fit_yac(), main(), analyze_game(), GameAnalysis

### Community 6 - "README Concepts & Verdicts"
Cohesion: 0.13
Nodes (19): Big Data Bowl 2023 dataset, Bon coup, Evaluation de la decision du QB (Chess.com style), Erreur, Estimated reception point, Gaffe, Meilleur coup, nflverse headshots (+11 more)

### Community 7 - "App UI Tests"
Cohesion: 0.17
Nodes (3): app(), plays_in(), test_filters_narrow_the_action_list_and_cascade()

## Knowledge Gaps
- **11 isolated node(s):** `Espace devant le receveur`, `Meilleur coup`, `Bon coup`, `Erreur`, `Gaffe` (+6 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 97 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `evaluate_decision()` connect `Evaluation Tests` to `Plotting & Integration Tests`, `Metrics Tests`, `Calibration Script`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `PlayAnalysis` (e.g. with `event_rows()` and `Player`) actually correct?**
  _`PlayAnalysis` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Espace devant le receveur`, `Meilleur coup`, `Bon coup` to the rest of the system?**
  _11 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Data Loading & Imports` be split into smaller, more focused modules?**
  _Cohesion score 0.07474747474747474 - nodes in this community are weakly interconnected._
- **Why does `PlayAnalysis` connect `Plotting & Integration Tests` to `Data Loading & Imports`, `Metrics Tests`, `Streamlit App Core`, `Evaluation Tests`, `Calibration Script`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `analyze_play()` (e.g. with `Player` and `PlayTracking`) actually correct?**
  _`analyze_play()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `Plotting & Integration Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.0851063829787234 - nodes in this community are weakly interconnected._
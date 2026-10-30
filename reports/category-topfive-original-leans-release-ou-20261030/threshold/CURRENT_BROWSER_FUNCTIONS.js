function propFinal(g) {
  return g?.state === "post" && typeof g.detail === "string" && /^Final(?:\/\d*OT)?$/i.test(g.detail.trim());
}

function propPickBound(m, p, g) {
  const id = x => typeof x === "string" && Boolean(x.trim()) || Number.isSafeInteger(x) && x >= 0;
  return !!(m && p && g && m.schema_version === "mypicks-player-game-v1"
    && [m.pid, p.id, m.gid, p.game_id, g.id].every(id)
    && String(m.pid) === String(p.id) && String(m.gid) === String(p.game_id) && String(m.gid) === String(g.id)
    && m.season === S.data.season && m.week === S.data.week && m.team === p.team
    && (m.espn_id == null || id(m.espn_id) && id(p.espn_id) && String(m.espn_id) === String(p.espn_id))
    && typeof m.kickoff === "string" && Number.isFinite(Date.parse(m.kickoff)) && Date.parse(m.kickoff) === Date.parse(g.kickoff)
    && m.period === "full_game_including_overtime" && m.stat_source === "ESPN_EVENT_BOXSCORE");
}

function propValue(stats, key) {
  const fields = key === "rush_rec_yd" ? ["rush_yd", "rec_yd"] : key === "anytime_td" ? ["rush_td", "rec_td"] : [key];
  if (!["pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd", "rush_att", "rec", "rec_yd", "rush_rec_yd", "anytime_td"].includes(key)) return null;
  if (!stats || !fields.every(k => Object.hasOwn(stats, k) && Number.isFinite(stats[k])
    && (k.endsWith("_yd") || Number.isSafeInteger(stats[k]) && stats[k] >= 0))) return null;
  return fields.reduce((sum, k) => sum + stats[k], 0);
}

function propStatus(p, key, line, dir, saved = null) {
  const unknown = reason => ({ v: null, res: "unresolved", final: false, reason });
  const g = p && S.games[p.game_id];
  if (saved && !propPickBound(saved, p, g)) return unknown("Saved player/game/period binding unavailable; stored record retained");
  if (!p || !g || String(g.id) !== String(p.game_id)) return unknown("Player/game identity unavailable");
  if (!Number.isFinite(line) || dir != null && !["over", "under"].includes(dir)) return unknown("Saved line or direction unavailable");
  if (key === "fpts" && saved) return unknown("Saved fantasy-point scoring/source completeness unavailable; stored record retained");
  if (g.state === "pre") return null;
  if (!["in", "post"].includes(g.state)) return unknown("Game status unavailable");
  if (key === "fpts") {
    const c = current(p);
    if (!c || c.none || !c.stats || typeof c.stats !== "object" || Array.isArray(c.stats) || !Object.keys(c.stats).length) {
      return unknown("Provisional fantasy points unavailable; no current player statistic row");
    }
    const v = livePPR(p);
    if (!Number.isFinite(v)) return unknown("Provisional fantasy points unavailable in current scoring");
    // Preserve the existing scoring display, including its uncertified sparse
    // inputs. Neither game finality nor the current scoring settles a saved FPts pick.
    return { v, res: g.state === "in" ? "live" : "pending", final: false,
      reason: "Provisional fantasy points in current scoring; complete source/scoring evidence is not certified" };
  }
  const event = S.propEvents?.[p.game_id];
  const scoped = event?.season === S.data.season && event?.week === S.data.week
    && event.gid === String(p.game_id) && Date.parse(event.kickoff) === Date.parse(g.kickoff) && event.source === "ESPN_EVENT_BOXSCORE";
  const candidate = scoped ? event.players[p.id] : null;
  const row = candidate?.team === p.team && candidate?.espn_id === String(p.espn_id) ? candidate : null;
  if (row?.conflict) return unknown("Conflicting participation or statistical evidence");
  if (row?.dnp && event.final && propFinal(g)) return { v: null, res: "dnp", final: true };
  let v = row?.played ? propValue(row.stats, key) : null;
  if (v == null && g.state === "in" && S.propSleeper?.board === S.data) {
    const stats = S.propSleeper.players[p.id];
    if (stats && (["gp", "off_snp", "pass_att", "rush_att", "rec"].some(k => Number.isSafeInteger(stats[k]) && stats[k] > 0))) v = propValue(stats, key);
  }
  if (v == null) return unknown("Requested statistic or confirmed participation unavailable");
  if (g.state !== "post" || !propFinal(g) || !event?.final) return { v, res: g.state === "in" ? "live" : "pending", final: false };
  const over = v > line;
  return { v, res: v === line ? "push" : dir ? ((dir === "over") === over ? "hit" : "miss") : over ? "over" : "under", final: true };
}

function selectedRankingPolicy(board = S.data) {
  const original = {"version":"selected-projection-gap-v1","top_n":12,"minimum_score":0.35,"minimum_games":2,"minimum_snap_share":0.5,"minimum_projected_ppr":{"QB":10,"RB":6,"WR":6,"TE":6},"projection_line_ratio":[0.4,2.5],"categories":{"pass_yd":{"lean":8,"scale":30,"minimum_line":150.5},"pass_td":{"lean":0.15,"scale":0.6,"minimum_line":0.5},"pass_cmp":{"lean":0.8,"scale":2.5,"minimum_line":12.5},"pass_att":{"lean":1,"scale":3,"minimum_line":20.5},"pass_int":{"lean":0.12,"scale":0.5,"minimum_line":0.5},"rush_yd":{"lean":4,"scale":12,"minimum_line":15.5},"rush_att":{"lean":0.8,"scale":3,"minimum_line":6.5},"rec":{"lean":0.3,"scale":1.2,"minimum_line":1.5},"rec_yd":{"lean":4,"scale":12,"minimum_line":15.5},"rush_rec_yd":{"lean":5,"scale":15,"minimum_line":25.5}},"unavailable":["Out","IR","PUP","Suspended","NA","Doubtful","COV","DNR"],"fallback":"same-opportunity R0 reference; unavailable is never zero","meaning":"descriptive scaled forecast gap, not win probability or EV","tie_order":["absolute_score_desc","game_id","player_id","category"]};
  return board.execution_model?.model === "sleeper-matchup-classic-fg-identity-v1" ? {...original,
    version:"selected-projection-gap-classic-v1",fallback:"same-opportunity reference identified by forecast_source and model_version; unavailable is never zero"} : original;
}

function effectivePropForecast(p, prop, now = Date.now()) {
  const selected = selectedPropForecast(p, prop.key, now);
  if (selected) return { ...selected, source: 'SELECTED' };
  const value = prop.key === 'anytime_td' ? prop.td_chance : prop.adj;
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  return { value, source: p.reference_model === 'sleeper-matchup-classic-fg-identity-v1' ? 'CURRENT_BASELINE' : 'R0_FALLBACK', label: prop.key === 'anytime_td' ? 'TD probability' : 'reference', binary: prop.key === 'anytime_td', text: prop.key === 'anytime_td' ? (100 * value).toFixed(1) + '%' : value.toFixed(2) };
}

function selectedPropGap(p, prop, custom = false) {
  const policy = selectedRankingPolicy(), cat = policy.categories[prop.key];
  if (!cat || !['dk', 'sleeper'].includes(prop.line_from)) return null;
  const forecast = effectivePropForecast(p, prop), line = custom ? S.lines[p.id + '|' + prop.key] ?? prop.line : prop.line;
  if (!forecast || typeof line !== 'number' || !Number.isFinite(line)) return null;
  const gap = forecast.value - line, lean = gap > cat.lean ? 'over' : gap < -cat.lean ? 'under' : null;
  return { ...forecast, line, gap, lean, score: gap / cat.scale };
}

function selectedPropForecast(p, key, now = Date.now()) {
  try {
    const api = globalThis.WeeklyAdaptiveOverlay, overlay = S.weeklyOverlay;
    if (typeof api?.card !== "function" || !api.card(overlay, p, key, now)) return null;
    const row = overlay.rows.get(JSON.stringify([p.game_id, p.id, key]));
    const labels = { point_mean: "mean", point_median: "median", binary_probability: "TD probability" };
    if (!row || !labels[row.product] || !Number.isFinite(row.forecast_value)) return null;
    return { value: row.forecast_value, label: labels[row.product], binary: row.product === "binary_probability",
      text: row.product === "binary_probability" ? `${(100 * row.forecast_value).toFixed(1)}%` : row.forecast_value.toFixed(2),
      frozen: now >= Date.parse(row.kickoff_utc) };
  } catch (_) { return null; }
}


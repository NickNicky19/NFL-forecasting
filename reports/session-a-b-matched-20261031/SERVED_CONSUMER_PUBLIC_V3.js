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


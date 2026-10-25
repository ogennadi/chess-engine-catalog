(() => {
  const root = document.documentElement;
  const toggle = document.querySelector("#theme-toggle");
  if (toggle) {
    const show = () => toggle.setAttribute("aria-pressed", String(root.dataset.theme === "light"));
    toggle.hidden = false;
    show();
    toggle.addEventListener("click", () => {
      root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
      show();
      try {
        localStorage.setItem("engine-catalog-theme", root.dataset.theme);
      } catch (error) {
        console.warn("Theme changed, but the preference could not be saved.", error);
      }
    });
  }

  const form = document.querySelector("#filters");
  if (!form) return;
  const search = form.querySelector("#search");
  const availability = form.querySelector("#availability");
  const strength = form.querySelector("#strength");
  const clear = form.querySelector("#clear-search");
  const count = document.querySelector("#match-count");
  const empty = document.querySelector("#no-results");
  const normalize = (value) => value.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
  const rows = Array.from(document.querySelectorAll("#engine-table tbody tr"), (row) => ({
    element: row,
    names: JSON.parse(row.dataset.names).map(normalize),
    state: row.dataset.availability,
    limited: "strengthLimited" in row.dataset,
  }));
  const filters = {
    all: () => true,
    available: (state) => ["linked", "available"].includes(state),
    archived: (state) => state === "archived_only",
    unavailable: (state) => ["not_located", "released_not_located"].includes(state),
  };
  const format = (n) => n.toLocaleString("en-US");

  const apply = (save) => {
    const query = normalize(search.value.trim());
    if (clear) clear.hidden = search.value === "";
    const filter = filters[availability.value] || filters.all;
    const limitedOnly = strength.value === "limited";
    let matches = 0;
    for (const row of rows) {
      const show = filter(row.state) && (!limitedOnly || row.limited)
        && (!query || row.names.some((name) => name.includes(query)));
      row.element.hidden = !show;
      if (show) matches++;
    }
    count.textContent = matches === rows.length
      ? `${format(rows.length)} families`
      : `${format(matches)} of ${format(rows.length)} families match`;
    empty.hidden = matches !== 0;
    if (!save) return;
    const url = new URL(window.location.href);
    const q = search.value.trim();
    if (q) url.searchParams.set("q", q);
    else url.searchParams.delete("q");
    if (availability.value !== "all") url.searchParams.set("availability", availability.value);
    else url.searchParams.delete("availability");
    if (limitedOnly) url.searchParams.set("strength", "limited");
    else url.searchParams.delete("strength");
    try {
      window.history.replaceState(null, "", url);
    } catch (error) {
      console.warn("Filters applied, but the address could not be updated for bookmarking.", error);
    }
  };

  const restore = () => {
    const params = new URLSearchParams(window.location.search);
    search.value = params.get("q") || "";
    const state = params.get("availability");
    availability.value = Object.prototype.hasOwnProperty.call(filters, state) ? state : "all";
    strength.value = params.get("strength") === "limited" ? "limited" : "all";
    apply(false);
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    apply(true);
  });
  search.addEventListener("input", () => apply(true));
  if (clear) {
    clear.addEventListener("click", () => {
      search.value = "";
      apply(true);
      search.focus();
    });
  }
  availability.addEventListener("change", () => apply(true));
  strength.addEventListener("change", () => apply(true));
  form.addEventListener("reset", (event) => {
    event.preventDefault();
    search.value = "";
    availability.value = "all";
    strength.value = "all";
    apply(true);
    search.focus();
  });
  window.addEventListener("popstate", restore);
  restore();
  form.hidden = false;
})();

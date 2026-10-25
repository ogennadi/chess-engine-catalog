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
  const select = form.querySelector("#filter");
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
    available: (row) => ["linked", "available"].includes(row.state),
    archived: (row) => row.state === "archived_only",
    unavailable: (row) => ["not_located", "released_not_located"].includes(row.state),
    limited: (row) => row.limited,
  };
  const has = (key) => Object.prototype.hasOwnProperty.call(filters, key);
  const format = (n) => n.toLocaleString("en-US");

  const apply = (save) => {
    const query = normalize(search.value.trim());
    if (clear) clear.hidden = search.value === "";
    const filter = filters[select.value] || filters.all;
    let matches = 0;
    for (const row of rows) {
      const show = filter(row)
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
    url.searchParams.delete("availability");
    url.searchParams.delete("strength");
    if (select.value === "limited") url.searchParams.set("strength", "limited");
    else if (select.value !== "all") url.searchParams.set("availability", select.value);
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
    if (params.get("strength") === "limited") select.value = "limited";
    else select.value = state !== "limited" && has(state) ? state : "all";
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
  select.addEventListener("change", () => apply(true));
  form.addEventListener("reset", (event) => {
    event.preventDefault();
    search.value = "";
    select.value = "all";
    apply(true);
    search.focus();
  });
  window.addEventListener("popstate", restore);
  restore();
  form.hidden = false;
})();

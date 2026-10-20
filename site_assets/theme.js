(() => {
  let theme = "dark";
  try {
    const saved = localStorage.getItem("engine-catalog-theme");
    if (saved === "light" || saved === "dark") theme = saved;
  } catch (error) {
    console.warn("Theme preference could not be read; using dark mode.", error);
  }
  document.documentElement.dataset.theme = theme;
})();

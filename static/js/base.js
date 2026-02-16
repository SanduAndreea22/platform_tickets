function setTheme(mode) {
  const html = document.documentElement;
  html.setAttribute("data-theme", mode);

  const icon = document.querySelector("#themeToggle i");
  if (icon) {
    if (mode === "dark") {
      icon.classList.remove("fa-moon");
      icon.classList.add("fa-sun");
    } else {
      icon.classList.remove("fa-sun");
      icon.classList.add("fa-moon");
    }
  }
}

(function initTheme() {
  const saved = localStorage.getItem("theme") || "light";
  setTheme(saved);
})();

/* Theme toggle */
const themeToggle = document.getElementById("themeToggle");
if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem("theme", next);
    setTheme(next);
  });
}

/* Mobile menu */
const menuToggle = document.getElementById("menuToggle");
const navbar = document.getElementById("navbar");

if (menuToggle && navbar) {
  menuToggle.addEventListener("click", () => {
    const open = navbar.classList.toggle("is-open");
    const icon = menuToggle.querySelector("i");
    if (icon) {
      icon.classList.toggle("fa-bars", !open);
      icon.classList.toggle("fa-times", open);
    }
  });

  window.addEventListener("resize", () => {
    if (!window.matchMedia("(max-width: 860px)").matches) {
      navbar.classList.remove("is-open");
      const icon = menuToggle.querySelector("i");
      if (icon) {
        icon.classList.add("fa-bars");
        icon.classList.remove("fa-times");
      }
    }
  });
}

/* Dropdown */
document.querySelectorAll(".dropdown-btn").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const panel = btn.closest(".dropdown")?.querySelector(".dropdown-content");
    if (panel) panel.classList.toggle("is-open");
  });
});

document.addEventListener("click", () => {
  document.querySelectorAll(".dropdown-content").forEach((p) => p.classList.remove("is-open"));
});

const toggle = document.getElementById("menuToggle");
const nav = document.getElementById("siteNav");
if (toggle && nav) {
  toggle.addEventListener("click", () => nav.classList.toggle("open"));
}

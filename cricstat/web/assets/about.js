/* cricstat "About" drawer (same pattern as the homepage's About pandyaHomeLab drawer).
   Content: /cricket/about.json. Opened by any [data-about] button. Text is set with textContent
   only; **bold** and *italic* in the JSON become <strong>/<em>. Mermaid (self-hosted) loads on
   first open, and only if a section has a diagram. */
(function () {
  "use strict";
  const C = window.cricstat, h = C.h;
  let loaded = false, mermaidReady = false, lastFocus = null;

  // "**bold** and *italic*" → nodes, never HTML.
  function rich(text) {
    return String(text).split(/(\*\*[^*]+\*\*|\*[^*]+\*)/).filter(Boolean).map((part) =>
      part.startsWith("**") ? h("strong", {}, part.slice(2, -2))
        : part.startsWith("*") && part.length > 2 ? h("em", {}, part.slice(1, -1)) : document.createTextNode(part));
  }
  function section(s) {
    return h("section", { class: "about-section", id: "about-" + s.id }, [
      h("h3", {}, [h("span", { class: "icon", "aria-hidden": "true" }, s.icon || ""), s.title]),
      (s.body || []).map((p) => h("p", {}, rich(p))),
      s.bullets ? h("ul", { class: "about-bullets" }, s.bullets.map((b) => h("li", {}, [h("b", {}, b.label), " — "].concat(rich(b.text))))) : null,
      (s.after || []).map((p) => h("p", {}, rich(p))),
      s.diagram && s.diagram.type === "mermaid" ? h("div", { class: "about-diagram" }, h("pre", { class: "mermaid" }, s.diagram.code)) : null,
      s.facts ? h("div", { class: "about-facts" }, s.facts.map((f) => h("div", { class: "about-fact" }, [
        h("div", { class: "about-fact-label" }, f.label), h("div", { class: "about-fact-value" }, f.value)]))) : null,
      s.links ? h("div", { class: "about-links" }, s.links.map((l) => h("a", { class: "about-link", href: l.href }, l.label + " →"))) : null,
    ].flat());
  }
  function ensureMermaid() {
    if (mermaidReady) return Promise.resolve();
    return new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = "/vendor/mermaid-10.9.8/mermaid.min.js"; s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    }).then(() => {
      window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "dark", themeVariables: {
        background: "#13161e", primaryColor: "#1a1e2a", primaryTextColor: "#e2e8f0", primaryBorderColor: "#FF9933",
        lineColor: "#64748b", secondaryColor: "#252a38", tertiaryColor: "#0d0f14" } });
      mermaidReady = true;
    });
  }
  async function load() {
    if (loaded) return;
    const body = document.getElementById("about-body");
    try {
      const r = await fetch("/cricket/about.json");
      if (!r.ok) throw new Error("HTTP " + r.status);
      const data = await r.json();
      document.getElementById("about-title").textContent = data.title || "About";
      document.getElementById("about-tagline").textContent = data.tagline || "";
      C.fill(body, data.sections.map(section));
      loaded = true;
      if (data.sections.some((s) => s.diagram && s.diagram.type === "mermaid")) {
        try { await ensureMermaid(); await window.mermaid.run({ querySelector: "#about-drawer .mermaid" }); }
        catch (e) { /* the diagram source stays readable as text */ }
      }
    } catch (e) {
      C.fill(body, h("p", { class: "error" }, "Couldn't load this page's story. Please try again later."));
    }
  }
  function open(ev) {
    if (ev && ev.preventDefault) ev.preventDefault();
    lastFocus = document.activeElement;
    const d = document.getElementById("about-drawer");
    d.classList.add("visible"); d.setAttribute("aria-hidden", "false");
    document.getElementById("about-backdrop").classList.add("visible");
    document.body.style.overflow = "hidden";
    document.getElementById("about-close").focus();
    d.scrollTop = 0;   // always open at the top (the story first)
    load();
  }
  function close() {
    const d = document.getElementById("about-drawer");
    if (!d.classList.contains("visible")) return;
    d.classList.remove("visible"); d.setAttribute("aria-hidden", "true");
    document.getElementById("about-backdrop").classList.remove("visible");
    document.body.style.overflow = "";
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  document.body.appendChild(h("div", { class: "about-backdrop", id: "about-backdrop", onclick: close }));
  document.body.appendChild(h("aside", { class: "about-drawer", id: "about-drawer", role: "dialog", "aria-modal": "true",
    "aria-hidden": "true", "aria-labelledby": "about-title" }, [
    h("div", { class: "about-header" }, [
      h("div", {}, [h("div", { class: "about-title", id: "about-title" }, "About cricstat"), h("div", { class: "about-tagline", id: "about-tagline" })]),
      h("button", { class: "about-close", id: "about-close", type: "button", "aria-label": "Close", onclick: close }, "✕")]),
    h("div", { id: "about-body" }, h("p", { class: "loading" }, "Loading…"))]));
  document.querySelectorAll("[data-about]").forEach((b) => b.addEventListener("click", open));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  if (location.hash === "#about") open();
})();

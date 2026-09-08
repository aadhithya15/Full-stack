
/* huefit-route-tagger */
/* Injected by Apply-HueFitVisualFix.ps1 (v5). Module-scope code: allowed by the
   app's Content Security Policy (script-src 'self'), unlike inline <script> tags.
   Adds hf-saved / hf-closet / hf-profile / ... to <body> from the current URL.
   Safe to delete this whole block. */
(function () {
  try {
    var CLASSES = ["hf-saved", "hf-closet", "hf-profile", "hf-analyze", "hf-dashboard", "hf-quiz"];
    var MAP = [
      [["/saved"], "hf-saved"],
      [["/closet", "/wardrobe", "/digital-closet"], "hf-closet"],
      [["/profile", "/preferences"], "hf-profile"],
      [["/analyze", "/analysis", "/style-analysis"], "hf-analyze"],
      [["/dashboard"], "hf-dashboard"],
      [["/quiz", "/style-quiz"], "hf-quiz"]
    ];
    var last = "";
    function currentPath() {
      var p = location.pathname;
      if (location.hash && location.hash.indexOf("#/") === 0) p = location.hash.slice(1);
      p = p.toLowerCase().replace(/\/+$/, "");
      return p === "" ? "/" : p;
    }
    function ensureRipple() {
      if (document.getElementById("huefitSareeRippleWrap")) return;
      var w = document.createElement("div");
      w.id = "huefitSareeRippleWrap";
      w.setAttribute("aria-hidden", "true");
      w.style.cssText = "position:absolute;width:0;height:0;overflow:hidden";
      w.innerHTML = '<svg width="0" height="0" focusable="false"><filter id="huefitSareeRipple"><feTurbulence type="fractalNoise" baseFrequency="0.006 0.012" numOctaves="2" seed="4" result="n"><animate attributeName="baseFrequency" dur="16s" values="0.006 0.012;0.009 0.016;0.006 0.012" repeatCount="indefinite"/></feTurbulence><feDisplacementMap in="SourceGraphic" in2="n" scale="26" xChannelSelector="R" yChannelSelector="G"/></filter></svg>';
      document.body.appendChild(w);
    }
    function apply() {
      if (!document.body) return;
      var p = currentPath(), cls = "";
      for (var i = 0; i < MAP.length; i++) { if (MAP[i][0].indexOf(p) !== -1) { cls = MAP[i][1]; break; } }
      for (var j = 0; j < CLASSES.length; j++) { if (CLASSES[j] !== cls) document.body.classList.remove(CLASSES[j]); }
      if (cls) document.body.classList.add(cls);
      if (cls === "hf-profile") ensureRipple();
      if (cls !== last) { last = cls; if (cls) console.info("%c[HueFit] background route class:", "color:#c99a4a", cls); }
    }
    ["pushState", "replaceState"].forEach(function (fn) {
      var orig = history[fn];
      if (orig && !orig.__hf) {
        history[fn] = function () { var r = orig.apply(this, arguments); setTimeout(apply, 0); return r; };
        history[fn].__hf = 1;
      }
    });
    window.addEventListener("popstate", apply);
    window.addEventListener("hashchange", apply);
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply); else apply();
    setInterval(apply, 900);
  } catch (e) { /* never break the app */ }
})();
/* /huefit-route-tagger */

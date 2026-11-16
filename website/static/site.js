// Happy Highrise - the only script on the site, and the site works without it.
// It moves the lift car to the floor you are reading, and opens screenshots
// in a lightbox instead of a new page.
(function () {
  "use strict";

  // ---- the lift car ----
  var shaft = document.querySelector(".shaft");
  if (shaft && "IntersectionObserver" in window) {
    var car = shaft.querySelector(".car");
    var links = Array.prototype.slice.call(shaft.querySelectorAll("a[href^='#']"));
    var byId = {};
    links.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var visible = {};

    function park(id) {
      var a = byId[id];
      if (!a) return;
      links.forEach(function (l) { l.removeAttribute("aria-current"); });
      a.setAttribute("aria-current", "location");
      car.style.transform = "translateY(" + a.parentNode.offsetTop + "px)";
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { visible[e.target.id] = e.intersectionRatio; });
      // The floor that fills most of a band across the middle of the screen.
      var best = null, bestRatio = 0;
      links.forEach(function (a) {
        var id = a.getAttribute("href").slice(1);
        if ((visible[id] || 0) > bestRatio) { best = id; bestRatio = visible[id]; }
      });
      if (best) park(best);
    }, { rootMargin: "-40% 0px -40% 0px", threshold: [0, 0.01, 0.25, 0.5, 0.75, 1] });

    Object.keys(byId).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) io.observe(el);
    });
    park(Object.keys(byId)[0]);
  }

  // ---- lightbox ----
  var dialog = document.querySelector("dialog.lightbox");
  var shots = Array.prototype.slice.call(document.querySelectorAll("a.shot"));
  if (dialog && typeof dialog.showModal === "function" && shots.length) {
    var img = dialog.querySelector("img");
    var cap = dialog.querySelector("figcaption");
    var at = 0;

    function show(i) {
      at = (i + shots.length) % shots.length;
      var a = shots[at];
      var alt = a.querySelector("img").getAttribute("alt");
      img.src = a.getAttribute("href");
      img.alt = alt;
      cap.textContent = alt;
    }

    shots.forEach(function (a, i) {
      a.addEventListener("click", function (ev) {
        if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button !== 0) return;
        ev.preventDefault();
        show(i);
        dialog.showModal();
      });
    });
    dialog.querySelector(".close").addEventListener("click", function () { dialog.close(); });
    dialog.querySelector(".prev").addEventListener("click", function () { show(at - 1); });
    dialog.querySelector(".next").addEventListener("click", function () { show(at + 1); });
    dialog.addEventListener("click", function (ev) {
      if (ev.target === dialog || ev.target.tagName === "FIGURE") dialog.close();
    });
    dialog.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowLeft") show(at - 1);
      if (ev.key === "ArrowRight") show(at + 1);
    });
    dialog.addEventListener("close", function () { img.removeAttribute("src"); });
  }
})();

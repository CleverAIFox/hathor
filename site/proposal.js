// **기획서 화면의 스크립트** (D-0368). `tools/render_proposal.py`가 이 파일을 통째로
// 페이지에 박는다 — 두 벌이 되지 않게 **여기 한 곳에만 있다.**
//
// fire-lane의 협업 방침 화면은 JS를 안 쓴다. 까닭은 *「이 페이지의 스크립트를 보는
// 검사가 없으므로 스크립트가 들어가면 검사 밖에서 자란다」*였다. 여기는 그 검사를
// 같이 두었다 — `node --check`가 `make check`에서 돈다. 없는 기기에서는 **안 쟀다고
// 적는다** (GR-0.5).
//
// CSS로 되는 것은 CSS가 한다. 이 파일이 맡는 것은 둘뿐이다.
//   1) 찾기 — 절 150개를 눈으로 훑을 수 없다
//   2) 지금 보는 절을 목차에서 표시 — 긴 문서에서 자리를 잃는다
"use strict";

(function () {
  var find = document.getElementById("find");
  var panes = document.querySelectorAll(".pane");
  var count = document.getElementById("found");

  // ---- 찾기. **절 단위로 숨긴다** — 문장 단위로 숨기면 표가 깨진다.
  function blocks() {
    var out = [];
    panes.forEach(function (pane) {
      var current = null;
      Array.prototype.forEach.call(pane.children, function (node) {
        if (node.tagName === "H2") {
          current = { head: node, body: [] };
          out.push(current);
        } else if (current) {
          current.body.push(node);
        }
      });
    });
    return out;
  }

  var groups = blocks();

  function run(word) {
    var needle = word.trim().toLowerCase();
    var shown = 0;
    groups.forEach(function (group) {
      var text = group.head.textContent + " ";
      group.body.forEach(function (node) {
        text += node.textContent + " ";
      });
      var hit = !needle || text.toLowerCase().indexOf(needle) >= 0;
      group.head.hidden = !hit;
      group.body.forEach(function (node) {
        node.hidden = !hit;
      });
      if (hit) shown += 1;
    });
    if (count) {
      count.textContent = needle ? shown + " / " + groups.length + " 절" : "";
    }
  }

  if (find) {
    find.addEventListener("input", function () {
      run(find.value);
    });
    // **새로 고침에도 남게 하지 않는다** — 찾던 말이 남아 절이 숨은 채로 보이면
    // 사람이 「문서가 비었다」로 읽는다.
    find.value = "";
  }

  // ---- 지금 보는 절. 목차에서 그 줄을 굵게 한다.
  var links = {};
  document.querySelectorAll("nav a").forEach(function (link) {
    links[decodeURIComponent(link.getAttribute("href") || "").slice(1)] = link;
  });
  var marked = null;
  var watch = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var link = links[entry.target.id];
        if (!link || link === marked) return;
        if (marked) marked.removeAttribute("aria-current");
        link.setAttribute("aria-current", "true");
        marked = link;
      });
    },
    { rootMargin: "-10% 0px -80% 0px" }
  );
  document.querySelectorAll(".pane h2").forEach(function (head) {
    watch.observe(head);
  });
})();

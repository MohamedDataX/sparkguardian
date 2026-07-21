// SparkGuardian landing — free token generation, scroll reveal.
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  }

  // FastAPI errors: `detail` is a string (HTTPException) or a list of
  // validation objects (422). Turn either into readable text.
  function errMsg(data, fallback) {
    const d = data && data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d.length) return d[0].msg || fallback;
    return fallback;
  }

  // ---- Free token generation ----
  const tokenForm = $("#token-form");
  if (tokenForm) {
    tokenForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = $("#token-msg");
      const btn = tokenForm.querySelector("button[type=submit]");
      msg.textContent = "";
      msg.className = "msg";
      btn.disabled = true;
      btn.textContent = "Generating…";

      const { ok, data } = await postJSON("/api/licenses/free", {
        name: $("#name").value.trim(),
        email: $("#email").value.trim(),
      });

      btn.disabled = false;
      btn.textContent = "Generate Free Token";

      if (ok) {
        $("#token-value").textContent = data.token;
        $("#token-out").hidden = false;
        msg.textContent = "Token ready — copy it below.";
        msg.classList.add("ok");
      } else {
        msg.textContent = errMsg(data, "Something went wrong.");
        msg.classList.add("err");
      }
    });
  }

  // ---- Copy token ----
  const copyBtn = $("#copy-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      await navigator.clipboard.writeText($("#token-value").textContent);
      copyBtn.textContent = "Copied!";
      setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
    });
  }

  // ---- Scroll reveal ----
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) {
          en.target.classList.add("in");
          io.unobserve(en.target);
        }
      });
    },
    { threshold: 0.12 }
  );
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
})();

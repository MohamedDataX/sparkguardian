// SparkGuardian landing — trial generation, checkout, scroll reveal.
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

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  // ---- Free-trial token generation ----
  const trialForm = $("#trial-form");
  if (trialForm) {
    trialForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = $("#trial-msg");
      const btn = trialForm.querySelector("button[type=submit]");
      msg.textContent = "";
      msg.className = "msg";
      btn.disabled = true;
      btn.textContent = "Generating…";

      const { ok, status, data } = await postJSON("/api/licenses/trial", {
        name: $("#name").value.trim(),
        email: $("#email").value.trim(),
      });

      btn.disabled = false;
      btn.textContent = "Generate Trial Token";

      if (ok) {
        $("#token-value").textContent = data.token;
        $("#token-out").hidden = false;
        msg.textContent = "Trial ready — copy your token below.";
        msg.classList.add("ok");
      } else {
        msg.textContent =
          status === 409
            ? "A trial already exists for this email."
            : errMsg(data, "Something went wrong.");
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

  // ---- Stripe subscribe ----
  const subBtn = $("#subscribe-btn");
  if (subBtn) {
    subBtn.addEventListener("click", async () => {
      const msg = $("#pay-msg");
      msg.textContent = "";
      msg.className = "msg";
      const email = (prompt("Enter your email to subscribe:") || "").trim();
      if (!email) return;
      if (!EMAIL_RE.test(email)) {
        msg.textContent = "Please enter a valid email address.";
        msg.classList.add("err");
        return;
      }
      subBtn.disabled = true;
      subBtn.textContent = "Redirecting…";
      const { ok, status, data } = await postJSON("/api/billing/checkout", { email });
      subBtn.disabled = false;
      subBtn.textContent = "Subscribe";
      if (ok && data.url) {
        window.location.href = data.url;
      } else if (status === 501) {
        msg.textContent = "Billing is not configured yet. Try the free trial instead.";
        msg.classList.add("err");
      } else {
        msg.textContent = errMsg(data, "Billing unavailable.");
        msg.classList.add("err");
      }
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

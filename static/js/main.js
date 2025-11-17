"use strict";

const canvasElement = document.getElementById("canvas");
const errorElement = document.getElementById("error");
const textArea = document.getElementById("processText");
const convertButton = document.getElementById("convertBtn");

const viewer = new BpmnJS({
  container: canvasElement,
});

// Type placeholder text word-by-word
(function setupTypingPlaceholder() {
  const demoText =
    "مثال: مشتری سفارش را ثبت می‌کند. واحد فروش سفارش را بررسی می‌کند. فاکتور صادر می‌شود.";

  let timerId = null;
  let currentCharIndex = 0;

  function stopTyping() {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
  }

  function startTyping() {
    // Start with empty placeholder
    textArea.placeholder = "";
    currentCharIndex = 0;

    stopTyping();
    timerId = setInterval(() => {
      // If user started typing or focused, stop the animation
      if (document.activeElement === textArea || textArea.value.trim().length > 0) {
        stopTyping();
        return;
      }

      currentCharIndex = Math.min(currentCharIndex + 1, demoText.length);
      textArea.placeholder = demoText.slice(0, currentCharIndex);

      if (currentCharIndex >= demoText.length) {
        stopTyping();
      }
    }, 90);
  }

  // Restart typing when the textarea loses focus and is empty
  textArea.addEventListener("blur", () => {
    if (!textArea.value.trim()) {
      startTyping();
    }
  });

  // Kick off once on load
  startTyping();
})();

async function convertToBpmn() {
  errorElement.textContent = "";
  convertButton.disabled = true;
  convertButton.textContent = "در حال تبدیل...";

  const text = textArea.value.trim();
  if (!text) {
    errorElement.textContent = "لطفاً شرح فرایند را وارد کنید.";
    convertButton.disabled = false;
    convertButton.textContent = "تبدیل به نمودار";
    return;
  }

  try {
    const response = await fetch("/convert", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text }),
    });

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "تبدیل با خطا مواجه شد.");
    }

    await viewer.importXML(payload.bpmn);
    viewer.get("canvas").zoom("fit-viewport", "auto");
  } catch (error) {
    console.error(error);
    errorElement.textContent = error.message || "خطای ناشناخته رخ داد.";
  } finally {
    convertButton.disabled = false;
    convertButton.textContent = "تبدیل به نمودار";
  }
}

convertButton.addEventListener("click", convertToBpmn);





// Guided tour implementation
(function guideTour() {
  const tourRoot = document.getElementById("tourRoot");
  if (!tourRoot) return;

  // Always show the tour on each page load

  const steps = [
    {
      id: "intro",
      position: { fixed: true, left: 16, bottom: 16 },
      text: "این صفحه متن فرایند را گرفته و آن را به نمودار BPMN تبدیل می‌کند.",
    },
    {
      id: "input",
      anchor: () => document.getElementById("processText"),
      offset: { x: 0, y: -70 },
      text: "در این کادر، شرح فرایند را بنویس و روی «تبدیل به نمودار» کلیک کن.",
    },
    {
      id: "viewer",
      anchor: () => document.getElementById("viewerSection"),
      offset: { x: 0, y: -70 },
      text: "اینجا نمودار BPMN رندر می‌شود. می‌توانی زوم کنی و جزییات را ببینی.",
    },
  ];

  let stepIndex = 0;

  function createCard(message) {
    const wrapper = document.createElement("div");
    wrapper.className = "tour-wrap";

    // Character image (outside the panel)
    const img = document.createElement("img");
    img.className = "tour-figure";
    img.src = "/assets/img.png";
    img.alt = "راهنما";

    // Right-side panel with text and button
    const panel = document.createElement("div");
    panel.className = "tour-panel";

    const textEl = document.createElement("p");
    textEl.textContent = message;

    const btn = document.createElement("button");
    btn.textContent = stepIndex < steps.length - 1 ? "بعدی" : "تمام شد";

    panel.appendChild(textEl);
    panel.appendChild(btn);

    wrapper.appendChild(img);
    wrapper.appendChild(panel);

    return { wrapper, btn };
  }

  function getAnchorRect(el) {
    const rect = el.getBoundingClientRect();
    return {
      left: rect.left + window.scrollX,
      top: rect.top + window.scrollY,
      width: rect.width,
      height: rect.height,
    };
  }

  function renderStep() {
    tourRoot.innerHTML = "";

    const overlay = document.createElement("div");
    overlay.className = "tour-overlay";
    tourRoot.appendChild(overlay);

    const { wrapper, btn } = createCard(steps[stepIndex].text);
    tourRoot.appendChild(wrapper);

    // Positioning
    const step = steps[stepIndex];
    if (step.position && step.position.fixed) {
      wrapper.style.position = "fixed";
      if (step.position.left != null) wrapper.style.left = step.position.left + "px";
      if (step.position.right != null) wrapper.style.right = step.position.right + "px";
      if (step.position.top != null) wrapper.style.top = step.position.top + "px";
      if (step.position.bottom != null) wrapper.style.bottom = step.position.bottom + "px";
    } else if (step.anchor) {
      const anchor = step.anchor();
      if (anchor) {
        const rect = anchor.getBoundingClientRect();
        // For input step, position the card centered ON the textarea section
        if (step.id === "input") {
          let x = rect.left + window.scrollX + (rect.width - wrapper.offsetWidth) / 2 + (step.offset?.x || 0);
          let y = rect.top + window.scrollY + (rect.height - wrapper.offsetHeight) / 2 + (step.offset?.y || 0);

          // Clamp to keep fully visible
          const minLeft = window.scrollX + 12;
          const maxLeft = window.scrollX + window.innerWidth - wrapper.offsetWidth - 12;
          const minTop = window.scrollY + 12;
          const maxTop = window.scrollY + window.innerHeight - wrapper.offsetHeight - 12;
          x = Math.min(Math.max(x, minLeft), maxLeft);
          y = Math.min(Math.max(y, minTop), maxTop);

          wrapper.style.left = x + "px";
          wrapper.style.top = y + "px";
        } else {
          // Default: above the anchor
          const x = rect.left + rect.width / 2 - wrapper.offsetWidth / 2 + (step.offset?.x || 0);
          let y = rect.top + window.scrollY - wrapper.offsetHeight - 12 + (step.offset?.y || 0);

          const minTop = window.scrollY + 12;
          const maxTop = window.scrollY + window.innerHeight - wrapper.offsetHeight - 12;
          wrapper.style.left = Math.max(12, x) + "px";
          wrapper.style.top = Math.min(Math.max(12, y), maxTop) + "px";
        }
      }
    }

    function next() {
      if (stepIndex < steps.length - 1) {
        stepIndex += 1;
        renderStep();
      } else {
        // Do not persist completion; always show on refresh
        tourRoot.innerHTML = "";
      }
    }

    overlay.addEventListener("click", next);
    btn.addEventListener("click", next);
  }

  // delay to ensure DOM sizes are ready
  window.requestAnimationFrame(() => {
    setTimeout(renderStep, 100);
  });
})(); 


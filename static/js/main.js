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







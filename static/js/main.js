"use strict";

const canvasElement = document.getElementById("canvas");
const errorElement = document.getElementById("error");
const textArea = document.getElementById("processText");
const convertButton = document.getElementById("convertBtn");

const viewer = new BpmnJS({
  container: canvasElement,
});

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



function drawChart(id, label) {
  const canvas = document.getElementById(id);
  if (!canvas || !window.Chart) return;
  const labels = JSON.parse(canvas.dataset.labels || "[]");
  const values = JSON.parse(canvas.dataset.values || "[]");
  new Chart(canvas, {
    type: "bar",
    data: { labels, datasets: [{ label, data: values, backgroundColor: "#0b3d75" }] },
    options: { responsive: true, plugins: { legend: { display: false } } }
  });
}
drawChart("categoryChart", "Complaints by category");
drawChart("statusChart", "Complaints by status");
drawChart("priorityChart", "Complaints by priority");

function setupComplaintPrediction() {
  const panel = document.getElementById("aiSuggestion");
  const title = document.getElementById("title");
  const description = document.getElementById("description");
  const category = document.getElementById("category");
  const priority = document.getElementById("priority");
  if (!panel || !title || !description || !category || !priority) return;

  const categoryBadge = document.getElementById("categoryConfidence");
  const priorityBadge = document.getElementById("priorityConfidence");
  const message = document.getElementById("aiSuggestionMessage");
  const predictedCategory = document.getElementById("predicted_category");
  const predictedPriority = document.getElementById("predicted_priority");
  const categoryConfidence = document.getElementById("category_confidence");
  const priorityConfidence = document.getElementById("priority_confidence");
  let timer = null;

  function setBadge(element, label, confidence) {
    element.textContent = confidence ? `${label} (${confidence.toFixed(1)}%)` : label;
    element.className = "confidence-badge";
    if (label.startsWith("High")) element.classList.add("confidence-high");
    else if (label.startsWith("Please")) element.classList.add("confidence-medium");
    else element.classList.add("confidence-low");
  }

  function clearSuggestion(text) {
    setBadge(categoryBadge, "Waiting for text", 0);
    setBadge(priorityBadge, "Waiting for text", 0);
    message.textContent = text;
    predictedCategory.value = "";
    predictedPriority.value = "";
    categoryConfidence.value = "";
    priorityConfidence.value = "";
  }

  async function predict() {
    const body = { title: title.value, description: description.value };
    const textLength = `${body.title} ${body.description}`.trim().length;
    if (textLength < 15) {
      clearSuggestion("Type at least 15 characters to get a suggestion.");
      return;
    }
    message.textContent = "Checking complaint text...";
    const response = await fetch(panel.dataset.predictUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      clearSuggestion("AI suggestion is unavailable right now. Please choose manually.");
      return;
    }
    const data = await response.json();
    setBadge(categoryBadge, data.category_confidence_label, data.category_confidence);
    setBadge(priorityBadge, data.priority_confidence_label, data.priority_confidence);
    message.textContent = data.low_confidence ? "Low confidence. Please choose the final category and priority." : data.message;

    predictedCategory.value = data.category || "";
    predictedPriority.value = data.priority || "";
    categoryConfidence.value = data.category_confidence || "";
    priorityConfidence.value = data.priority_confidence || "";
    category.value = data.category_confidence >= 60 && data.category ? data.category : "";
    priority.value = data.priority_confidence >= 60 && data.priority ? data.priority : "";
  }

  function queuePredict() {
    window.clearTimeout(timer);
    timer = window.setTimeout(predict, 600);
  }

  title.addEventListener("input", queuePredict);
  description.addEventListener("input", queuePredict);
}

setupComplaintPrediction();

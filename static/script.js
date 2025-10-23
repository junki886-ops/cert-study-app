let currentId = 100; // 시작 문제 번호 (샘플 JSON이 100번부터라고 가정)

async function loadQuestion(id) {
  const res = await fetch(`/question/${id}`);
  const q = await res.json();

  if (q.error) {
    document.getElementById("question-area").innerHTML = `<p>문제를 찾을 수 없습니다.</p>`;
    return;
  }

  currentId = q.id;

  let html = `<h2>${q.id}. ${q.question}</h2>`;
  for (const [key, val] of Object.entries(q.options)) {
    html += `<label><input type="radio" name="answer" value="${key}"> ${key}. ${val}</label><br>`;
  }
  html += `<button onclick="submitAnswer(${q.id})">제출</button>`;

  document.getElementById("question-area").innerHTML = html;
  document.getElementById("result").innerHTML = "";
  document.getElementById("next-btn").style.display = "none";
}

async function submitAnswer(id) {
  const selected = document.querySelector("input[name='answer']:checked");
  if (!selected) {
    alert("답을 선택하세요!");
    return;
  }

  const res = await fetch("/check_answer", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({id: id, answer: selected.value})
  });
  const result = await res.json();

  let msg = result.correct ? "✅ 정답입니다!" : "❌ 오답입니다!";
  msg += `<br>정답: ${result.correct_answer}`;
  msg += `<br>해설: ${result.explanation}`;

  document.getElementById("result").innerHTML = msg;

  // "다음 문제" 버튼 표시
  document.getElementById("next-btn").style.display = "inline-block";
}

function nextQuestion() {
  loadQuestion(currentId + 1);
}

// 시작 시 첫 문제 로드
window.onload = () => {
  loadQuestion(currentId);
};

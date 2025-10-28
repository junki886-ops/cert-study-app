let currentId = 0;
let chosen = null;

function loadQuestion(qid = null) {
  let url = "/api/question";
  if (qid) url += "?id=" + qid;

  $.getJSON(url, function(data) {
    currentId = data.id;
    $("#qno").text("문제 " + data.qno);
    $("#stem").text(data.stem);

    $("#options").empty();
    data.options.forEach(opt => {
      let btn = $("<button>")
        .addClass("list-group-item list-group-item-action")
        .text(opt)
        .click(function() {
          $("#options button").removeClass("active");
          $(this).addClass("active");
          chosen = opt;
        });
      $("#options").append(btn);
    });

    $("#result").empty();
  });
}

function submitAnswer() {
  if (!chosen) {
    alert("선택지를 고르세요!");
    return;
  }

  $.ajax({
    url: "/api/answer",
    type: "POST",
    contentType: "application/json",
    data: JSON.stringify({ question_id: currentId, chosen: chosen }),
    success: function(resp) {
      let resultText = resp.correct
        ? `<div class="alert alert-success">정답입니다! ✅</div>`
        : `<div class="alert alert-danger">틀렸습니다 ❌<br>정답: ${resp.answer}</div>`;
      $("#result").html(resultText);
    }
  });
}

function loadNext() {
  $.getJSON("/api/next?current_id=" + currentId, function(data) {
    if (data.end) {
      $("#qno").text("끝!");
      $("#stem").text(data.message);
      $("#options").empty();
      $("#result").empty();
    } else {
      currentId = data.id;
      $("#qno").text("문제 " + data.qno);
      $("#stem").text(data.stem);

      $("#options").empty();
      chosen = null;
      data.options.forEach(opt => {
        let btn = $("<button>")
          .addClass("list-group-item list-group-item-action")
          .text(opt)
          .click(function() {
            $("#options button").removeClass("active");
            $(this).addClass("active");
            chosen = opt;
          });
        $("#options").append(btn);
      });

      $("#result").empty();
    }
  });
}

$(document).ready(function() {
  loadQuestion();
  $("#submitBtn").click(submitAnswer);
  $("#nextBtn").click(loadNext);
});

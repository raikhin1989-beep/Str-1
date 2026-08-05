// Раунд: подсветка повторов и автосохранение черновика.
//
// Проверка «одно название дважды» дублируется на сервере — здесь она только
// для того, чтобы человек увидел ошибку сразу, а не после отправки.
(function () {
  var form = document.getElementById('round');
  if (!form) return;

  var state = document.getElementById('draft-state');
  var url = form.dataset.draft;
  var timer = null;
  var pending = false;
  var stale = /другому раунду/;

  function answers() {
    var result = {};
    form.querySelectorAll('select[data-answer]').forEach(function (select) {
      result[select.name.slice('sample_'.length)] = select.value;
    });
    return result;
  }

  function collect(prefix) {
    var result = {};
    form.querySelectorAll('[name^="' + prefix + '"]').forEach(function (field) {
      result[field.name.slice(prefix.length)] = field.value;
    });
    return result;
  }

  function markDuplicates() {
    var seen = {};
    var duplicate = false;
    var selects = form.querySelectorAll('select[data-answer]');
    selects.forEach(function (select) {
      select.classList.remove('dup');
    });
    selects.forEach(function (select) {
      if (!select.value) return;
      if (seen[select.value]) {
        select.classList.add('dup');
        seen[select.value].classList.add('dup');
        duplicate = true;
      }
      seen[select.value] = select;
    });
    return duplicate;
  }

  function say(text) {
    if (state) state.textContent = text;
  }

  function save() {
    if (markDuplicates()) {
      say('Одно название стоит у двух образцов — черновик не сохраняю.');
      return;
    }
    if (pending) return;
    pending = true;
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        // Раунд, для которого нарисована страница: сервер сверит и не даст
        // черновику по запаху лечь в раунд вкуса, если ведущий успел перейти.
        round: form.dataset.round,
        answers: answers(),
        scores: collect('score_'),
        tags: collect('tags_'),
        categories: collect('class_')
      })
    })
      .then(function (response) { return response.json().catch(function () { return {}; }); })
      .then(function (body) {
        say(body.ok ? 'Черновик сохранён' : (body.error || 'Черновик сохранить не удалось'));
        // Ведущий перешёл к другому раунду, пока гость отвечал. Показываем
        // ему актуальную страницу сами: дожимать «Отправить» бессмысленно.
        if (!body.ok && stale.test(body.error || '')) {
          setTimeout(function () { window.location.reload(); }, 1500);
        }
      })
      .catch(function () { say('Нет связи — черновик не сохранён, но кнопка «Отправить» работает.'); })
      .finally(function () { pending = false; });
  }

  // Ждём полсекунды после последнего изменения: пока человек двигает ползунок,
  // запрос уходить не должен.
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(save, 500);
  }

  form.addEventListener('change', schedule);
  form.addEventListener('input', schedule);

  form.addEventListener('submit', function (event) {
    if (markDuplicates()) {
      event.preventDefault();
      say('Одно название стоит у двух образцов — поправьте перед отправкой.');
      return;
    }
    if (!confirm('Отправить ответ? Изменить его будет нельзя.')) event.preventDefault();
  });

  markDuplicates();
})();

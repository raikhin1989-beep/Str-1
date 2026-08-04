// Экран ведущего: та же таблица, что и на странице итогов, но обновляется сама.
// Опрос раз в три секунды — этого хватает, чтобы за столом успевали заметить,
// и не хватает, чтобы нагрузить сервер: страница одна, на проекторе.
(function () {
  var root = document.querySelector('.board');
  if (!root) return;

  var status = document.getElementById('board-status');
  var table = document.getElementById('board-table');
  var body = table.querySelector('tbody');

  function text(cell, value) {
    cell.textContent = value === null || value === undefined ? '—' : String(value);
    return cell;
  }

  function render(data) {
    if (data.round) {
      status.textContent = 'Раунд ' + data.round + ': сдали ' +
        data.submitted + ' из ' + data.participants;
    } else {
      status.textContent = data.status;
    }

    table.hidden = data.rows.length === 0;
    body.textContent = '';
    data.rows.forEach(function (row) {
      var tr = document.createElement('tr');
      // Порядок обязан совпадать с <thead> в board.html: заголовки там,
      // значения здесь, и разъехаться им ничего не мешает, кроме внимания.
      // Итого — сразу после имени: это главное число таблицы, и на телефоне
      // оно единственное, что обязано попасть на экран.
      [
        ['num', row.place], [null, row.name], ['num', row.total], ['num', row.nose],
        ['num', row.palate], ['num', row.partial], ['num', row.bonus]
      ].forEach(function (pair, index) {
        var td = document.createElement('td');
        if (pair[0]) td.className = pair[0];
        // Через textContent, а не innerHTML: имя участника пишет он сам.
        text(td, pair[1]);
        if (index === 2) td.innerHTML = '<strong>' + td.textContent + '</strong>';
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
  }

  function poll() {
    fetch(root.dataset.source, { cache: 'no-store' })
      .then(function (response) { return response.json(); })
      .then(render)
      .catch(function () { status.textContent = 'Нет связи с сервером'; });
  }

  poll();
  setInterval(poll, 3000);
})();

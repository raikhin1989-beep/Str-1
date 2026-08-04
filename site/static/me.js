// Личная страница гостя: следим за ходом вечера.
//
// Раунд открывает ведущий со своего экрана, а гость в это время смотрит
// в телефон. Догадаться обновить страницу за столом не догадывается никто,
// поэтому спрашиваем сами и перезагружаемся, когда состояние изменилось.
//
// Раз в три секунды — как на экране ведущего: этого хватает, чтобы «начали!»
// и появление формы совпали по ощущению, и не хватает, чтобы нагрузить сервер
// десятком телефонов.
(function () {
  var root = document.getElementById('live');
  if (!root) return;

  var was = JSON.parse(root.dataset.state);
  var button = document.getElementById('start-round');
  var failures = 0;

  function changed(now) {
    return now.status !== was.status || now.round !== was.round ||
           now.submitted !== was.submitted;
  }

  function poll() {
    fetch(root.dataset.source, { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error(response.status);
        return response.json();
      })
      .then(function (now) {
        failures = 0;
        if (!changed(now)) return;
        // Не подменяем содержимое сами: страница целиком рисуется сервером,
        // и перезагрузка гарантированно показывает то же, что увидит любой,
        // кто откроет ссылку заново.
        if (button) {
          button.disabled = false;
          button.textContent = 'Начинаем!';
        }
        window.location.reload();
      })
      .catch(function () {
        // Связь на вечеринке пропадает — это нормально. Молчим, пока
        // не станет ясно, что дело не в одной неудачной попытке.
        failures += 1;
        if (failures === 5 && button) button.textContent = 'Нет связи с сервером';
      });
  }

  setInterval(poll, 3000);
  // Вернулись во вкладку — не ждать полного интервала.
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) poll();
  });
})();

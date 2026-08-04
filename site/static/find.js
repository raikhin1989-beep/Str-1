// Поиск по фотографии: убрать лишнее касание и объяснить паузу.
//
// Выбрал файл — отправляем сразу. На телефоне выбор фотографии это уже два-три
// касания, и третье, по кнопке «Распознать», ничего не решает. Кнопка остаётся
// в разметке и работает без скрипта: если JS отключён, страница остаётся
// рабочей, просто с лишним касанием.
//
// Ждать приходится секунд пять: этикетку читает OCR, потом текст опознаёт
// модель. Без объяснения эта пауза выглядит как зависший сайт.
(function () {
  var form = document.getElementById("byphoto");
  if (!form) return;

  var input = form.querySelector('input[type="file"]');
  var button = form.querySelector("[data-go]");
  var busy = form.querySelector("[data-busy]");
  var label = form.querySelector(".pickfile span");

  // Со скриптом кнопка не нужна вовсе: отправляем по выбору файла. Она
  // остаётся в разметке ради страниц без JS, но глаза не отвлекает и
  // не спорит с «Найти» за внимание.
  if (button) button.hidden = true;

  function start() {
    if (button) button.disabled = true;
    if (busy) busy.hidden = false;
  }

  input.addEventListener("change", function () {
    if (!input.files || !input.files.length) return;
    // Показываем, что именно выбрано: в галерее легко промахнуться.
    if (label) label.textContent = "📷 " + input.files[0].name;
    start();
    form.submit();
  });

  // Отправка кнопкой — тот же экран ожидания.
  form.addEventListener("submit", start);
})();

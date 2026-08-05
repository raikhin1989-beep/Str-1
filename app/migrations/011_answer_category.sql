-- Отдельный ответ «а какой это хотя бы класс».
--
-- До сих пор частичный балл можно было получить единственным способом:
-- назвать другой виски того же класса. То есть надо было знать хоть одно
-- название в этом классе — а человек, который уверенно скажет «это точно
-- островной односолодовый», но не вспомнит ни одной винокурни, не получал
-- ничего. На живой дегустации это и заметили: «в поле нет ввода класса
-- или региона, а за это допбаллы».
--
-- Отдельной таблицей, а не колонкой в answer: там whisky_id NOT NULL, и
-- ответ «класс без названия» туда просто не ложится. Перестраивать answer
-- ради этого — трогать то, что хранит уже сыгранные вечера; добавить рядом
-- дешевле и безопаснее.
--
-- Категория — строка, а не ссылка: что именно ею считать, решает дегустация
-- (category_level: класс или регион), и список классов живёт в коде.
CREATE TABLE answer_category (
    id             INTEGER PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
    round          TEXT NOT NULL,
    sample_no      INTEGER NOT NULL,
    category       TEXT NOT NULL,
    UNIQUE (participant_id, round, sample_no)
);

CREATE INDEX idx_answer_category_participant ON answer_category(participant_id);

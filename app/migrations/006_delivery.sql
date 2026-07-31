-- Отметки об отправленных сообщениях.
--
-- Пишется только УСПЕШНАЯ отправка, и на участника с видом сообщения стоит
-- UNIQUE. Из этого следует ровно то поведение, которое нужно вечером:
-- повторное нажатие «разослать» никому не пришлёт второй раз, но догонит тех,
-- кому не дошло, и тех, кто привязал телеграм уже после первой рассылки.
--
-- Отдельная таблица, а не флаг на дегустации: флаг отвечал бы «рассылка была»,
-- а спрашивать надо «дошло ли до этого человека».
CREATE TABLE delivery (
    id             INTEGER PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
    kind           TEXT NOT NULL,
    sent_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (participant_id, kind)
);

-- Цены по российским магазинам (WineStyle, Декантер), проверено 31.07.2026.
--
-- Точное совпадение бутылки нашлось только у Kemlya: остальные четыре — трэвел-
-- ретейл, в российскую розницу они не попадают вовсе. Для них цена посчитана от
-- ближайшего розлива того же производителя, и в notes написано, от чего именно:
-- иначе через полгода никто не поймёт, откуда взялась цифра.
--
-- UPDATE трогает только строки с source='ai' — правки из админки не затираются.

-- Точное попадание: тот же розлив, тот же объём, та же крепость, деревянный ящик.
-- https://winestyle.ru/products/Kemlya-American-Oak-wooden-box.html — 17 490 ₽
UPDATE whisky SET
    price_rub = 17490,
    notes = notes || ' Цена: 17 490 ₽ (WineStyle, ровно этот розлив 0,7 л 49,5 % в деревянном ящике), 31.07.2026.'
WHERE name = 'Kemlya American Oak' AND source = 'ai';

-- В рознице продаётся литровая версия: 15 380 ₽ (Декантер) и 19 990 ₽ (WineStyle).
-- Наша бутылка 0,7 л — пересчёт по объёму даёт 11–14 тысяч.
UPDATE whisky SET
    price_rub = 12000,
    notes = notes || ' Цена ориентировочная: в России продаётся литровая версия — 15 380 ₽ (Декантер) и 19 990 ₽ (WineStyle), в пересчёте на 0,7 л это 11–14 тыс., 31.07.2026.'
WHERE name = 'The Dalmore The Quartet' AND source = 'ai';

-- Обычный литровый Black Label: 4 390–7 750 ₽ у разных магазинов.
-- Trэвел-версия Triple Cask по цене примерно там же.
UPDATE whisky SET
    price_rub = 5500,
    notes = notes || ' Цена ориентировочная: обычный литровый Black Label стоит 4 390–7 750 ₽ (WineStyle, Декантер), трэвел-версия Triple Cask примерно там же, 31.07.2026.'
WHERE name = 'Johnnie Walker Black Label Triple Cask Edition' AND source = 'ai';

-- Обычный Single Barrel Select 0,7 л (45 %): 6 990 ₽ (WineStyle), 8 020 ₽ (Декантер).
-- Наш 100 proof крепче и редче, поэтому дороже.
UPDATE whisky SET
    price_rub = 9000,
    notes = notes || ' Цена ориентировочная: обычный Single Barrel Select 0,7 л 45 % стоит 6 990 ₽ (WineStyle) и 8 020 ₽ (Декантер); 100 proof дороже, 31.07.2026.'
WHERE name = 'Jack Daniel''s Single Barrel 100 Proof' AND source = 'ai';

-- Ближайшие по духу хересные Aberlour 0,7 л: A'bunadh Alba 14 470 ₽,
-- 16 Double Cask 13 570 ₽, 14 Double Cask 11 000 ₽ (Декантер).
UPDATE whisky SET
    price_rub = 13000,
    notes = notes || ' Цена ориентировочная: сопоставимые хересные Aberlour 0,7 л стоят 11 000–14 470 ₽ (Декантер, A''bunadh Alba и Double Cask), 31.07.2026.'
WHERE name = 'Aberlour Suthainn Double Sherry Cask Solera' AND source = 'ai';

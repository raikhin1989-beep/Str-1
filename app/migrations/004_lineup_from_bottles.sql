-- Состав первой дегустации, сверенный с самими коробками (фотографии от 31.07.2026).
--
-- Что изменилось против предположений миграции 002:
--   * Dewar's 12 из состава ушёл — его на столе нет;
--   * «джек сингл баррел ржаной» оказался Single Barrel 100 Proof — это
--     теннесси-виски, а не ржаной, и 50 %, а не 47;
--   * «аберлоу 13» оказался Suthainn Double Sherry Cask Solera — без заявленного
--     возраста, 48 % и без холодной фильтрации;
--   * добавилась пятая бутылка: Kemlya American Oak, российский односолодовый
--     из одной бочки из-под бурбона, 49,5 %.
--
-- UPDATE трогает только строки с source='ai': то, что уже поправили руками
-- в админке, миграция не затирает. DELETE срабатывает лишь для позиций,
-- не попавших ни в одну дегустацию — иначе состав уже налитого вечера
-- развалился бы задним числом.
--
-- Крепость, класс, бочки и фильтрация ниже взяты с коробок. Ноты вкуса взяты
-- с коробки там, где производитель их напечатал (Dalmore, Jack Daniel's,
-- Aberlour), и написаны описательно там, где нет (Johnnie Walker, Kemlya).
-- Цены — грубый ориентир российской розницы, а не котировка.

-- 1. Dalmore The Quartet: цифры сошлись, ноты заменены на печатные с коробки.
UPDATE whisky SET
    cask = 'первого налива ex-bourbon, херес Matusalem и Apostoles, французский Cabernet Sauvignon',
    filtration = 'неизвестно',
    colour = 'тёмное золото с медным отливом; цвет подправлен карамельным колером',
    nose = 'мадагаскарская ваниль, засахаренный красный апельсин, спелый красный виноград',
    palate = 'рождественский штоллен, изюм в хересе, мягкая тягучая лакрица',
    finish = 'груша дюшес с малиновым кули и шоколадные трюфели',
    notes = 'Traveller''s Exclusive, 0,7 л, 41,5 %. Крепость, бочки и ноты — с коробки. Там же указано подкрашивание карамельным колером (mit Farbstoff / Zuckerkulör).'
WHERE name = 'The Dalmore The Quartet' AND source = 'ai';

-- 2. Johnnie Walker Black Label Triple Cask Edition: бочки на этикетке названы
-- прямо, крепость на ней не написана — считаем по таблице пищевой ценности.
UPDATE whisky SET
    abv = 40.0,
    cask = 'ручной отбор: ex-bourbon, бочки из-под скотча и бочки из-под рома',
    nose = 'ваниль и сушёные фрукты поверх узнаваемого лёгкого дымка, сладковатая нота от ромовых бочек',
    palate = 'сладкая карамель и специи, дым держится фоном и не забивает',
    finish = 'среднее, дымно-сладкое',
    notes = 'Travel Exclusive, 1 л. Крепость 40 % посчитана по этикетке: 33 порции по 30 мл, 9,5 г спирта на порцию. Возраст не заявлен. Штрих-код 5000267170251. Ноты описательные, на коробке их нет.'
WHERE name = 'Johnnie Walker Black Label Triple Cask Edition' AND source = 'ai';

-- 3. Dewar's 12 в состав не попал.
DELETE FROM whisky
WHERE name = 'Dewar''s 12 Year Old'
  AND NOT EXISTS (SELECT 1 FROM tasting_whisky WHERE whisky_id = whisky.id);

-- 4. Не ржаной Jack Daniel's, а Single Barrel 100 Proof.
DELETE FROM whisky
WHERE name = 'Jack Daniel''s Single Barrel Rye'
  AND NOT EXISTS (SELECT 1 FROM tasting_whisky WHERE whisky_id = whisky.id);

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Jack Daniel''s Single Barrel 100 Proof', 'Jack Daniel''s', 'теннесси', 'Tennessee',
       50.0, NULL,
       'новая обожжённая американская бочка ручной работы, розлив из одной бочки, bottled in bond',
       'кукуруза, рожь, ячменный солод', 'неизвестно', 7000, 'насыщенная медь',
       'поджаренный дуб, сладкая ваниль и лёгкая пряность',
       'плотный и сладкий: ваниль, карамель, дубовые специи; 50 % чувствуются тёплой волной',
       'долгое и на удивление мягкое для такой крепости, с ванилью и дубом',
       'Travelers'' Exclusive, 0,7 л, 50 % (100 proof), bottled in bond. Крепость, класс и ноты — с коробки. Угольная фильтрация по-теннессийски (Lincoln County Process) — это не холодная фильтрация, про неё на коробке ничего.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Jack Daniel''s Single Barrel 100 Proof');

-- 5. Не Aberlour 13, а Suthainn.
DELETE FROM whisky
WHERE name = 'Aberlour 13 Year Old Double Cask Matured'
  AND NOT EXISTS (SELECT 1 FROM tasting_whisky WHERE whisky_id = whisky.id);

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Aberlour Suthainn Double Sherry Cask Solera', 'Aberlour', 'односолодовый скотч',
       'Speyside', 48.0, NULL,
       'двойная выдержка: американский дуб и олоросо; часть партии остаётся в хересных бочках американского и испанского дуба — солера',
       'ячменный солод', 'нет', 11000, 'тёмное золото с медным отливом',
       'густой херес и сухофрукты, поверх ваниль и ирис от американского дуба',
       'яблоки в карамели и корица, плотная хересная сладость',
       'долгое, насыщенно-фруктовое, с ноткой пряности',
       'Travel Exclusive, 0,7 л, 48 %, без холодной фильтрации. Возраст не заявлен: solera, а не выдержка в годах. Крепость, бочки и ноты — с тубуса. Штрих-код 5000299639146.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Aberlour Suthainn Double Sherry Cask Solera');

-- 6. Пятая бутылка, которой в справочнике не было вовсе.
INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Kemlya American Oak', 'Kemlya Distillery', 'односолодовый (не Шотландия)',
       'Россия', 49.5, NULL,
       'одна бочка из-под бурбона, американский дуб',
       'ячменный солод', 'нет', 9000, 'светлое золото, цвет натуральный — без колера',
       'ваниль и солод, свежая сдоба, за ними груша и мёд',
       'плотный и маслянистый: ваниль, злаковая сладость, дубовая пряность; 49,5 % дают ощутимое тепло',
       'долгое и сухое, с дубом и лёгкой горчинкой',
       'Duty free only, 0,7 л, 49,5 %. На акцизной наклейке — «Солодовый виски КЕМЛЯ АМЕРИКАН ОУК», штрих-код 4601823016535. Крепость, бочка, отсутствие колера и холодной фильтрации — с коробки. Ноты описательные, на коробке их нет.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Kemlya American Oak');

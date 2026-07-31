-- Справочник для первой дегустации, заполнен заранее (см. docs/TASTING-001.md).
--
-- source='ai' стоит намеренно: тексты нот и оценки цен написаны моделью, а не
-- списаны с этикетки, и на публичной карточке у них будет пометка «данные
-- ориентировочные». Когда данные сверят с бутылками, пометку снимают правкой
-- записи в админке.
--
-- Что подтверждено внешними источниками, а что нет:
--   Dalmore The Quartet    — 41,5 %, четыре бочки: подтверждено (WhiskyNotes, Moodie Davitt)
--   Aberlour 13 Double Cask — 40 %, американский дуб + олоросо: подтверждено (The Whiskey Wash, Whiskybase)
--   Dewar's 12, JW Black Triple Cask, JD Single Barrel Rye — класс и регион
--   известны, крепость проставлена по типовым розливам и требует сверки с бутылкой.
-- Цены — грубый ориентир для российской розницы, а не котировка.
--
-- INSERT берёт только те названия, которых ещё нет: повторный прогон миграции
-- ничего не задвоит, а правки, сделанные в админке, не затрёт.

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Dalmore The Quartet', 'Dalmore', 'односолодовый скотч', 'Highland',
       41.5, NULL,
       'четыре финиша: первого налива ex-bourbon, Matusalem 30 лет, Apostoles 30 лет, Cabernet Sauvignon',
       'ячменный солод', 'вероятно да', 12000, 'густое красное дерево',
       'апельсиновая цедра и тёмный шоколад, за ними сушёная вишня и ореховая сладость хереса',
       'плотный и сладкий: изюм, кофе, немного кожи; спирт почти не чувствуется',
       'долгое, с какао и лёгкой горчинкой дубовых танинов',
       'Трэвел-ретейл. Данные не сверены с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Dalmore The Quartet');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Dewar''s 12 Year Old', 'Dewar''s', 'купажированный скотч', NULL,
       40.0, 12,
       'двойное вызревание: после купажирования выдержка продолжается в дубе',
       'ячменный солод и зерно', 'вероятно да', 3500, 'светлый янтарь',
       'мягкий мёд, ваниль и спелое яблоко, немного вересковой травы',
       'гладкий и округлый: карамель, груша, лёгкая ореховая нота',
       'короткое и сладковатое, с намёком на дым',
       'Крепость сверить с бутылкой. Данные не сверены с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Dewar''s 12 Year Old');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Johnnie Walker Black Label Triple Cask Edition', 'Johnnie Walker',
       'купажированный скотч', NULL, 40.0, NULL,
       'три типа бочек, включая обожжённый американский дуб',
       'ячменный солод и зерно', 'вероятно да', 4500, 'тёплое золото',
       'ваниль и сушёные фрукты поверх узнаваемого лёгкого дымка',
       'сладкая карамель и специи, дым держится фоном и не забивает',
       'среднее, дымно-сладкое',
       'Трэвел-ретейл. Крепость сверить с бутылкой. Данные не сверены с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Johnnie Walker Black Label Triple Cask Edition');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Jack Daniel''s Single Barrel Rye', 'Jack Daniel''s', 'ржаной', 'Tennessee',
       47.0, NULL,
       'новая обожжённая американская бочка, розлив из одной бочки',
       'рожь (около 70 %), кукуруза, ячменный солод', 'нет', 6000, 'тёмная медь',
       'ржаная пряность, укроп и чёрный перец, за ними ваниль и жжёный сахар',
       'острый и сухой: перец, корица, дубовая горчинка; заметно крепче остальных',
       'длинное, пряное, с сухим дубом',
       'Крепость сверить с бутылкой (встречаются розливы 45 %). Данные не сверены с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Jack Daniel''s Single Barrel Rye');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Aberlour 13 Year Old Double Cask Matured', 'Aberlour', 'односолодовый скотч',
       'Speyside', 40.0, 13,
       'американский дуб и бочки из-под олоросо',
       'ячменный солод', 'вероятно да', 7000, 'тёмное золото с медным отливом',
       'мёд, печёное яблоко и сухофрукты, за ними марципан',
       'мягкий и сладкий: изюм, корица, немного апельсиновой цедры',
       'среднее, тёплое, с медово-ореховой нотой',
       'Трэвел-ретейл. Данные не сверены с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Aberlour 13 Year Old Double Cask Matured');

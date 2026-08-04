-- Справочник ходовых виски: то, из чего участники выбирают ответ.
--
-- Составлен целиком нами, а не скопирован из магазина: описания и ноты
-- в каталогах WineStyle, Декантера и Whiskybase — их контент, и
-- перепубликовывать его нельзя. Цена — ориентир для российской розницы
-- на август 2026, а не котировка.
--
-- Всё уезжает с source='ai': крепость и возраст даны по стандартным розливам,
-- у трэвел-ретейла и старых партий они другие. На публичной карточке из-за
-- этого стоит пометка «данные ориентировочные». Для конкретного вечера админ
-- сверяет цифры с бутылкой и правит руками — так сделано для пяти бутылок
-- первой дегустации (см. docs/TASTING-001.md).
--
-- Файл сгенерирован: python3 tools/make_catalogue.py
-- INSERT берёт только те названия, которых ещё нет: повторный прогон
-- миграции ничего не задвоит, а правки из админки не затрёт.

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glenfiddich 12', 'Glenfiddich', 'односолодовый скотч', 'Speyside', 40, 12, 'американский и европейский дуб', 'ячменный солод', 'да', 4500, 'светлое золото', 'груша, яблоко, лёгкая ваниль', 'мягкий, солодовый, фруктовый', 'среднее, чуть дубовое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glenfiddich 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glenfiddich 15 Solera', 'Glenfiddich', 'односолодовый скотч', 'Speyside', 40, 15, 'солера: бурбон, херес, новый дуб', 'ячменный солод', 'да', 8000, 'тёмное золото', 'мёд, марципан, сухофрукты', 'плотный, пряный, медовый', 'долгое, тёплое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glenfiddich 15 Solera');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Glenlivet 12', 'The Glenlivet', 'односолодовый скотч', 'Speyside', 40, 12, 'бурбон и херес', 'ячменный солод', 'да', 4700, 'светлое золото', 'цветы, цитрус, ваниль', 'лёгкий, ананасовый, мягкий', 'среднее, чистое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Glenlivet 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Glenlivet 15 French Oak', 'The Glenlivet', 'односолодовый скотч', 'Speyside', 40, 15, 'финиш во французском дубе', 'ячменный солод', 'да', 9000, 'золото', 'миндаль, ирис, специи', 'маслянистый, ореховый', 'долгое, пряное', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Glenlivet 15 French Oak');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Macallan 12 Double Cask', 'The Macallan', 'односолодовый скотч', 'Speyside', 40, 12, 'херес: американский и европейский дуб', 'ячменный солод', 'да', 12000, 'тёплый янтарь', 'ваниль, изюм, апельсин', 'сладкий, хересный, древесный', 'долгое, сушёные фрукты', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Macallan 12 Double Cask');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Macallan 12 Sherry Oak', 'The Macallan', 'односолодовый скотч', 'Speyside', 40, 12, 'олоросо, испанский дуб', 'ячменный солод', 'да', 16000, 'красное дерево', 'сухофрукты, имбирь, дуб', 'густой, хересный, пряный', 'долгое, сладко-древесное', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Macallan 12 Sherry Oak');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Balvenie DoubleWood 12', 'The Balvenie', 'односолодовый скотч', 'Speyside', 43, 12, 'бурбон, финиш в олоросо', 'ячменный солод', 'да', 9000, 'тёплое золото', 'мёд, ваниль, херес', 'сладкий, ореховый, сливочный', 'долгое, медовое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Balvenie DoubleWood 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Balvenie Caribbean Cask 14', 'The Balvenie', 'односолодовый скотч', 'Speyside', 43, 14, 'бурбон, финиш в ромовой бочке', 'ячменный солод', 'да', 13000, 'золото', 'тропические фрукты, ваниль', 'сладкий, ромовый, мягкий', 'долгое, карамельное', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Balvenie Caribbean Cask 14');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Aberlour 12 Double Cask', 'Aberlour', 'односолодовый скотч', 'Speyside', 40, 12, 'бурбон и олоросо', 'ячменный солод', 'да', 6000, 'янтарь', 'яблоко, херес, специи', 'сладкий, пряный, фруктовый', 'среднее, тёплое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Aberlour 12 Double Cask');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Aberlour A''bunadh', 'Aberlour', 'односолодовый скотч', 'Speyside', 60, NULL, 'олоросо, бочковая крепость', 'ячменный солод', 'нет', 14000, 'тёмная медь', 'изюм, шоколад, вишня', 'мощный, хересный, без воды почти жгучий', 'очень долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Aberlour A''bunadh');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glenmorangie The Original 10', 'Glenmorangie', 'односолодовый скотч', 'Highland', 40, 10, 'бурбон первого налива', 'ячменный солод', 'да', 5500, 'светлое золото', 'цитрус, ваниль, персик', 'лёгкий, сливочный, цветочный', 'среднее, свежее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glenmorangie The Original 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glenmorangie Lasanta 12', 'Glenmorangie', 'односолодовый скотч', 'Highland', 43, 12, 'финиш в олоросо и PX', 'ячменный солод', 'да', 8000, 'тёплый янтарь', 'херес, орех, тоффи', 'сладкий, ореховый', 'долгое, сушёные фрукты', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glenmorangie Lasanta 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glenmorangie Quinta Ruban 14', 'Glenmorangie', 'односолодовый скотч', 'Highland', 46, 14, 'финиш в портвейновых бочках', 'ячменный солод', 'нет', 9500, 'медь с розовым', 'тёмный шоколад, мята, слива', 'плотный, шоколадный', 'долгое, сухое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glenmorangie Quinta Ruban 14');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Ardbeg 10', 'Ardbeg', 'односолодовый скотч', 'Islay', 46, 10, 'бурбон', 'ячменный солод', 'нет', 8000, 'бледное золото', 'торф, дым, морской бриз, лимон', 'мощный дым, соль, сажа', 'очень долгое, дымное', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Ardbeg 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Ardbeg An Oa', 'Ardbeg', 'односолодовый скотч', 'Islay', 46.6, NULL, 'PX, новый дуб, бурбон', 'ячменный солод', 'нет', 9500, 'золото', 'дым, шоколад, ирис', 'сладковатый дым, специи', 'долгое, мягко-дымное', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Ardbeg An Oa');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Ardbeg Uigeadail', 'Ardbeg', 'односолодовый скотч', 'Islay', 54.2, NULL, 'бурбон и олоросо, бочковая крепость', 'ячменный солод', 'нет', 14000, 'тёмное золото', 'дым, изюм, кофе', 'густой, дымно-хересный', 'очень долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Ardbeg Uigeadail');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Laphroaig 10', 'Laphroaig', 'односолодовый скотч', 'Islay', 40, 10, 'бурбон', 'ячменный солод', 'да', 7500, 'золото', 'йод, торф, аптека, морская соль', 'медицинский дым, соль, сладость', 'долгое, дымное', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Laphroaig 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Laphroaig Quarter Cask', 'Laphroaig', 'односолодовый скотч', 'Islay', 48, NULL, 'малая бочка, двойное вызревание', 'ячменный солод', 'нет', 9500, 'тёплое золото', 'дым, ваниль, кокос', 'плотный, дымно-сладкий', 'долгое, маслянистое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Laphroaig Quarter Cask');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Lagavulin 16', 'Lagavulin', 'односолодовый скотч', 'Islay', 43, 16, 'бурбон и херес', 'ячменный солод', 'да', 14000, 'тёмный янтарь', 'торфяной дым, йод, сухофрукты', 'густой, дымный, чуть сладкий', 'очень долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Lagavulin 16');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Talisker 10', 'Talisker', 'односолодовый скотч', 'Isle of Skye', 45.8, 10, 'бурбон', 'ячменный солод', 'да', 7500, 'золото', 'дым, морская соль, перец', 'перечный, дымный, солёный', 'долгое, перечное', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Talisker 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Talisker Storm', 'Talisker', 'односолодовый скотч', 'Isle of Skye', 45.8, NULL, 'бурбон, часть — сильно обожжённые', 'ячменный солод', 'да', 8500, 'золото', 'дым, соль, цитрус', 'острый, дымный', 'долгое, перечное', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Talisker Storm');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Oban 14', 'Oban', 'односолодовый скотч', 'Highland', 43, 14, 'бурбон', 'ячменный солод', 'да', 11000, 'тёплое золото', 'морская соль, апельсин, лёгкий дым', 'сладко-солёный, фруктовый', 'долгое, солоноватое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Oban 14');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Highland Park 12 Viking Honour', 'Highland Park', 'односолодовый скотч', 'Orkney', 40, 12, 'херес', 'ячменный солод', 'да', 7000, 'янтарь', 'вереск, мёд, лёгкий дым', 'сбалансированный, медово-дымный', 'среднее, тёплое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Highland Park 12 Viking Honour');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Highland Park 18', 'Highland Park', 'односолодовый скотч', 'Orkney', 43, 18, 'херес', 'ячменный солод', 'да', 25000, 'тёмный янтарь', 'мёд, сухофрукты, торф', 'богатый, хересный, дымный', 'очень долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Highland Park 18');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Bowmore 12', 'Bowmore', 'односолодовый скотч', 'Islay', 40, 12, 'бурбон и херес', 'ячменный солод', 'да', 7000, 'тёплое золото', 'дым, лимон, мёд', 'дымный, сладкий, морской', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Bowmore 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Bunnahabhain 12', 'Bunnahabhain', 'односолодовый скотч', 'Islay', 46.3, 12, 'херес', 'ячменный солод', 'нет', 9500, 'тёмное золото', 'орех, херес, лёгкая соль', 'сладкий, ореховый, почти без дыма', 'долгое, мягкое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Bunnahabhain 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Caol Ila 12', 'Caol Ila', 'односолодовый скотч', 'Islay', 43, 12, 'бурбон', 'ячменный солод', 'да', 8500, 'бледное золото', 'дым, лайм, морской воздух', 'дымный, свежий, маслянистый', 'долгое, чистое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Caol Ila 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Bruichladdich The Classic Laddie', 'Bruichladdich', 'односолодовый скотч', 'Islay', 50, NULL, 'бурбон', 'ячменный солод', 'нет', 9500, 'светлое золото', 'ячмень, цветы, морской бриз', 'яркий, солодовый, без торфа', 'долгое, свежее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Bruichladdich The Classic Laddie');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Port Charlotte 10', 'Bruichladdich', 'односолодовый скотч', 'Islay', 50, 10, 'бурбон и вино', 'ячменный солод', 'нет', 11000, 'золото', 'торф, ваниль, соль', 'плотный дым, сладость', 'очень долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Port Charlotte 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Kilchoman Machir Bay', 'Kilchoman', 'односолодовый скотч', 'Islay', 46, NULL, 'бурбон и олоросо', 'ячменный солод', 'нет', 10000, 'светлое золото', 'молодой торф, цитрус, ваниль', 'дымный, яркий, свежий', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Kilchoman Machir Bay');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Springbank 10', 'Springbank', 'односолодовый скотч', 'Campbeltown', 46, 10, 'бурбон и херес', 'ячменный солод', 'нет', 12000, 'золото', 'промасленная бумага, соль, фрукты', 'маслянистый, слегка дымный', 'долгое, сложное', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Springbank 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glen Scotia Double Cask', 'Glen Scotia', 'односолодовый скотч', 'Campbeltown', 46, NULL, 'бурбон, финиш в PX', 'ячменный солод', 'нет', 8000, 'янтарь', 'изюм, соль, ваниль', 'сладко-солёный, пряный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glen Scotia Double Cask');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Dalmore 12', 'The Dalmore', 'односолодовый скотч', 'Highland', 40, 12, 'бурбон и олоросо Матусалем', 'ячменный солод', 'да', 9500, 'медь', 'апельсин, шоколад, херес', 'плотный, апельсиново-хересный', 'долгое, сладкое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Dalmore 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Dalmore 15', 'The Dalmore', 'односолодовый скотч', 'Highland', 40, 15, 'три вида хереса', 'ячменный солод', 'да', 18000, 'тёмная медь', 'мандарин, корица, изюм', 'густой, хересный', 'очень долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Dalmore 15');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glenfarclas 12', 'Glenfarclas', 'односолодовый скотч', 'Speyside', 43, 12, 'олоросо', 'ячменный солод', 'да', 7000, 'янтарь', 'херес, солод, орех', 'сладкий, хересный, тёплый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glenfarclas 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glenfarclas 105', 'Glenfarclas', 'односолодовый скотч', 'Speyside', 60, NULL, 'олоросо, бочковая крепость', 'ячменный солод', 'нет', 12000, 'тёмное золото', 'херес, специи, дуб', 'мощный, сладко-пряный', 'очень долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glenfarclas 105');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'GlenDronach 12 Original', 'GlenDronach', 'односолодовый скотч', 'Highland', 43, 12, 'PX и олоросо', 'ячменный солод', 'нет', 8500, 'тёмный янтарь', 'изюм, херес, специи', 'густой, сладкий, хересный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'GlenDronach 12 Original');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Cragganmore 12', 'Cragganmore', 'односолодовый скотч', 'Speyside', 40, 12, 'бурбон и херес', 'ячменный солод', 'да', 7000, 'золото', 'сушёные травы, мёд, орех', 'сложный, солодовый', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Cragganmore 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Dalwhinnie 15', 'Dalwhinnie', 'односолодовый скотч', 'Highland', 43, 15, 'бурбон', 'ячменный солод', 'да', 8500, 'светлое золото', 'вереск, мёд, лёгкий дым', 'мягкий, медовый', 'среднее, чистое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Dalwhinnie 15');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Cardhu 12', 'Cardhu', 'односолодовый скотч', 'Speyside', 40, 12, 'бурбон', 'ячменный солод', 'да', 6000, 'золото', 'яблоко, ваниль, солод', 'лёгкий, сладкий', 'короткое, мягкое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Cardhu 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Auchentoshan 12', 'Auchentoshan', 'односолодовый скотч', 'Lowland', 40, 12, 'бурбон и херес', 'ячменный солод', 'да', 6500, 'светлое золото', 'лимон, миндаль, карамель', 'лёгкий, тройной перегонки, мягкий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Auchentoshan 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glen Grant 12', 'Glen Grant', 'односолодовый скотч', 'Speyside', 43, 12, 'бурбон', 'ячменный солод', 'да', 5500, 'бледное золото', 'яблоко, орех, ваниль', 'чистый, солодовый', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glen Grant 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Tomatin 12', 'Tomatin', 'односолодовый скотч', 'Highland', 43, 12, 'бурбон и херес', 'ячменный солод', 'да', 5500, 'золото', 'яблоко, мёд, ваниль', 'мягкий, фруктовый', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Tomatin 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Old Pulteney 12', 'Old Pulteney', 'односолодовый скотч', 'Highland', 40, 12, 'бурбон', 'ячменный солод', 'да', 6500, 'золото', 'морская соль, ваниль, яблоко', 'солоновато-сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Old Pulteney 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Deanston 12', 'Deanston', 'односолодовый скотч', 'Highland', 46.3, 12, 'бурбон', 'ячменный солод', 'нет', 7000, 'золото', 'мёд, солод, воск', 'маслянистый, медовый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Deanston 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Isle of Jura 10', 'Jura', 'односолодовый скотч', 'Jura', 40, 10, 'бурбон, финиш в олоросо', 'ячменный солод', 'да', 6000, 'золото', 'груша, лёгкий дым, солод', 'мягкий, чуть дымный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Isle of Jura 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Tobermory 12', 'Tobermory', 'односолодовый скотч', 'Isle of Mull', 46.3, 12, 'бурбон', 'ячменный солод', 'нет', 8500, 'золото', 'фрукты, воск, орех', 'маслянистый, фруктовый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Tobermory 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'anCnoc 12', 'Knockdhu', 'односолодовый скотч', 'Highland', 40, 12, 'бурбон и херес', 'ячменный солод', 'да', 6000, 'светлое золото', 'мёд, лимон, солод', 'чистый, свежий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'anCnoc 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'BenRiach The Original Ten', 'BenRiach', 'односолодовый скотч', 'Speyside', 43, 10, 'бурбон, херес, виргинский дуб', 'ячменный солод', 'нет', 6500, 'золото', 'яблоко, ваниль, мёд', 'фруктовый, сливочный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'BenRiach The Original Ten');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Benromach 10', 'Benromach', 'односолодовый скотч', 'Speyside', 43, 10, 'бурбон и херес', 'ячменный солод', 'нет', 8000, 'янтарь', 'лёгкий дым, херес, кожа', 'старомодный, дымно-хересный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Benromach 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Craigellachie 13', 'Craigellachie', 'односолодовый скотч', 'Speyside', 46, 13, 'бурбон и херес', 'ячменный солод', 'нет', 8500, 'золото', 'сера, ананас, воск', 'плотный, необычный, мясистый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Craigellachie 13');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Aultmore 12', 'Aultmore', 'односолодовый скотч', 'Speyside', 46, 12, 'бурбон', 'ячменный солод', 'нет', 8000, 'светлое золото', 'трава, лимон, мёд', 'чистый, свежий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Aultmore 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Arran 10', 'Arran', 'односолодовый скотч', 'Isle of Arran', 46, 10, 'бурбон и херес', 'ячменный солод', 'нет', 7500, 'золото', 'цитрус, ваниль, солод', 'яркий, сливочный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Arran 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Singleton of Dufftown 12', 'Dufftown', 'односолодовый скотч', 'Speyside', 40, 12, 'бурбон и херес', 'ячменный солод', 'да', 5500, 'золото', 'яблоко, карамель, орех', 'мягкий, сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Singleton of Dufftown 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Speyburn 10', 'Speyburn', 'односолодовый скотч', 'Speyside', 40, 10, 'бурбон и херес', 'ячменный солод', 'да', 4500, 'светлое золото', 'яблоко, ваниль, травы', 'лёгкий, свежий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Speyburn 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Loch Lomond 12', 'Loch Lomond', 'односолодовый скотч', 'Highland', 46, 12, 'бурбон, три типа перегонки', 'ячменный солод', 'нет', 6500, 'золото', 'груша, лёгкий дым, ваниль', 'фруктовый с дымком', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Loch Lomond 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glengoyne 12', 'Glengoyne', 'односолодовый скотч', 'Highland', 43, 12, 'бурбон и херес', 'ячменный солод', 'да', 7500, 'золото', 'яблоко, орех, солод', 'мягкий, без дыма', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glengoyne 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Tamdhu 12', 'Tamdhu', 'односолодовый скотч', 'Speyside', 43, 12, 'только херес', 'ячменный солод', 'нет', 8500, 'янтарь', 'херес, специи, изюм', 'сладкий, хересный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Tamdhu 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Glenkinchie 12', 'Glenkinchie', 'односолодовый скотч', 'Lowland', 43, 12, 'бурбон', 'ячменный солод', 'да', 7000, 'светлое золото', 'трава, лимон, цветы', 'лёгкий, сухой', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Glenkinchie 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Clynelish 14', 'Clynelish', 'односолодовый скотч', 'Highland', 46, 14, 'бурбон', 'ячменный солод', 'нет', 10000, 'золото', 'воск, соль, цитрус', 'маслянистый, восковой', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Clynelish 14');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Johnnie Walker Red Label', 'Johnnie Walker', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 2200, 'золото', 'специи, лёгкий дым', 'резковатый, пряный', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Johnnie Walker Red Label');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Johnnie Walker Black Label 12', 'Johnnie Walker', 'купажированный скотч', NULL, 40, 12, 'разные бочки', 'ячменный солод и зерно', 'да', 4000, 'тёплое золото', 'ваниль, сухофрукты, дымок', 'сбалансированный, дымно-сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Johnnie Walker Black Label 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Johnnie Walker Double Black', 'Johnnie Walker', 'купажированный скотч', NULL, 40, NULL, 'сильно обожжённые бочки', 'ячменный солод и зерно', 'да', 5000, 'тёмное золото', 'дым, специи', 'дымный, плотный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Johnnie Walker Double Black');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Johnnie Walker Green Label 15', 'Johnnie Walker', 'купажированный скотч', NULL, 43, 15, 'купаж только солодов', 'ячменный солод', 'да', 8000, 'золото', 'трава, дым, фрукты', 'свежий, солодовый', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Johnnie Walker Green Label 15');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Johnnie Walker Blue Label', 'Johnnie Walker', 'купажированный скотч', NULL, 40, NULL, 'отборные бочки', 'ячменный солод и зерно', 'да', 30000, 'тёмное золото', 'мёд, дым, орех', 'гладкий, сложный', 'очень долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Johnnie Walker Blue Label');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Chivas Regal 12', 'Chivas Brothers', 'купажированный скотч', NULL, 40, 12, 'разные бочки', 'ячменный солод и зерно', 'да', 4000, 'золото', 'мёд, яблоко, ваниль', 'мягкий, сладковатый', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Chivas Regal 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Chivas Regal 18', 'Chivas Brothers', 'купажированный скотч', NULL, 40, 18, 'разные бочки', 'ячменный солод и зерно', 'да', 11000, 'тёмное золото', 'шоколад, сухофрукты', 'богатый, бархатный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Chivas Regal 18');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Ballantine''s Finest', 'Ballantine''s', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 2200, 'светлое золото', 'ваниль, яблоко', 'лёгкий, простой', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Ballantine''s Finest');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Ballantine''s 12', 'Ballantine''s', 'купажированный скотч', NULL, 40, 12, 'разные бочки', 'ячменный солод и зерно', 'да', 4200, 'золото', 'мёд, орех, ваниль', 'мягкий, сливочный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Ballantine''s 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Ballantine''s 17', 'Ballantine''s', 'купажированный скотч', NULL, 43, 17, 'разные бочки', 'ячменный солод и зерно', 'да', 12000, 'тёмное золото', 'мёд, дымок, специи', 'сложный, гладкий', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Ballantine''s 17');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'The Famous Grouse', 'Edrington', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 2000, 'золото', 'солод, карамель', 'простой, сладковатый', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'The Famous Grouse');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Dewar''s White Label', 'Dewar''s', 'купажированный скотч', NULL, 40, NULL, 'двойное вызревание', 'ячменный солод и зерно', 'да', 2200, 'светлое золото', 'мёд, трава', 'лёгкий, мягкий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Dewar''s White Label');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Dewar''s 12', 'Dewar''s', 'купажированный скотч', NULL, 40, 12, 'двойное вызревание', 'ячменный солод и зерно', 'да', 3800, 'золото', 'мёд, ваниль, яблоко', 'гладкий, округлый', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Dewar''s 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Dewar''s 15', 'Dewar''s', 'купажированный скотч', NULL, 40, 15, 'двойное вызревание', 'ячменный солод и зерно', 'да', 6000, 'тёмное золото', 'карамель, сухофрукты', 'плотный, сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Dewar''s 15');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Grant''s Triple Wood', 'William Grant & Sons', 'купажированный скотч', NULL, 40, NULL, 'три типа бочек', 'ячменный солод и зерно', 'да', 2000, 'золото', 'ваниль, ирис', 'простой, сладкий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Grant''s Triple Wood');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Monkey Shoulder', 'William Grant & Sons', 'купажированный скотч', NULL, 40, NULL, 'бурбон, купаж солодов', 'ячменный солод', 'да', 4500, 'золото', 'ваниль, апельсин, солод', 'сладкий, мягкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Monkey Shoulder');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Naked Malt', 'Edrington', 'купажированный скотч', NULL, 40, NULL, 'финиш в хересе, купаж солодов', 'ячменный солод', 'да', 4500, 'янтарь', 'изюм, ваниль', 'сладкий, хересный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Naked Malt');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Cutty Sark', 'La Martiniquaise', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 2000, 'бледное золото', 'цитрус, ваниль', 'лёгкий, сухой', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Cutty Sark');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'J&B Rare', 'Diageo', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 2000, 'светлое золото', 'трава, мёд', 'лёгкий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'J&B Rare');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Whyte & Mackay Triple Matured', 'Whyte & Mackay', 'купажированный скотч', NULL, 40, NULL, 'тройное вызревание', 'ячменный солод и зерно', 'да', 2200, 'золото', 'карамель, апельсин', 'мягкий, сладкий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Whyte & Mackay Triple Matured');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Teacher''s Highland Cream', 'Beam Suntory', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 2000, 'тёмное золото', 'дымок, солод', 'дымноватый, крепкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Teacher''s Highland Cream');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Black & White', 'Diageo', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 2000, 'золото', 'солод, лёгкий дым', 'простой, сухой', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Black & White');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Bell''s Original', 'Diageo', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 1900, 'золото', 'орех, специи', 'простой, пряный', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Bell''s Original');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'William Lawson''s', 'Bacardi', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 1800, 'светлое золото', 'ваниль, зерно', 'лёгкий, резковатый', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'William Lawson''s');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Label 5 Classic Black', 'La Martiniquaise', 'купажированный скотч', NULL, 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 1800, 'золото', 'карамель, зерно', 'простой', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Label 5 Classic Black');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Jameson', 'Midleton', 'ирландский', 'Ирландия', 40, NULL, 'бурбон и херес', 'ячменный солод и зерно', 'да', 3000, 'золото', 'ваниль, орех, цветы', 'гладкий, сладковатый', 'короткое, мягкое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Jameson');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Jameson Black Barrel', 'Midleton', 'ирландский', 'Ирландия', 40, NULL, 'сильно обожжённый бурбон', 'ячменный солод и зерно', 'да', 5000, 'тёмное золото', 'ваниль, ирис, специи', 'плотный, сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Jameson Black Barrel');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Bushmills 10 Single Malt', 'Bushmills', 'ирландский', 'Ирландия', 40, 10, 'бурбон и херес', 'ячменный солод', 'да', 5500, 'золото', 'мёд, ваниль, абрикос', 'мягкий, фруктовый', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Bushmills 10 Single Malt');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Tullamore D.E.W.', 'Tullamore', 'ирландский', 'Ирландия', 40, NULL, 'три типа бочек', 'ячменный солод и зерно', 'да', 3000, 'золото', 'яблоко, ваниль', 'мягкий, лёгкий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Tullamore D.E.W.');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Redbreast 12', 'Midleton', 'ирландский', 'Ирландия', 40, 12, 'бурбон и олоросо, single pot still', 'ячменный солод', 'да', 9500, 'тёмное золото', 'херес, специи, фрукты', 'маслянистый, пряный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Redbreast 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Connemara Peated', 'Cooley', 'ирландский', 'Ирландия', 40, NULL, 'бурбон, торфяной солод', 'ячменный солод', 'да', 6000, 'светлое золото', 'торф, мёд', 'дымный, сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Connemara Peated');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Teeling Small Batch', 'Teeling', 'ирландский', 'Ирландия', 46, NULL, 'финиш в ромовых бочках', 'ячменный солод и зерно', 'нет', 5500, 'золото', 'ваниль, ром, специи', 'сладкий, пряный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Teeling Small Batch');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Green Spot', 'Midleton', 'ирландский', 'Ирландия', 40, NULL, 'бурбон и херес, single pot still', 'ячменный солод', 'да', 9000, 'золото', 'яблоко, мята, ваниль', 'свежий, маслянистый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Green Spot');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Powers Gold Label', 'Midleton', 'ирландский', 'Ирландия', 43.2, NULL, 'бурбон, single pot still в составе', 'ячменный солод и зерно', 'да', 4500, 'золото', 'мёд, специи', 'пряный, плотный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Powers Gold Label');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Jack Daniel''s Old No. 7', 'Jack Daniel''s', 'теннесси', 'Tennessee', 40, NULL, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 3000, 'тёплое золото', 'ваниль, банан, карамель', 'сладкий, мягкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Jack Daniel''s Old No. 7');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Gentleman Jack', 'Jack Daniel''s', 'теннесси', 'Tennessee', 40, NULL, 'двойная угольная фильтрация', 'кукуруза, рожь, ячменный солод', 'неизвестно', 4500, 'золото', 'ваниль, карамель', 'очень мягкий, сладкий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Gentleman Jack');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Jack Daniel''s Single Barrel Select', 'Jack Daniel''s', 'теннесси', 'Tennessee', 45, NULL, 'одна бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 7000, 'медь', 'дуб, ваниль, специи', 'плотный, дубовый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Jack Daniel''s Single Barrel Select');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Jim Beam White Label', 'Jim Beam', 'бурбон', 'Kentucky', 40, 4, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 2200, 'золото', 'ваниль, зерно', 'простой, сладковатый', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Jim Beam White Label');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Jim Beam Black', 'Jim Beam', 'бурбон', 'Kentucky', 43, NULL, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 3500, 'медь', 'карамель, дуб', 'плотный, сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Jim Beam Black');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Maker''s Mark', 'Maker''s Mark', 'бурбон', 'Kentucky', 45, NULL, 'новая обожжённая бочка, пшеница вместо ржи', 'кукуруза, пшеница, ячменный солод', 'неизвестно', 5000, 'тёплая медь', 'ваниль, карамель, пшеничная сладость', 'мягкий, сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Maker''s Mark');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Wild Turkey 81', 'Wild Turkey', 'бурбон', 'Kentucky', 40.5, NULL, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 3500, 'медь', 'ваниль, апельсин', 'пряный, сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Wild Turkey 81');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Wild Turkey 101', 'Wild Turkey', 'бурбон', 'Kentucky', 50.5, NULL, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 4500, 'тёмная медь', 'ваниль, специи, дуб', 'мощный, пряный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Wild Turkey 101');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Buffalo Trace', 'Buffalo Trace', 'бурбон', 'Kentucky', 45, NULL, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 5000, 'медь', 'карамель, специи, дуб', 'сбалансированный, сладко-пряный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Buffalo Trace');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Four Roses Bourbon', 'Four Roses', 'бурбон', 'Kentucky', 40, NULL, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 3500, 'золото', 'груша, ваниль', 'лёгкий, фруктовый', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Four Roses Bourbon');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Woodford Reserve', 'Woodford Reserve', 'бурбон', 'Kentucky', 43.2, NULL, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 5500, 'медь', 'сухофрукты, ваниль, дуб', 'плотный, сложный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Woodford Reserve');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Bulleit Bourbon', 'Bulleit', 'бурбон', 'Kentucky', 45, NULL, 'новая обожжённая бочка, много ржи', 'кукуруза, рожь, ячменный солод', 'неизвестно', 4500, 'медь', 'рожь, ваниль, специи', 'пряный, сухой', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Bulleit Bourbon');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Knob Creek 9', 'Jim Beam', 'бурбон', 'Kentucky', 50, 9, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 6000, 'тёмная медь', 'дуб, карамель, орех', 'мощный, дубовый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Knob Creek 9');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Elijah Craig Small Batch', 'Heaven Hill', 'бурбон', 'Kentucky', 47, NULL, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 6000, 'медь', 'ваниль, дым, дуб', 'плотный, пряный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Elijah Craig Small Batch');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Eagle Rare 10', 'Buffalo Trace', 'бурбон', 'Kentucky', 45, 10, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 8000, 'тёмная медь', 'тоффи, апельсин, дуб', 'плотный, сложный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Eagle Rare 10');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Bulleit Rye', 'Bulleit', 'ржаной', 'Kentucky', 45, NULL, 'новая обожжённая бочка', 'рожь, ячменный солод', 'неизвестно', 5000, 'золото', 'ржаная пряность, укроп, ваниль', 'острый, сухой', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Bulleit Rye');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Rittenhouse Rye', 'Heaven Hill', 'ржаной', 'Kentucky', 50, NULL, 'новая обожжённая бочка', 'рожь, кукуруза, ячменный солод', 'неизвестно', 6000, 'медь', 'рожь, корица, дуб', 'пряный, плотный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Rittenhouse Rye');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Sazerac Rye', 'Buffalo Trace', 'ржаной', 'Kentucky', 45, NULL, 'новая обожжённая бочка', 'рожь, кукуруза, ячменный солод', 'неизвестно', 7000, 'золото', 'рожь, чёрный перец, ваниль', 'острый, сладковатый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Sazerac Rye');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Michter''s US*1 Bourbon', 'Michter''s', 'бурбон', 'Kentucky', 45.7, NULL, 'новая обожжённая бочка', 'кукуруза, рожь, ячменный солод', 'неизвестно', 9000, 'медь', 'карамель, ваниль, орех', 'мягкий, сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Michter''s US*1 Bourbon');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Suntory Toki', 'Suntory', 'японский', 'Япония', 43, NULL, 'американский дуб', 'ячменный солод и зерно', 'да', 6000, 'светлое золото', 'зелёное яблоко, мёд, базилик', 'лёгкий, свежий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Suntory Toki');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Hibiki Japanese Harmony', 'Suntory', 'японский', 'Япония', 43, NULL, 'пять типов бочек', 'ячменный солод и зерно', 'да', 14000, 'золото', 'мёд, апельсин, сандал', 'гладкий, сложный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Hibiki Japanese Harmony');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Yamazaki 12', 'Suntory', 'японский', 'Япония', 43, 12, 'бурбон, херес, мидзунара', 'ячменный солод', 'да', 30000, 'золото', 'персик, ваниль, японский дуб', 'мягкий, фруктовый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Yamazaki 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Hakushu 12', 'Suntory', 'японский', 'Япония', 43, 12, 'бурбон, лёгкий торф', 'ячменный солод', 'да', 30000, 'светлое золото', 'хвоя, груша, дымок', 'свежий, зелёный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Hakushu 12');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Nikka From The Barrel', 'Nikka', 'японский', 'Япония', 51.4, NULL, 'бочковая крепость, купаж', 'ячменный солод и зерно', 'нет', 8000, 'тёмное золото', 'карамель, специи, дуб', 'мощный, насыщенный', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Nikka From The Barrel');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Nikka Days', 'Nikka', 'японский', 'Япония', 40, NULL, 'разные бочки', 'ячменный солод и зерно', 'да', 6000, 'светлое золото', 'яблоко, ваниль', 'лёгкий, мягкий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Nikka Days');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Nikka Coffey Grain', 'Nikka', 'японский', 'Япония', 45, NULL, 'колонна Коффи, кукуруза', 'кукуруза', 'нет', 11000, 'золото', 'ваниль, кукурузная сладость', 'очень сладкий, маслянистый', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Nikka Coffey Grain');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Suntory Chita', 'Suntory', 'японский', 'Япония', 43, NULL, 'зерновой, три типа бочек', 'кукуруза', 'да', 12000, 'светлое золото', 'мёд, ваниль', 'лёгкий, сладкий', 'короткое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Suntory Chita');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Kavalan Classic', 'Kavalan', 'односолодовый (не Шотландия)', 'Тайвань', 40, NULL, 'разные бочки, жаркий климат', 'ячменный солод', 'да', 12000, 'золото', 'манго, ваниль, кокос', 'тропический, сладкий', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Kavalan Classic');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Amrut Fusion', 'Amrut', 'односолодовый (не Шотландия)', 'Индия', 50, NULL, 'бурбон, часть солода торфяная', 'ячменный солод', 'нет', 11000, 'тёмное золото', 'дым, апельсин, специи', 'плотный, дымно-фруктовый', 'долгое', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Amrut Fusion');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Paul John Brilliance', 'Paul John', 'односолодовый (не Шотландия)', 'Индия', 46, NULL, 'бурбон', 'ячменный солод', 'нет', 8000, 'золото', 'мёд, ваниль, специи', 'сладкий, плотный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Paul John Brilliance');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Penderyn Madeira', 'Penderyn', 'односолодовый (не Шотландия)', 'Уэльс', 46, NULL, 'финиш в бочках из-под мадеры', 'ячменный солод', 'нет', 9000, 'светлое золото', 'цитрус, ваниль, изюм', 'лёгкий, сладковатый', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Penderyn Madeira');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Mackmyra Brukswhisky', 'Mackmyra', 'односолодовый (не Шотландия)', 'Швеция', 41.4, NULL, 'шведский дуб и бурбон', 'ячменный солод', 'нет', 8000, 'золото', 'ваниль, брусника, дуб', 'свежий, ягодный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Mackmyra Brukswhisky');

INSERT INTO whisky (name, distillery, wclass, region, abv, age_years, cask, grain,
                    filtration, price_rub, colour, nose, palate, finish, notes, source)
SELECT 'Teerenpeli Kaski', 'Teerenpeli', 'односолодовый (не Шотландия)', 'Финляндия', 43, NULL, 'херес', 'ячменный солод', 'нет', 9000, 'янтарь', 'изюм, орех, ваниль', 'сладкий, хересный', 'среднее', 'Данные ориентировочные: сверьте крепость и цену с бутылкой.', 'ai'
WHERE NOT EXISTS (SELECT 1 FROM whisky WHERE name = 'Teerenpeli Kaski');

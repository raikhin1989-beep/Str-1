-- Публичный код дегустации: он в ссылке и в QR-коде, по которому гости
-- попадают на регистрацию. Отдельно от id, чтобы адрес нельзя было угадать
-- перебором и чужой человек не записался на закрытую дегустацию.
ALTER TABLE tasting ADD COLUMN public_code TEXT;

CREATE UNIQUE INDEX idx_tasting_public_code ON tasting(public_code)
WHERE public_code IS NOT NULL;

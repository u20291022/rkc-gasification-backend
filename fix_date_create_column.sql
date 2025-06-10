-- Если поле уже создано, сначала удалите его
-- Выполните этот SQL в pgAdmin

-- Удаляем поле если оно уже существует
ALTER TABLE s_gazifikacia.t_gazifikacia_data 
DROP COLUMN IF EXISTS date_create;

-- Создаем поле заново с правильным типом
ALTER TABLE s_gazifikacia.t_gazifikacia_data 
ADD COLUMN date_create TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Устанавливаем значение по умолчанию для существующих записей
UPDATE s_gazifikacia.t_gazifikacia_data 
SET date_create = CURRENT_TIMESTAMP 
WHERE date_create IS NULL;

-- Добавляем комментарий к полю
COMMENT ON COLUMN s_gazifikacia.t_gazifikacia_data.date_create IS 'Дата создания записи';

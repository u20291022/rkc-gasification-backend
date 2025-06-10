-- Добавление поля date_create в таблицу t_gazifikacia_data
-- Выполните этот SQL в pgAdmin

ALTER TABLE s_gazifikacia.t_gazifikacia_data 
ADD COLUMN date_create TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Устанавливаем значение по умолчанию для существующих записей
UPDATE s_gazifikacia.t_gazifikacia_data 
SET date_create = CURRENT_TIMESTAMP 
WHERE date_create IS NULL;

-- Добавляем комментарий к полю
COMMENT ON COLUMN s_gazifikacia.t_gazifikacia_data.date_create IS 'Дата создания записи';

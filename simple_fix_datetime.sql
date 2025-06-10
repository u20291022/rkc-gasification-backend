-- Простое решение проблемы с datetime
-- Выполните этот SQL в pgAdmin

-- Сначала удаляем зависимое представление
DROP VIEW IF EXISTS s_gazifikacia.excel_export_09_06_25 CASCADE;

-- Убираем DEFAULT из поля, чтобы Tortoise ORM мог управлять им сам
ALTER TABLE s_gazifikacia.t_gazifikacia_data 
ALTER COLUMN date_create DROP DEFAULT;

-- Устанавливаем тип без timezone для совместимости с Python datetime
ALTER TABLE s_gazifikacia.t_gazifikacia_data 
ALTER COLUMN date_create TYPE TIMESTAMP WITHOUT TIME ZONE;

-- Добавляем комментарий
COMMENT ON COLUMN s_gazifikacia.t_gazifikacia_data.date_create IS 'Дата создания записи (управляется из приложения)';

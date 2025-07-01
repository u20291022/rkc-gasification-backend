# Оптимизация экспорта

## Что было сделано

### 1. Оптимизация функции экспорта (`export_utils.py`)

**Основные улучшения:**
- **Единый SQL запрос**: Вместо множественных запросов к базе данных теперь используется один оптимизированный SQL запрос с JOIN'ами
- **Удаление дублирования**: Убрана дублирующая логика получения адресов
- **Параметризованные запросы**: Использование безопасных параметризованных запросов вместо форматирования строк
- **Оптимизированная фильтрация**: Фильтры по району и улице применяются в памяти после получения данных

**Структура оптимизированного запроса:**
```sql
SELECT DISTINCT ON (gd.id_address) 
    gd.id_address, gd.id_type_address, gd.date_create, gd.from_login,
    a.id_mo, a.district, a.city, a.street, a.house, a.flat, a.from_login as address_from_login
FROM s_gazifikacia.t_gazifikacia_data gd
JOIN s_gazifikacia.t_address_v2 a ON gd.id_address = a.id
WHERE gd.id_type_address IN (3, 4, 6, 7, 8) 
    AND gd.is_mobile = true 
    AND gd.deleted = false
    AND a.deleted = false
    AND a.house IS NOT NULL
    [+ фильтры по mo_id и датам]
ORDER BY gd.id_address, gd.date_create DESC
```

### 2. Поддержка дат с временем

Функция `parse_date` поддерживает следующие форматы:
- `YYYY-MM-DD` - только дата
- `YYYY-MM-DDTHH:MM:SS` - дата и время
- `YYYY-MM-DDTHH:MM:SS.ffffff` - дата и время с микросекундами

### 3. Обновленный API эндпоинт

**URL**: `GET /export`

**Параметры:**
- `mo_id` (Optional[int]) - ID муниципалитета
- `district` (Optional[str]) - Название района
- `street` (Optional[str]) - Название улицы
- `date_from` (Optional[str]) - Начальная дата/время в формате YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS
- `date_to` (Optional[str]) - Конечная дата/время в формате YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS
- `only_new` (Optional[bool]) - Выгружать только новые записи с последней выгрузки
- `client_source` (Optional[str]) - Источник запроса (web, bot, api) для логирования

**Особенности:**
- Поддерживает фильтрацию по дате и времени
- Универсальный для всех клиентов (веб, бот, API)
- Отдельное логирование в зависимости от источника

## Как использовать для бота

### Сценарий использования:

1. **Первый запрос** (выгрузка всех данных):
   ```
   GET /export?mo_id=123&client_source=bot
   ```

2. **Бот сохраняет время последней выгрузки**: `2025-07-01T14:30:00`

3. **Последующие запросы** (только новые данные):
   ```
   GET /export?mo_id=123&date_from=2025-07-01T14:30:00&client_source=bot
   ```

4. **Бот обновляет время последней выгрузки** после успешного экспорта

### Пример для бота на Python:

```python
import asyncio
import aiohttp
from datetime import datetime

class GazificationBot:
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url
        self.last_export_time = None
    
    async def export_data(self, mo_id=None, district=None, street=None):
        params = {"client_source": "bot"}
        if mo_id:
            params['mo_id'] = mo_id
        if district:
            params['district'] = district
        if street:
            params['street'] = street
        if self.last_export_time:
            params['date_from'] = self.last_export_time.isoformat()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_base_url}/export", params=params) as response:
                if response.status == 200:
                    # Сохраняем файл
                    content = await response.read()
                    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    with open(filename, 'wb') as f:
                        f.write(content)
                    
                    # Обновляем время последней выгрузки
                    self.last_export_time = datetime.now()
                    return filename
                else:
                    raise Exception(f"Export failed: {response.status}")
```

## Преимущества оптимизации

1. **Производительность**: Значительно меньше запросов к базе данных
2. **Безопасность**: Параметризованные запросы защищают от SQL injection
3. **Гибкость**: Поддержка точного времени в фильтрах
4. **Универсальность**: Один API для всех клиентов
5. **Логирование**: Отслеживание источника запросов
6. **Масштабируемость**: Лучшая производительность при больших объемах данных

## Совместимость

- Существующий API `/export` расширен дополнительными параметрами
- Все существующие клиенты продолжат работать как прежде
- Новые параметры опциональные и не ломают совместимость

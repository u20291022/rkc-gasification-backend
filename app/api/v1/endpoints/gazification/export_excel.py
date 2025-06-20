from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.core.exceptions import DatabaseError
from app.core.export_utils import get_gazification_data
from app.core.export_optimization import create_excel_data_vectorized, create_optimized_dataframe
from app.core.export_config import get_vectorized_threshold, get_optimization_config
from typing import Optional
from datetime import date
import pandas as pd
import tempfile
import os
from datetime import datetime
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)
config = get_optimization_config()

router = APIRouter()

@router.get("/export", response_class=FileResponse)
async def export_to_excel(
    mo_id: Optional[int] = Query(None, description="ID муниципалитета"),
    district: Optional[str] = Query(None, description="Название района"),
    street: Optional[str] = Query(None, description="Название улицы"),
    date_from: Optional[date] = Query(None, description="Начальная дата для фильтрации (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Конечная дата для фильтрации (YYYY-MM-DD)"),
):
    """
    Экспорт данных в Excel файл
    
    Принимает фильтры (муниципалитет, район, улица, даты) и создает Excel-файл с данными.
    Если параметры не указаны, выгружаются все данные.
    """
    try:
        logger.info(f"Starting export with filters: mo_id={mo_id}, district={district}, street={street}, date_from={date_from}, date_to={date_to}")
        
        addresses, questions, answers = await get_gazification_data(
            mo_id, district, street, date_from, date_to
        )
        
        if not addresses:
            raise HTTPException(
                status_code=404, 
                detail="Не найдено данных для экспорта с указанными параметрами"
            )
        
        logger.info(f"Retrieved {len(addresses)} addresses, {len(questions)} questions")
        
        # ОПТИМИЗАЦИЯ: Используем векторизованное создание данных для больших объемов
        vectorized_threshold = get_vectorized_threshold()
        if len(addresses) > vectorized_threshold:
            logger.info("Using vectorized data creation for large dataset")
            data = create_excel_data_vectorized(addresses, questions, answers)
        else:
            # Для небольших объемов используем стандартный подход
            data = []
            gas_status_map = {3: "Да", 6: "Адрес не существует", 4: "Нет", 7: "Нет"}
            question_columns = [(q['id'], q.get('type_value', f"Вопрос {q['id']}")) for q in questions]
            
            for address in addresses:
                # Быстрое определение статуса газификации
                gas_status = gas_status_map.get(address.get('gas_type'), "Нет")
                
                # Оптимизированное форматирование даты
                date_create_formatted = None
                date_create = address.get('date_create')
                if date_create:
                    try:
                        date_with_offset = date_create + timedelta(hours=7)
                        date_create_formatted = date_with_offset.strftime("%d.%m.%Y %H:%M")
                    except:
                        date_create_formatted = str(date_create)
                
                # Определяем район/город
                district_city = address.get('district') or address.get('city') or 'Не указан'
                
                # Создаем базовую строку данных оптимизированно
                row = {
                    'Дата создания': date_create_formatted,
                    'Создатель адреса': address.get('from_login') or 'Отсутствует',
                    'Отправитель': address.get('gas_from_login') or 'Отсутствует',
                    'Муниципалитет': address.get('mo_name', 'Не указан'),
                    'Район': district_city,
                    'Улица': address.get('street') or 'Не указана',
                    'Дом': address.get('house', 'Не указан'),
                    'Квартира': address.get('flat', ''),
                    'Газифицирован?': gas_status,
                }
                
                # Быстрое добавление ответов на вопросы
                address_id = address['id']
                address_answers = answers.get(address_id, {})
                
                # Используем dict comprehension для быстрого добавления ответов
                row.update({
                    column_name: address_answers.get(question_id, '')
                    for question_id, column_name in question_columns
                })
                    
                data.append(row)
        
        # Проверяем, что данные есть
        if not data:
            raise HTTPException(
                status_code=404, 
                detail="Нет данных для экспорта после фильтрации"
            )
        
        # Создаем DataFrame оптимизированно для больших объемов
        if len(data) > vectorized_threshold:
            df = await create_optimized_dataframe(data)
        else:
            df = pd.DataFrame(data)
        
        # Создаем Excel файл с оптимизированными настройками
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"gazification_export_{timestamp}.xlsx")
        
        # Используем настройки из конфигурации
        excel_options = config["excel_options"]
        formatting_config = config["excel_formatting"]
        column_config = config["excel_columns"]
        
        with pd.ExcelWriter(file_path, **excel_options) as writer:
            df.to_excel(writer, sheet_name='Газификация', index=False)
            
            workbook = writer.book
            worksheet = writer.sheets['Газификация']
            
            # Создаем форматы из конфигурации
            header_format = workbook.add_format(formatting_config["header_format"])
            cell_format = workbook.add_format(formatting_config["cell_format"])
            date_format = workbook.add_format(formatting_config["date_format"])
            
            # Применяем форматирование к заголовкам и настраиваем ширину колонок
            for col_num, column_name in enumerate(df.columns):
                worksheet.write(0, col_num, column_name, header_format)
                
                # Устанавливаем ширину колонки из конфигурации
                column_width = column_config.get(column_name, column_config["default_width"])
                worksheet.set_column(col_num, col_num, column_width)
            
            # Оптимизированное форматирование данных
            num_rows = len(df)
            if num_rows > 0:
                # Находим колонку с датами
                date_col = None
                for col_num, column_name in enumerate(df.columns):
                    if column_name == 'Дата создания':
                        date_col = col_num
                        break
                
                # Форматируем все данные кроме дат
                for col_num in range(len(df.columns)):
                    if col_num != date_col:
                        for row_num in range(1, num_rows + 1):
                            worksheet.write(row_num, col_num, df.iloc[row_num-1, col_num], cell_format)
                
                # Специальное форматирование для дат
                if date_col is not None:
                    for row_num in range(1, num_rows + 1):
                        cell_value = df.iloc[row_num-1, date_col]
                        if cell_value and isinstance(cell_value, str):
                            try:
                                date_obj = datetime.strptime(cell_value, "%d.%m.%Y %H:%M")
                                worksheet.write(row_num, date_col, date_obj, date_format)
                            except:
                                worksheet.write(row_num, date_col, cell_value, cell_format)
                        else:
                            worksheet.write(row_num, date_col, cell_value, cell_format)
            
            # Логирование результата
            log_db_operation("export", "Excel", {
                "mo_id": mo_id, 
                "district": district, 
                "street": street,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "rows": len(data),
                "questions": len(questions),
                "file": file_path,
                "unique_addresses": len(addresses),
                "optimization_used": "vectorized" if len(addresses) > vectorized_threshold else "standard"
            })
        
        # Возвращаем файл с оптимизированными заголовками
        return FileResponse(
            path=file_path,
            filename=f"gazification_export_{timestamp}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Cache-Control": "no-cache"}
        )
        
    except Exception as e:
        logger.error(f"Error during Excel export: {str(e)}")
        raise DatabaseError(f"Ошибка при экспорте данных в Excel: {str(e)}")

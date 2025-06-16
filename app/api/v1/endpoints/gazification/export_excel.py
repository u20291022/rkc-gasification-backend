from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.core.exceptions import DatabaseError
from app.core.export_utils import get_gazification_data
from typing import Optional
from datetime import date
import pandas as pd
import tempfile
import os
from datetime import datetime
from datetime import timedelta

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
        addresses, questions, answers = await get_gazification_data(
            mo_id, district, street, date_from, date_to
        )
        
        if not addresses:
            raise HTTPException(
                status_code=404, 
                detail="Не найдено данных для экспорта с указанными параметрами"
            )
        
        # Создаем DataFrame для экспорта
        # Сначала создаем словарь для отслеживания уникальных адресов
        unique_addresses = {}
        
        for address in addresses:
            # Создаем ключ для идентификации уникального адреса
            address_key = (
                address.get('id_mo'),
                (address.get('district') or '').strip().lower(),
                (address.get('city') or '').strip().lower(), 
                (address.get('street') or '').strip().lower(),
                (address.get('house') or '').strip().lower(),
                (address.get('flat') or '').strip().lower()
            )
            
            # Если адрес уже есть, сравниваем даты и оставляем более свежий
            if address_key in unique_addresses:
                existing_date = unique_addresses[address_key].get('date_create')
                current_date = address.get('date_create')
                
                # Если у текущего адреса дата новее (или у существующего нет даты)
                if current_date and (not existing_date or current_date > existing_date):
                    unique_addresses[address_key] = address
            else:
                unique_addresses[address_key] = address
        
        # Создаем данные для экспорта из уникальных адресов
        data = []
        for address in unique_addresses.values():
            gas_status = "Да" if address.get('gas_type') == 3 else "Нет"
            date_create_formatted = None
            if address.get('date_create'):
                date_with_offset = address['date_create'] + timedelta(hours=7)
                date_create_formatted = date_with_offset.strftime("%d.%m.%Y %H:%M")
            
            row = {
                'Дата создания': date_create_formatted,
                'Создатель адреса': address.get('from_login') or 'Отсутствует',
                'Отправитель': address.get('gas_from_login') or 'Отсутствует',
                'Муниципалитет': address.get('mo_name', 'Не указан'),
                'Район': address.get('district') or address.get('city') or 'Не указан',
                'Улица': address.get('street', 'Не указана'),
                'Дом': address.get('house', 'Не указан'),
                'Квартира': address.get('flat', ''),
                'Газифицирован?': gas_status,
            }
            
            # Добавляем столбцы для всех вопросов и их ответы
            for question in questions:
                question_id = question.get('id')
                column_name = question.get('type_value', f"Вопрос {question_id}")
                
                # Ищем ответ на вопрос для текущего адреса
                address_id = address.get('id')
                answer_value = ''
                
                if address_id in answers and question_id in answers[address_id]:
                    answer_value = answers[address_id][question_id]
                
                row[column_name] = answer_value
                
            data.append(row)
        
        # Создаем DataFrame и сохраняем в Excel
        df = pd.DataFrame(data)
        
        # Создаем временный файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"gazification_export_{timestamp}.xlsx")
        
        # Настройка стилей для Excel
        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Газификация', index=False)
            
            # Форматирование
            workbook = writer.book
            worksheet = writer.sheets['Газификация']
              # Форматы для заголовков и ячеек
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'align': 'center',
                'border': 1,
                'bg_color': '#D7E4BC'
            })
            
            cell_format = workbook.add_format({
                'border': 1,
                'text_wrap': True
            })
              # Формат для столбца с датами
            date_format = workbook.add_format({
                'border': 1,
                'num_format': 'dd.mm.yyyy hh:mm'
            })
            
            # Применяем форматирование к заголовкам
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, max(len(str(value)) + 2, 15))
            
            # Применяем форматирование к ячейкам
            for row_num in range(1, len(df) + 1):
                for col_num in range(len(df.columns)):
                    column_name = df.columns[col_num]
                    cell_value = df.iloc[row_num-1, col_num]
                      # Для столбца "Дата создания" применяем формат даты
                    if column_name == 'Дата создания' and cell_value:
                        # Преобразуем строку даты обратно в datetime для Excel
                        try:
                            if isinstance(cell_value, str) and cell_value:
                                date_obj = datetime.strptime(cell_value, "%d.%m.%Y %H:%M")
                                worksheet.write(row_num, col_num, date_obj, date_format)
                            else:
                                worksheet.write(row_num, col_num, cell_value, cell_format)
                        except:
                            worksheet.write(row_num, col_num, cell_value, cell_format)
                    else:
                        worksheet.write(row_num, col_num, cell_value, cell_format)
            
            # Автоподбор ширины столбцов
            for col_num, column in enumerate(df.columns):
                column_width = max(df[column].astype(str).map(len).max(), len(column) + 2)
                worksheet.set_column(col_num, col_num, min(column_width, 50))  # Ограничиваем максимальную ширину
            
            log_db_operation("export", "Excel", {
                "mo_id": mo_id, 
                "district": district, 
                "street": street,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "rows": len(data),
                "questions": len(questions),
                "file": file_path
            })
        
        # Возвращаем файл
        return FileResponse(
            path=file_path,
            filename=f"gazification_export_{timestamp}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except Exception as e:
        raise DatabaseError(f"Ошибка при экспорте данных в Excel: {str(e)}")
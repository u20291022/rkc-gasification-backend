from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.core.exceptions import DatabaseError
from app.core.export_utils import get_gazification_data
from typing import Optional
import pandas as pd
import tempfile
import os
from datetime import datetime

router = APIRouter()

@router.get("/export", response_class=FileResponse)
async def export_to_excel(
    mo_id: Optional[int] = Query(None, description="ID муниципалитета"),
    district: Optional[str] = Query(None, description="Название района"),
    street: Optional[str] = Query(None, description="Название улицы"),
):
    """
    Экспорт данных в Excel файл
    
    Принимает фильтры (муниципалитет, район, улица) и создает Excel-файл с данными.
    Хотя бы один из параметров должен быть указан.
    """
    # Проверяем, что хотя бы один из параметров указан
    if mo_id is None and district is None and street is None:
        raise HTTPException(
            status_code=400, 
            detail="Необходимо указать хотя бы один параметр: mo_id, district или street"
        )
    try:        # Получаем данные для экспорта
        addresses, questions, answers = await get_gazification_data(mo_id, district, street)
        
        if not addresses:
            raise HTTPException(
                status_code=404, 
                detail="Не найдено данных для экспорта с указанными параметрами"
            )
        
        # Создаем DataFrame для экспорта
        data = []
        for address in addresses:
            # Определяем статус газификации
            gas_status = "Да" if address.get('gas_type') == 3 else "Нет"
            
            row = {
                'Муниципалитет': address.get('mo_name', 'Не указан'),
                'Район': address.get('district') or address.get('city') or 'Не указан',
                'Улица': address.get('street', 'Не указана'),
                'Дом': address.get('house', 'Не указан'),
                'Квартира': address.get('flat', ''),
                'Газифицирован?': gas_status
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
            
            # Применяем форматирование к заголовкам
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, max(len(str(value)) + 2, 15))
            
            # Применяем форматирование к ячейкам
            for row_num in range(1, len(df) + 1):
                for col_num in range(len(df.columns)):
                    worksheet.write(row_num, col_num, df.iloc[row_num-1, col_num], cell_format)
            
            # Автоподбор ширины столбцов
            for col_num, column in enumerate(df.columns):
                column_width = max(df[column].astype(str).map(len).max(), len(column) + 2)
                worksheet.set_column(col_num, col_num, min(column_width, 50))  # Ограничиваем максимальную ширину
        
        log_db_operation("export", "Excel", {
            "mo_id": mo_id, 
            "district": district, 
            "street": street,
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
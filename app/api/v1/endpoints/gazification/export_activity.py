from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.core.exceptions import DatabaseError
from app.core.export_utils import get_activity_data
from typing import Optional
from datetime import date
import pandas as pd
import tempfile
import os
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/export-activity", response_class=FileResponse)
async def export_activity_to_excel(
    date_from: Optional[date] = Query(
        None, description="Начальная дата для фильтрации (YYYY-MM-DD)"
    ),
    date_to: Optional[date] = Query(
        None, description="Конечная дата для фильтрации (YYYY-MM-DD)"
    ),
):
    """
    Экспорт данных активности пользователей в Excel файл
    Создает Excel-файл с тремя столбцами:
    - Дата входа: дата создания сессии
    - Аккаунт: email пользователя
    - Количество внесений: количество операций в сессии
    """
    try:
        activities = await get_activity_data(date_from, date_to)
        if not activities:
            raise HTTPException(
                status_code=404,
                detail="Не найдено данных активности для экспорта с указанными параметрами",
            )
        data = []
        for activity in activities:
            date_create_formatted = None
            if activity.get("date_create"):
                date_with_offset = activity["date_create"] + timedelta(hours=7)
                date_create_formatted = date_with_offset.strftime("%d.%m.%Y %H:%M")
            row = {
                "Дата входа": date_create_formatted,
                "Аккаунт": activity.get("email", "Не указан"),
                "Количество внесений": activity.get("activity_count", 0),
            }
            data.append(row)
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"activity_export_{timestamp}.xlsx")
        with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Активность", index=False)
            workbook = writer.book
            worksheet = writer.sheets["Активность"]
            header_format = workbook.add_format(
                {
                    "bold": True,
                    "text_wrap": True,
                    "valign": "top",
                    "align": "center",
                    "border": 1,
                    "bg_color": "#D7E4BC",
                }
            )
            cell_format = workbook.add_format({"border": 1, "text_wrap": True})
            date_format = workbook.add_format(
                {"border": 1, "num_format": "dd.mm.yyyy hh:mm"}
            )
            number_format = workbook.add_format({"border": 1, "align": "center"})
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            for row_num in range(1, len(df) + 1):
                for col_num in range(len(df.columns)):
                    column_name = df.columns[col_num]
                    cell_value = df.iloc[row_num - 1, col_num]
                    if column_name == "Дата входа" and cell_value:
                        try:
                            if isinstance(cell_value, str) and cell_value:
                                date_obj = datetime.strptime(
                                    cell_value, "%d.%m.%Y %H:%M"
                                )
                                worksheet.write(row_num, col_num, date_obj, date_format)
                            else:
                                worksheet.write(
                                    row_num, col_num, cell_value, cell_format
                                )
                        except:
                            worksheet.write(row_num, col_num, cell_value, cell_format)
                    elif column_name == "Количество внесений":
                        worksheet.write(row_num, col_num, cell_value, number_format)
                    else:
                        worksheet.write(row_num, col_num, cell_value, cell_format)
            for col_num, column in enumerate(df.columns):
                column_width = max(
                    df[column].astype(str).map(len).max(), len(column) + 2
                )
                worksheet.set_column(col_num, col_num, min(column_width, 30))
            log_db_operation(
                "export",
                "Activity Excel",
                {
                    "date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None,
                    "rows": len(data),
                    "file": file_path,
                },
            )
        return FileResponse(
            path=file_path,
            filename=f"activity_export_{timestamp}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при экспорте данных активности в Excel: {str(e)}")

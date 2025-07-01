from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.core.exceptions import DatabaseError
from app.core.export_utils import get_optimized_gazification_data, parse_date
from typing import Optional
from datetime import datetime, timedelta
import pandas as pd
import tempfile
import os

router = APIRouter()


@router.get("/export", response_class=FileResponse)
async def export_to_excel(
    mo_id: Optional[int] = Query(None, description="ID муниципалитета"),
    district: Optional[str] = Query(None, description="Название района"),
    street: Optional[str] = Query(None, description="Название улицы"),
    date_from: Optional[str] = Query(
        None,
        description="Начальная дата для фильтрации (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)",
    ),
    date_to: Optional[str] = Query(
        None,
        description="Конечная дата для фильтрации (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)",
    ),
    only_new: Optional[bool] = Query(False, description="Выгружать только новые записи с последней выгрузки"),
    client_source: Optional[str] = Query("web", description="Источник запроса (web, bot, api)"),
):
    """
    Экспорт данных в Excel файл
    Принимает фильтры (муниципалитет, район, улица, даты) и создает Excel-файл с данными.
    Если параметры не указаны, выгружаются все данные.
    """
    try:
        dt_from = parse_date(date_from, is_start=True)
        dt_to = parse_date(date_to, is_start=False)
        addresses, questions, answers = await get_optimized_gazification_data(
            mo_id, district, street, dt_from, dt_to, only_new, "excel"
        )

        if not addresses:
            raise HTTPException(
                status_code=404,
                detail="Не найдено данных для экспорта с указанными параметрами",
            )

        data = []

        for address in addresses:
            gas_status = "Нет"

            if address.get("gas_type") == 3:
                gas_status = "Да"
            elif address.get("gas_type") == 6:
                gas_status = "Адрес не существует"
            elif address.get("gas_type") == 7:
                gas_status = "Собственника нет дома"
            elif address.get("gas_type") == 8:
                gas_status = "Внесён повторно"

            date_create_formatted = None

            if address.get("date_create"):
                date_with_offset = address["date_create"] + timedelta(hours=7)
                date_create_formatted = date_with_offset.strftime("%d.%m.%Y %H:%M")

            row = {
                "Дата создания": date_create_formatted,
                "Создатель адреса": address.get("from_login") or "Отсутствует",
                "Отправитель": address.get("gas_from_login") or "Отсутствует",
                "Муниципалитет": address.get("mo_name", "Не указан"),
                "Район": address.get("district") or address.get("city") or "Не указан",
                "Улица": address.get("street", "Не указана"),
                "Дом": address.get("house", "Не указан"),
                "Квартира": address.get("flat", ""),
                "Газифицирован?": gas_status,
            }

            for question in questions:
                question_id = question.get("id")
                column_name = question.get("type_value", f"Вопрос {question_id}")
                address_id = address.get("id")
                answer_value = ""
                if address_id in answers and question_id in answers[address_id]:
                    answer_value = answers[address_id][question_id]
                row[column_name] = answer_value
            data.append(row)

        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"gazification_export_{timestamp}.xlsx")

        with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Газификация", index=False)
            workbook = writer.book
            worksheet = writer.sheets["Газификация"]
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

            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, max(len(str(value)) + 2, 15))

            for row_num in range(1, len(df) + 1):
                for col_num in range(len(df.columns)):
                    column_name = df.columns[col_num]
                    cell_value = df.iloc[row_num - 1, col_num]
                    if column_name == "Дата создания" and cell_value:
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
                    else:
                        worksheet.write(row_num, col_num, cell_value, cell_format)

            for col_num, column in enumerate(df.columns):
                column_width = max(
                    df[column].astype(str).map(len).max(), len(column) + 2
                )
                worksheet.set_column(col_num, col_num, min(column_width, 50))

            log_db_operation(
                "export",
                f"Excel ({client_source})",
                {
                    "mo_id": mo_id,
                    "district": district,
                    "street": street,
                    "date_from": dt_from.isoformat() if dt_from else None,
                    "date_to": dt_to.isoformat() if dt_to else None,
                    "only_new": only_new,
                    "client_source": client_source,
                    "rows": len(data),
                    "questions": len(questions),
                    "file": file_path,
                },
            )

        return FileResponse(
            path=file_path,
            filename=f"gazification_export_{timestamp}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при экспорте данных в Excel: {str(e)}")

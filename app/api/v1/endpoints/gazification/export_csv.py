from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from app.core.export_utils import get_gazification_view_data, parse_date
from app.core.utils import log_db_operation
from typing import Optional
import csv
import io
from datetime import datetime

router = APIRouter()


@router.get("/export-csv")
async def export_gazification_to_csv(
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
    client_source: Optional[str] = Query("web", description="Источник запроса (web, bot, api)"),
):
    """
    Экспорт данных газификации в CSV файл с развернутыми ответами на вопросы.
    
    Выгружает данные на основе представления v_gazifikacia_data_10_07_2025
    с разворачиванием ответов на вопросы в отдельные колонки.
    
    Принимает фильтры:
    - mo_id: ID муниципалитета
    - district: название района 
    - street: название улицы
    - date_from/date_to: диапазон дат
    
    Если параметры не указаны, выгружаются все данные.
    """
    try:
        # Парсим даты
        dt_from = parse_date(date_from, is_start=True)
        dt_to = parse_date(date_to, is_start=False)
        
        # Получаем данные
        data = await get_gazification_view_data(
            mo_id=mo_id,
            district=district, 
            street=street,
            date_from=dt_from,
            date_to=dt_to
        )

        if not data:
            raise HTTPException(
                status_code=404,
                detail="Не найдено данных для экспорта с указанными параметрами",
            )

        # Нормализуем None значения для CSV
        for row in data:
            for key, value in row.items():
                if value is None:
                    row[key] = ""

        # Определяем заголовки CSV
        headers = [
            "ID адреса",
            "ID муниципалитета", 
            "Муниципалитет",
            "Город",
            "Улица",
            "Дом",
            "Квартира",
            "Район",
            "Дата создания",
            "ID типа адреса",
            "Тип адреса",
            "Мобильное приложение",
            "Дата",
            "Подал заявку",
            "Документы на домовладение",
            "Документы на земельный участок",
            "Есть отдельные жилые помещения",
            "Социальная поддержка",
            "Проинформирован о новых условиях",
            "Проинформирован о новой организации",
            "Планирует подключиться",
            "Причина",
            "Буклет с контактами",
            "Текущий способ отопления",
            "Причина нежелания",
            "Способ отопления"
        ]

        # Создаем CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
        
        # Записываем заголовки
        writer.writerow(headers)
        
        # Записываем данные
        for row in data:
            csv_row = [
                str(row.get("id_address", "")),
                str(row.get("id_mo", "")),
                str(row.get("name_mo", "")),
                str(row.get("city", "")),
                str(row.get("street", "")),
                str(row.get("house", "")),
                str(row.get("flat", "")),
                str(row.get("district", "")),
                str(row.get("date_doc", "")),
                str(row.get("id_type_address", "")),
                str(row.get("type_address", "")),
                "Да" if row.get("is_mobile") else "Нет",
                str(row.get("date", "")),
                str(row.get("podal_zaivku", "")),
                str(row.get("doc_na_domovladenie", "")),
                str(row.get("doc_na_zem_ych", "")),
                str(row.get("est_otdeln_zjil_pomech", "")),
                str(row.get("soc_potderhka", "")),
                str(row.get("proinformirovan_new_ystr", "")),
                str(row.get("proinformirovan_new_org", "")),
                str(row.get("planiryet_podkluchits", "")),
                str(row.get("prichina", "")),
                str(row.get("buklet_s_kontaktami", "")),
                str(row.get("tekychi_sposob_otoplenia", "")),
                str(row.get("prichina_nehelania", "")),
                str(row.get("sposob_otoplenia", ""))
            ]
            writer.writerow(csv_row)

        # Подготавливаем ответ
        output.seek(0)
        csv_content = output.getvalue()
        output.close()

        # Создаем имя файла с текущей датой
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gazification_data_{timestamp}.csv"

        # Логируем операцию
        log_db_operation(
            "export",
            "gazification_csv",
            {
                "mo_id": mo_id,
                "district": district,
                "street": street,
                "date_from": date_from,
                "date_to": date_to,
                "records_count": len(data),
                "client_source": client_source,
                "export_filename": filename
            },
        )

        # Возвращаем CSV как streaming response
        def iter_csv():
            yield csv_content.encode('utf-8-sig')  # BOM для корректного отображения в Excel
            
        return StreamingResponse(
            iter_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при экспорте данных: {str(e)}"
        )
